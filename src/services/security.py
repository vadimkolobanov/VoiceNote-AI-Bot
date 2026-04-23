"""Security primitives: argon2id-хэширование паролей + JWT access-токены.

Только чистые функции; никакой работы с БД здесь не ведётся (хранение
refresh-токенов — в ``src.services.auth_service``).

Ссылки на план:
- §5.2 — контракт auth endpoints
- §10.1 — "Пароли: argon2id (moderate profile)"
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from jose import JWTError, jwt

from src.core.config import JWT_ALGORITHM, JWT_SECRET_KEY

# Moderate profile (OWASP 2024 baseline: 19 MiB RAM, 2 iterations, 1 lane).
# argon2-cffi дефолты близки к этому; параметры фиксируем явно.
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19 * 1024,  # kibibytes
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

# §5.2: access 30 минут, refresh 30 дней.
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30


def hash_password(plain: str) -> str:
    """Возвращает argon2id-хэш (self-contained, с параметрами и солью)."""
    return _hasher.hash(plain)


def verify_password(plain: str, stored_hash: str) -> bool:
    """True, если ``plain`` соответствует ``stored_hash``. False — иначе.

    Ловим весь ``VerificationError``-subtree: mismatch, invalid hash формат,
    decoding error (мусор в колонке). Наружу 500 не летит — решение о HTTP
    принимает уже auth-слой.
    """
    try:
        _hasher.verify(stored_hash, plain)
        return True
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    """Нужно ли пересохранить хэш с обновлёнными параметрами argon2id."""
    return _hasher.check_needs_rehash(stored_hash)


def create_access_token(user_id: int, *, expires_delta: timedelta | None = None) -> str:
    """JWT access-токен; payload: ``sub = str(user_id)``, ``type = "access"``."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Возвращает user_id из валидного access-токена, иначе None.

    None покрывает: истёкший токен, неверная подпись, неверный type,
    отсутствие/кривой ``sub``. Вызывающий поднимает 401 уже сам.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    sub = payload.get("sub")
    if not isinstance(sub, str):
        return None
    try:
        return int(sub)
    except ValueError:
        return None


def hash_refresh_token(token: str) -> str:
    """SHA-256 hex digest; достаточно для одноразового sparce-хранения."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
