"""/health — liveness + readiness (docs/PRODUCT_PLAN.md §11.1).

Контракт ответа:
    200 OK { "status": "ok", "version": "<git-sha|package>", "db": "ok|degraded" }

«ok» по БД — удачный ``SELECT 1``; «degraded» — исключение. Liveness-проверки
Docker/uptime можно бить хоть сюда, хоть в ``/api/v1/health``.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

# Версия приложения: читаем из переменной окружения (пишется в CI при сборке),
# fallback — 'dev' для локалки.
APP_VERSION = os.environ.get("APP_VERSION", "dev")


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    db_status = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — health-check ничего не пропускает дальше
        logger.warning("Health-check DB ping failed: %s", exc)
        db_status = "degraded"

    return {
        "status": "ok",
        "version": APP_VERSION,
        "db": db_status,
    }
