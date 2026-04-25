"""Тонкая httpx-обёртка над YooKassa Payments API v3.

Контракт API: https://yookassa.ru/developers/api

Ключевые правила:
- Idempotence-Key обязателен на каждом POST. Используем UUID4 на вызов,
  плюс по задаче бизнес-слой может передать собственный (для повторов).
- Для боевой проверки статуса (внутри webhook-хендлера) после получения
  уведомления делаем GET /v3/payments/{id} и доверяем только этому ответу.
  Сами уведомления не подписываются — это требование самой YooKassa.
"""
from __future__ import annotations

import base64
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from src.core.config import (
    YK_API_BASE,
    YK_RETURN_URL,
    YK_SECRET_KEY,
    YK_SHOP_ID,
)

logger = logging.getLogger(__name__)


class YooKassaError(Exception):
    """Любая проблема с YooKassa: сеть, 4xx/5xx, кривой JSON."""


@dataclass(slots=True)
class Payment:
    """Унифицированный ответ. Полный JSON — в `raw`."""

    id: str
    status: str  # 'pending' | 'waiting_for_capture' | 'succeeded' | 'canceled'
    paid: bool
    amount_value: str
    amount_currency: str
    confirmation_url: Optional[str]
    payment_method_id: Optional[str]
    save_payment_method: bool
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Payment":
        amount = data.get("amount") or {}
        confirmation = data.get("confirmation") or {}
        pm = data.get("payment_method") or {}
        return cls(
            id=data["id"],
            status=data.get("status", "pending"),
            paid=bool(data.get("paid", False)),
            amount_value=str(amount.get("value", "0")),
            amount_currency=str(amount.get("currency", "RUB")),
            confirmation_url=confirmation.get("confirmation_url"),
            payment_method_id=pm.get("id"),
            save_payment_method=bool(data.get("save_payment_method", False)),
            metadata=dict(data.get("metadata") or {}),
            raw=data,
        )


class YooKassaClient:
    """Async httpx клиент. Создаёт сессию на каждый вызов; короткие пиковые
    нагрузки (один платёж на юзера) — connection pool не нужен."""

    def __init__(
        self,
        *,
        shop_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        api_base: str = YK_API_BASE,
        timeout_sec: int = 20,
    ) -> None:
        self._shop_id = shop_id or YK_SHOP_ID
        self._secret = secret_key or YK_SECRET_KEY
        self._api_base = api_base.rstrip("/")
        self._timeout = httpx.Timeout(timeout_sec)

    @property
    def configured(self) -> bool:
        return bool(self._shop_id and self._secret)

    # --- public ----------------------------------------------------------

    async def create_payment(
        self,
        *,
        amount_rub: str,
        description: str,
        return_url: str = YK_RETURN_URL,
        save_payment_method: bool = True,
        metadata: Optional[dict[str, Any]] = None,
        idempotence_key: Optional[str] = None,
    ) -> Payment:
        """Создаёт обычный платёж с redirect-confirmation.

        После успешной оплаты вернётся `payment_method.id`, который надо
        сохранить для recurring (см. `charge_with_saved_method`).
        """
        body: dict[str, Any] = {
            "amount": {"value": amount_rub, "currency": "RUB"},
            "capture": True,
            "save_payment_method": save_payment_method,
            "confirmation": {"type": "redirect", "return_url": return_url},
            "description": description,
        }
        if metadata:
            body["metadata"] = metadata
        data = await self._post("/payments", body, idempotence_key)
        return Payment.from_json(data)

    async def charge_with_saved_method(
        self,
        *,
        amount_rub: str,
        payment_method_id: str,
        description: str,
        metadata: Optional[dict[str, Any]] = None,
        idempotence_key: Optional[str] = None,
    ) -> Payment:
        """Recurring-списание без 3DS. Используется для авто-продления
        подписки (auto_renew=true)."""
        body: dict[str, Any] = {
            "amount": {"value": amount_rub, "currency": "RUB"},
            "capture": True,
            "payment_method_id": payment_method_id,
            "description": description,
        }
        if metadata:
            body["metadata"] = metadata
        data = await self._post("/payments", body, idempotence_key)
        return Payment.from_json(data)

    async def get_payment(self, payment_id: str) -> Payment:
        """GET /payments/{id} — авторитетный источник правды о статусе.
        Используется в webhook-хендлере для anti-spoofing."""
        data = await self._get(f"/payments/{payment_id}")
        return Payment.from_json(data)

    # --- internal --------------------------------------------------------

    def _auth_header(self) -> str:
        token = base64.b64encode(
            f"{self._shop_id}:{self._secret}".encode("utf-8")
        ).decode("ascii")
        return f"Basic {token}"

    async def _post(
        self,
        path: str,
        body: dict[str, Any],
        idempotence_key: Optional[str],
    ) -> dict[str, Any]:
        if not self.configured:
            raise YooKassaError(
                "YooKassa client not configured (YK_SHOP_ID/YK_SECRET_KEY missing). "
                "Set YK_MODE=mock for local dev or fill in test credentials."
            )
        headers = {
            "Authorization": self._auth_header(),
            "Content-Type": "application/json",
            "Idempotence-Key": idempotence_key or str(uuid.uuid4()),
        }
        url = self._api_base + path
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise YooKassaError(f"network error: {exc}") from exc

        if response.status_code >= 400:
            raise YooKassaError(
                f"{response.status_code} {response.text[:300]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise YooKassaError(f"bad JSON: {exc}") from exc

    async def _get(self, path: str) -> dict[str, Any]:
        if not self.configured:
            raise YooKassaError("YooKassa client not configured")
        headers = {"Authorization": self._auth_header()}
        url = self._api_base + path
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise YooKassaError(f"network error: {exc}") from exc
        if response.status_code >= 400:
            raise YooKassaError(
                f"{response.status_code} {response.text[:300]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise YooKassaError(f"bad JSON: {exc}") from exc
