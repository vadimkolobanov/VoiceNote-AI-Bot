# src/web/api/mobile_auth.py
"""
Email/password аутентификация для мобильного приложения.
Полностью независима от Telegram.

Мобильный пользователь получает синтетический telegram_id (отрицательное число
из sequence mobile_user_id_seq), чтобы остаться совместимым с существующей схемой БД.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field

from src.database.connection import get_db_pool
from .auth import _issue_tokens, _revoke_refresh_token
from .dependencies import get_current_user
from .schemas import Token, UserProfile

router = APIRouter(prefix="/auth/email", tags=["Mobile Authentication"])

PASSWORD_MIN_LEN = 8
PASSWORD_MAX_LEN = 128
PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{%d,%d}$" % (PASSWORD_MIN_LEN, PASSWORD_MAX_LEN))


class EmailRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=PASSWORD_MIN_LEN, max_length=PASSWORD_MAX_LEN)
    first_name: str = Field(..., min_length=1, max_length=128)


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=PASSWORD_MAX_LEN)


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=PASSWORD_MIN_LEN, max_length=PASSWORD_MAX_LEN)


def _validate_password_strength(password: str) -> None:
    if not PASSWORD_RE.match(password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Password must be 8-128 chars and contain at least one letter and one digit."
            ),
        )


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


async def _allocate_mobile_user_id() -> int:
    """Выделяет синтетический telegram_id для мобильного пользователя (отрицательное число)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        seq_value = await conn.fetchval("SELECT nextval('mobile_user_id_seq')")
    # Отрицательные значения, чтобы не пересекаться с реальными Telegram ID.
    return -int(seq_value)


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register_with_email(payload: EmailRegisterRequest) -> dict:
    """Регистрация нового пользователя по email/паролю."""
    _validate_password_strength(payload.password)

    email_norm = payload.email.strip().lower()
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT telegram_id FROM users WHERE LOWER(email) = $1", email_norm
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists.",
            )

        synthetic_id = await _allocate_mobile_user_id()
        now = datetime.now(timezone.utc)

        await conn.execute(
            """
            INSERT INTO users (
                telegram_id, first_name, email, password_hash,
                auth_provider, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, 'email', $5, $5)
            """,
            synthetic_id,
            payload.first_name.strip(),
            email_norm,
            _hash_password(payload.password),
            now,
        )

    return await _issue_tokens(synthetic_id)


@router.post("/login", response_model=Token)
async def login_with_email(payload: EmailLoginRequest) -> dict:
    """Логин по email/паролю."""
    email_norm = payload.email.strip().lower()
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT telegram_id, password_hash
            FROM users
            WHERE LOWER(email) = $1 AND auth_provider = 'email'
            """,
            email_norm,
        )
    if row is None or not row["password_hash"] or not _verify_password(
        payload.password, row["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    return await _issue_tokens(row["telegram_id"])


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def change_password(
    payload: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user),
) -> Response:
    """Смена пароля."""
    _validate_password_strength(payload.new_password)

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT password_hash FROM users WHERE telegram_id = $1",
            current_user["telegram_id"],
        )
        if not row or not row["password_hash"] or not _verify_password(
            payload.current_password, row["password_hash"]
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            )

        await conn.execute(
            "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE telegram_id = $2",
            _hash_password(payload.new_password),
            current_user["telegram_id"],
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(
    payload: LogoutRequest,
    current_user: dict = Depends(get_current_user),
) -> Response:
    """Отзыв refresh token."""
    await _revoke_refresh_token(payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserProfile)
async def me(current_user: dict = Depends(get_current_user)) -> dict:
    """Текущий пользователь."""
    return current_user
