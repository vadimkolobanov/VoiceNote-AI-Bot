"""FastAPI-зависимости для /api/v1 (новая схема auth).

Старый `src/web/api/dependencies.py` продолжает обслуживать legacy-эндпоинты
(на Telegram-токенах и telegram_id). Новый слой работает по ``users.id``.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User
from src.db.session import get_session
from src.services.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Extract + validate access JWT, return the ``User`` row.

    Raises 401 для любой проблемы (no token / bad token / expired / soft-deleted).
    """
    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Missing bearer token"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = decode_access_token(creds.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired token"}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
