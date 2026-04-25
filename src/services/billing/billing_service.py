"""BillingService — domain-логика подписок (PRODUCT_PLAN.md §8).

Не знает про FastAPI / HTTP. Работает поверх SQLAlchemy + YooKassaClient.

Режимы (по env `YK_MODE`):
- 'yookassa' — реальные вызовы API (нужны YK_SHOP_ID + YK_SECRET_KEY)
- 'mock'    — без сети: создаёт «фейковый» payment, имитирует webhook
              через 3 секунды; нужен для локального UX-теста и CI

Ответственности:
- Создать Subscription (status='pending') + payment в провайдере
- Обработать webhook: проверить статус через GET и обновить
  subscription + user.pro_until
- Recurring charge: списать с сохранённого payment_method и продлить
- Отменить (auto_renew=false; pro_until остаётся до конца оплаченного периода)
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import (
    PLAN_MONTHLY_PRICE_RUB,
    PLAN_YEARLY_PRICE_RUB,
    YK_MODE,
    YK_RETURN_URL,
)
from src.db.models import Subscription, User

from .yookassa_client import Payment, YooKassaClient, YooKassaError

logger = logging.getLogger(__name__)


class BillingError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PlanInfo:
    code: str  # 'pro_monthly' | 'pro_yearly'
    title: str
    price_rub: str
    period_days: int
    description: str


def plans() -> list[PlanInfo]:
    return [
        PlanInfo(
            code="pro_monthly",
            title="Pro · месяц",
            price_rub=PLAN_MONTHLY_PRICE_RUB,
            period_days=30,
            description="Месячная подписка Pro",
        ),
        PlanInfo(
            code="pro_yearly",
            title="Pro · год",
            price_rub=PLAN_YEARLY_PRICE_RUB,
            period_days=365,
            description="Годовая подписка Pro (выгоднее ~27%)",
        ),
    ]


def _find_plan(code: str) -> PlanInfo:
    for p in plans():
        if p.code == code:
            return p
    raise BillingError(f"Unknown plan: {code}")


@dataclass(slots=True)
class CreateSubscriptionResult:
    subscription_id: int
    confirmation_url: Optional[str]
    external_id: str
    is_mock: bool


class BillingService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        client: Optional[YooKassaClient] = None,
        mode: Optional[str] = None,
    ) -> None:
        self._session = session
        self._client = client or YooKassaClient()
        self._mode = mode or YK_MODE

    # --- create -----------------------------------------------------------

    async def create_subscription(
        self,
        user: User,
        plan_code: str,
    ) -> CreateSubscriptionResult:
        plan = _find_plan(plan_code)
        if self._mode == "mock":
            return await self._create_mock(user, plan)
        return await self._create_yookassa(user, plan)

    async def _create_yookassa(
        self, user: User, plan: PlanInfo
    ) -> CreateSubscriptionResult:
        try:
            payment = await self._client.create_payment(
                amount_rub=plan.price_rub,
                description=f"{plan.description} · {user.email or user.id}",
                return_url=YK_RETURN_URL,
                save_payment_method=True,
                metadata={"user_id": str(user.id), "plan": plan.code},
            )
        except YooKassaError as exc:
            raise BillingError(f"YooKassa create_payment: {exc}") from exc

        sub = Subscription(
            user_id=user.id,
            provider="yookassa",
            external_id=payment.id,
            plan=plan.code,
            status="pending",
            raw_payload=payment.raw,
            auto_renew=True,
        )
        self._session.add(sub)
        await self._session.flush()
        return CreateSubscriptionResult(
            subscription_id=sub.id,
            confirmation_url=payment.confirmation_url,
            external_id=payment.id,
            is_mock=False,
        )

    async def _create_mock(
        self, user: User, plan: PlanInfo
    ) -> CreateSubscriptionResult:
        external_id = f"mock_{uuid.uuid4().hex[:24]}"
        sub = Subscription(
            user_id=user.id,
            provider="yookassa",
            external_id=external_id,
            plan=plan.code,
            status="pending",
            raw_payload={"mock": True, "plan": plan.code},
            auto_renew=True,
            payment_method_id=f"mock_pm_{uuid.uuid4().hex[:16]}",
        )
        self._session.add(sub)
        await self._session.flush()

        # Mock confirmation URL ведёт на наш собственный экран, который сразу
        # дёргает /billing/mock/confirm/{external_id} и закрывает себя.
        return CreateSubscriptionResult(
            subscription_id=sub.id,
            confirmation_url=f"voicenote://billing/mock?id={external_id}",
            external_id=external_id,
            is_mock=True,
        )

    # --- webhook ----------------------------------------------------------

    async def handle_webhook(
        self,
        notification: dict[str, Any],
    ) -> Optional[Subscription]:
        """YooKassa шлёт `{event, object: {id, status, ...}}`. Не верим
        payload-у в подписку — делаем GET /payments/{id} и трастим только
        ответ API. Возвращает обновлённую подписку или None если не нашли.
        """
        obj = notification.get("object") or {}
        payment_id = obj.get("id")
        if not payment_id:
            raise BillingError("webhook payload has no payment id")

        # Anti-spoof: реальный статус — только из GET /payments
        try:
            payment = await self._client.get_payment(payment_id)
        except YooKassaError as exc:
            raise BillingError(f"verify payment: {exc}") from exc

        return await self._apply_payment(payment)

    async def confirm_mock(self, external_id: str) -> Optional[Subscription]:
        """Mock-сценарий: имитируем 'payment.succeeded' для подписки
        с указанным external_id. Только при YK_MODE=mock."""
        if self._mode != "mock":
            raise BillingError("confirm_mock disabled when YK_MODE != mock")

        sub = await self._session.scalar(
            select(Subscription).where(Subscription.external_id == external_id)
        )
        if sub is None:
            return None

        plan = _find_plan(sub.plan)
        await self._activate(sub, plan_period_days=plan.period_days)
        return sub

    async def _apply_payment(self, payment: Payment) -> Optional[Subscription]:
        sub = await self._session.scalar(
            select(Subscription).where(Subscription.external_id == payment.id)
        )
        if sub is None:
            # Неизвестный payment — могла быть recurring-чарж, ищем по metadata
            user_id_str = payment.metadata.get("user_id")
            if user_id_str:
                # Пишем как новую запись «продление» — id payment'a в external_id.
                sub = Subscription(
                    user_id=int(user_id_str),
                    provider="yookassa",
                    external_id=payment.id,
                    plan=payment.metadata.get("plan", "pro_monthly"),
                    status="pending",
                    raw_payload=payment.raw,
                    auto_renew=True,
                    payment_method_id=payment.payment_method_id,
                )
                self._session.add(sub)
                await self._session.flush()

        if sub is None:
            logger.warning("Webhook for unknown payment %s — ignoring", payment.id)
            return None

        sub.raw_payload = payment.raw
        if payment.payment_method_id and not sub.payment_method_id:
            sub.payment_method_id = payment.payment_method_id

        if payment.status == "succeeded" and payment.paid:
            plan = _find_plan(sub.plan)
            await self._activate(sub, plan_period_days=plan.period_days)
        elif payment.status == "canceled":
            sub.status = "cancelled"
        else:
            sub.status = payment.status
        return sub

    async def _activate(
        self, sub: Subscription, *, plan_period_days: int
    ) -> None:
        now = datetime.now(timezone.utc)
        sub.started_at = sub.started_at or now
        sub.status = "active"

        user = await self._session.get(User, sub.user_id)
        if user is None:
            raise BillingError(f"user {sub.user_id} disappeared")

        # Если у юзера ещё есть Pro — продлеваем от его конца, иначе от now.
        from_date = (
            user.pro_until if user.pro_until and user.pro_until > now else now
        )
        new_end = from_date + timedelta(days=plan_period_days)
        sub.ends_at = new_end
        user.pro_until = new_end

    # --- recurring --------------------------------------------------------

    async def charge_recurring(self, sub: Subscription) -> Subscription:
        """Списать продление по сохранённому методу. Зовётся APScheduler-job-ом
        за день до `ends_at`. Mock-режим имитирует успех."""
        if not sub.payment_method_id:
            raise BillingError("subscription has no saved payment_method_id")

        plan = _find_plan(sub.plan)

        if self._mode == "mock":
            # Сразу «успешно» — pro_until продлевается.
            await self._activate(sub, plan_period_days=plan.period_days)
            return sub

        try:
            payment = await self._client.charge_with_saved_method(
                amount_rub=plan.price_rub,
                payment_method_id=sub.payment_method_id,
                description=f"{plan.description} (продление)",
                metadata={"user_id": str(sub.user_id), "plan": sub.plan},
            )
        except YooKassaError as exc:
            sub.status = "past_due"
            raise BillingError(f"recurring charge failed: {exc}") from exc

        if payment.status == "succeeded" and payment.paid:
            await self._activate(sub, plan_period_days=plan.period_days)
        else:
            sub.status = "past_due"
        return sub

    # --- cancel -----------------------------------------------------------

    async def cancel(self, sub: Subscription) -> Subscription:
        """Отменяем авто-продление. До `ends_at` Pro остаётся доступным."""
        sub.auto_renew = False
        return sub

    # --- read -------------------------------------------------------------

    async def status_for_user(self, user: User) -> dict[str, Any]:
        """Сводка для `GET /billing/status`."""
        sub = await self._session.scalar(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.id.desc())
            .limit(1)
        )
        is_pro = user.is_pro()
        return {
            "is_pro": is_pro,
            "pro_until": user.pro_until.isoformat() if user.pro_until else None,
            "plan": sub.plan if sub else None,
            "status": sub.status if sub else None,
            "auto_renew": sub.auto_renew if sub else False,
            "ends_at": sub.ends_at.isoformat() if sub and sub.ends_at else None,
        }
