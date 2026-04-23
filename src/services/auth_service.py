"""Auth-service для email/password flow.

Спецификация: docs/PRODUCT_PLAN.md §5.2.

Работает поверх нового SQLAlchemy-слоя (``src.db``). Legacy-код в
``src/database/user_repo.py`` не трогаем — он обслуживает старую схему
до финальной миграции §4.9.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import RefreshToken, User
from src.services.security import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    verify_password,
)


class AuthError(Exception):
    """База для ошибок auth-слоя; ловится на уровне FastAPI-хендлера."""


class EmailAlreadyRegistered(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class InvalidRefreshToken(AuthError):
    pass


class UserNotFound(AuthError):
    pass


@dataclass(slots=True)
class TokenPair:
    access: str
    refresh: str
    user: User


async def register_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: Optional[str] = None,
) -> TokenPair:
    """§5.2 ``POST /auth/email/register``.

    Raises:
        EmailAlreadyRegistered: если email занят.
    """
    normalized_email = email.strip().lower()

    existing = await session.scalar(select(User).where(User.email == normalized_email))
    if existing is not None and existing.deleted_at is None:
        raise EmailAlreadyRegistered()

    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        display_name=(display_name or "").strip() or None,
    )
    session.add(user)
    try:
        await session.flush()  # получить user.id
    except IntegrityError as exc:  # race — кто-то зарегистрировался параллельно
        raise EmailAlreadyRegistered() from exc

    return await _issue_token_pair(session, user)


async def login_user(
    session: AsyncSession, *, email: str, password: str
) -> TokenPair:
    """§5.2 ``POST /auth/email/login``.

    Raises:
        InvalidCredentials: если юзера нет / пароль не совпал / soft-deleted.
    """
    normalized_email = email.strip().lower()
    user = await session.scalar(select(User).where(User.email == normalized_email))

    # Универсальная ошибка, чтобы не дать отличить «нет пользователя» от
    # «пароль неверный» (тайминг-атаки на email enumeration).
    if user is None or user.deleted_at is not None or user.password_hash is None:
        # Всё равно тратим CPU на верификацию, чтобы тайминги были стабильны.
        verify_password(password, "$argon2id$v=19$m=19456,t=2,p=1$"
                                  "fake_salt_1234567890$fake_hash_abcdefghij")
        raise InvalidCredentials()

    if not verify_password(password, user.password_hash):
        raise InvalidCredentials()

    # Прозрачный upgrade хэша при смене параметров argon2id.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    return await _issue_token_pair(session, user)


async def refresh_tokens(session: AsyncSession, *, refresh_token: str) -> TokenPair:
    """§5.2 ``POST /auth/refresh``. С ротацией: старый токен сразу отзывается."""
    token_hash = hash_refresh_token(refresh_token)

    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    if row is None:
        raise InvalidRefreshToken()

    now = datetime.now(timezone.utc)
    if row.revoked_at is not None or row.expires_at <= now:
        raise InvalidRefreshToken()

    user = await session.get(User, row.user_id)
    if user is None or user.deleted_at is not None:
        raise InvalidRefreshToken()

    # Ротация — отзываем старый ПЕРЕД выдачей нового (чтобы не накопить дубли
    # при ретрае в случае сетевой ошибки клиента).
    row.revoked_at = now

    return await _issue_token_pair(session, user)


async def logout(session: AsyncSession, *, refresh_token: str) -> None:
    """§5.2 ``POST /auth/logout``. Идемпотентно."""
    token_hash = hash_refresh_token(refresh_token)
    await session.execute(
        update(RefreshToken)
        .where(and_(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None)))
        .values(revoked_at=datetime.now(timezone.utc))
    )


async def soft_delete_user(session: AsyncSession, *, user_id: int) -> None:
    """§5.2 ``POST /auth/delete``. Ставит ``deleted_at`` и отзывает все токены.

    Фактическое cascade-удаление данных через 14 дней делает отдельный job
    (появится в M7+; см. §10.1).
    """
    user = await session.get(User, user_id)
    if user is None:
        raise UserNotFound()

    now = datetime.now(timezone.utc)
    user.deleted_at = now

    await session.execute(
        update(RefreshToken)
        .where(and_(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)))
        .values(revoked_at=now)
    )


# --- internal ---------------------------------------------------------------


def _generate_refresh_token() -> str:
    """64 байта случайных данных base64url-encoded; ~86 символов."""
    return secrets.token_urlsafe(64)


async def _issue_token_pair(session: AsyncSession, user: User) -> TokenPair:
    refresh_plain = _generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_plain),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return TokenPair(
        access=create_access_token(user.id),
        refresh=refresh_plain,
        user=user,
    )
