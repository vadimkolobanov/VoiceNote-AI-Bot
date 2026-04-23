"""UsageLogger — пишет в ``ai_usage`` по §18.4.

Используется LLMRouter'ом после каждого удачного вызова. В тестах
подменяется на ``InMemoryUsageLogger``, чтобы не поднимать БД.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.db.models import AiUsage
from src.db.session import AsyncSessionLocal

from .base import LLMResponse, LLMTask

logger = logging.getLogger(__name__)


class DbUsageLogger:
    """Async-запись одной строки в ``ai_usage`` на каждый LLM-вызов.

    Собственная сессия: не мешается в транзакцию бизнес-запроса, не
    блокируется её rollback'ом. Падения записи глотаются логом — они
    не должны ронять ответ клиенту (это аналитика, не контракт).
    """

    def __init__(
        self,
        sessionmaker: Optional[async_sessionmaker] = None,
    ) -> None:
        self._sessionmaker = sessionmaker or AsyncSessionLocal

    async def record(
        self,
        *,
        user_id: Optional[int],
        task: LLMTask,
        response: LLMResponse,
    ) -> None:
        try:
            async with self._sessionmaker() as session:
                session.add(
                    AiUsage(
                        user_id=user_id,
                        task=task.value,
                        provider=response.provider,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        audio_seconds=None,
                        cost_rub=response.cost_rub or Decimal("0"),
                        latency_ms=response.latency_ms,
                    )
                )
                await session.commit()
        except Exception:  # noqa: BLE001 — аналитика не должна ронять бизнес
            logger.exception(
                "Failed to record ai_usage: task=%s provider=%s",
                task.value,
                response.provider,
            )


# --- In-memory реализация для тестов ---------------------------------------


@dataclass(slots=True)
class UsageRecord:
    user_id: Optional[int]
    task: str
    provider: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    cost_rub: Decimal
    latency_ms: Optional[int]


class InMemoryUsageLogger:
    """Собирает usage-записи в список. Используется в тестах."""

    def __init__(self) -> None:
        self.records: list[UsageRecord] = []

    async def record(
        self,
        *,
        user_id: Optional[int],
        task: LLMTask,
        response: LLMResponse,
    ) -> None:
        self.records.append(
            UsageRecord(
                user_id=user_id,
                task=task.value,
                provider=response.provider,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost_rub=response.cost_rub,
                latency_ms=response.latency_ms,
            )
        )
