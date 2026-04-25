"""/api/v1/billing/* — подписки YooKassa (PRODUCT_PLAN.md §5.2 + §8).

Webhook-эндпоинт публичный (без авторизации) — YooKassa бьёт по нему сама.
Защита от подделки — через GET /payments/{id} в BillingService (см. там).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import YK_MODE
from src.db.models import User
from src.db.session import get_session
from src.services.billing import BillingError, BillingService, plans

from .dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


# --- schemas ---------------------------------------------------------------


class PlanOut(BaseModel):
    code: str
    title: str
    price_rub: str
    period_days: int


class SubscribeIn(BaseModel):
    plan: str = Field(pattern="^(pro_monthly|pro_yearly)$")


class SubscribeOut(BaseModel):
    subscription_id: int
    confirmation_url: Optional[str] = None
    external_id: str
    is_mock: bool


class StatusOut(BaseModel):
    is_pro: bool
    pro_until: Optional[str] = None
    plan: Optional[str] = None
    status: Optional[str] = None
    auto_renew: bool
    ends_at: Optional[str] = None


# --- endpoints -------------------------------------------------------------


@router.get("/plans", response_model=list[PlanOut])
async def list_plans() -> list[PlanOut]:
    return [
        PlanOut(
            code=p.code,
            title=p.title,
            price_rub=p.price_rub,
            period_days=p.period_days,
        )
        for p in plans()
    ]


@router.post("/subscribe", response_model=SubscribeOut)
async def subscribe(
    payload: SubscribeIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SubscribeOut:
    service = BillingService(session)
    try:
        result = await service.create_subscription(user, payload.plan)
    except BillingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "BILLING_ERROR", "message": str(exc)}},
        )
    return SubscribeOut(
        subscription_id=result.subscription_id,
        confirmation_url=result.confirmation_url,
        external_id=result.external_id,
        is_mock=result.is_mock,
    )


@router.get("/status", response_model=StatusOut)
async def status_endpoint(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StatusOut:
    service = BillingService(session)
    data = await service.status_for_user(user)
    return StatusOut(**data)


@router.post("/cancel", status_code=status.HTTP_200_OK)
async def cancel(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Снимает auto-renew. Pro остаётся до конца оплаченного периода."""
    from sqlalchemy import desc, select

    from src.db.models import Subscription

    sub = await session.scalar(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .where(Subscription.status == "active")
        .order_by(desc(Subscription.id))
        .limit(1)
    )
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NO_ACTIVE_SUBSCRIPTION",
                    "message": "У тебя нет активной подписки.",
                }
            },
        )
    service = BillingService(session)
    await service.cancel(sub)
    return {"status": "ok"}


# --- webhook (public) ------------------------------------------------------


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """YooKassa HTTP-уведомление. Полезная нагрузка проверяется через
    GET /payments/{id} в BillingService (anti-spoof)."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception as exc:
        logger.warning("Webhook bad JSON: %s", exc)
        raise HTTPException(status_code=400, detail="bad json")

    service = BillingService(session)
    try:
        sub = await service.handle_webhook(body)
    except BillingError as exc:
        # Возвращаем 200 чтобы YooKassa не ретраила бесконечно — пишем в лог.
        logger.exception("Webhook handling failed: %s", exc)
        return {"status": "error", "message": str(exc)}

    return {"status": "ok", "subscription_id": str(sub.id) if sub else "none"}


# --- mock helper (только при YK_MODE=mock) --------------------------------


@router.post("/mock/confirm", status_code=status.HTTP_200_OK)
async def mock_confirm(
    external_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Mock-only: имитирует успешный платёж. Mobile-WebView в mock-режиме
    показывает кнопку «Я заплатил», которая дёргает этот endpoint.

    В режиме `YK_MODE=yookassa` возвращает 404 — чтобы прод не имел
    возможности сделать себе Pro бесплатно.
    """
    if YK_MODE != "mock":
        raise HTTPException(status_code=404, detail="not found")
    service = BillingService(session)
    try:
        sub = await service.confirm_mock(external_id)
    except BillingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if sub is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    if sub.user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    return {"status": "ok", "subscription_id": str(sub.id)}
