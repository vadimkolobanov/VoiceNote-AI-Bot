"""Billing — YooKassa-обёртка + сервисный слой подписок.

Точки входа бизнес-кода:
    BillingService.create_subscription(user, plan)
    BillingService.handle_webhook(notification_payload)
    BillingService.charge_recurring(subscription)  # для APScheduler
    BillingService.cancel(subscription)

Архитектура:
- yookassa_client: тонкий httpx-обёртка к Payments API v3
- billing_service: domain — пишет в `subscriptions`, обновляет `users.pro_until`
- mock_provider: тот же интерфейс, для CI и для juser-а без юр.лица
"""

from .billing_service import BillingService, BillingError, PlanInfo, plans  # noqa: F401
from .yookassa_client import (  # noqa: F401
    YooKassaClient,
    YooKassaError,
    Payment,
)
