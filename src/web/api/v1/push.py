"""/api/v1/push/* — регистрация FCM-токенов (PRODUCT_PLAN.md §5.2, §9).

FCM-отправка реального пуша — в M7, тут только хранилище токенов.
"""
from __future__ import annotations

import httpx
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PushToken, User
from src.db.session import get_session
from src.services import push_service

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


class PushTestIn(BaseModel):
    title: str = Field(default="Methodex Manager", max_length=100)
    body: str = Field(default="Тестовый push 🚀", max_length=240)


@router.post("/test", status_code=status.HTTP_200_OK)
async def send_test_push(
    payload: PushTestIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Отправить тестовый push на все устройства текущего пользователя."""
    if not push_service.FIREBASE_INITIALIZED:
        raise HTTPException(503, "Firebase не инициализирован на сервере")

    rows = await session.scalars(
        select(PushToken).where(PushToken.user_id == user.id)
    )
    tokens = [r.token for r in rows]
    if not tokens:
        raise HTTPException(404, "У пользователя нет зарегистрированных устройств")

    access_token = push_service.get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    fcm_url = push_service.FCM_V1_URL_TEMPLATE.format(
        project_id=push_service.PROJECT_ID
    )
    sent, failed = 0, []
    async with httpx.AsyncClient(timeout=10) as client:
        for token in tokens:
            msg = {
                "message": {
                    "token": token,
                    "notification": {"title": payload.title, "body": payload.body},
                    "android": {"priority": "high"},
                }
            }
            try:
                resp = await client.post(fcm_url, headers=headers, json=msg)
                if 200 <= resp.status_code < 300:
                    sent += 1
                else:
                    failed.append({"prefix": token[:12], "status": resp.status_code, "err": resp.text[:200]})
            except Exception as e:
                failed.append({"prefix": token[:12], "err": str(e)[:200]})

    return {"sent": sent, "total": len(tokens), "failed": failed}


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
