"""/api/v1/push/* — регистрация FCM-токенов (PRODUCT_PLAN.md §5.2, §9).

FCM-отправка реального пуша — в M7, тут только хранилище токенов.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PushToken, User
from src.db.session import get_session

from .dependencies import get_current_user

router = APIRouter(prefix="/push", tags=["push"])


class PushRegisterIn(BaseModel):
    token: str = Field(min_length=10, max_length=4096)
    platform: Literal["ios", "android"]


class PushUnregisterIn(BaseModel):
    token: str = Field(min_length=10, max_length=4096)


@router.post("/register", status_code=status.HTTP_200_OK)
async def register_token(
    payload: PushRegisterIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    existing = await session.scalar(
        select(PushToken).where(
            PushToken.user_id == user.id, PushToken.token == payload.token
        )
    )
    if existing is not None:
        existing.last_seen = datetime.now(timezone.utc)
        existing.platform = payload.platform
    else:
        session.add(
            PushToken(
                user_id=user.id,
                platform=payload.platform,
                token=payload.token,
            )
        )
    return {"status": "ok"}


@router.post("/unregister", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_token(
    payload: PushUnregisterIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    token = await session.scalar(
        select(PushToken).where(
            PushToken.user_id == user.id, PushToken.token == payload.token
        )
    )
    if token is not None:
        await session.delete(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
