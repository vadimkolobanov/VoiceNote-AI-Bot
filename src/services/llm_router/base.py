"""Базовые типы LLMRouter: задача, ответ, ошибки, интерфейс провайдера.

Бизнес-код говорит с роутером терминами ``LLMTask`` (facet_extract, agent_ask,
digest_write, ...). Роутер сам решает, какой провайдер вызвать, пишет
стоимость в ``ai_usage`` и делает fallback при 5xx/timeout.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable


class LLMTask(str, Enum):
    """Задачи из §6.0 таблицы. Имя задачи = ключ в `ai_usage.task`."""

    FACET_EXTRACT = "facet_extract"          # текст → moment JSON (primary: DeepSeek)
    FACTS_EXTRACT = "facts_extract"          # Pro-only (§6.4)
    AGENT_ASK = "agent_ask"                  # Claude Haiku через Hetzner (§6.3)
    DIGEST_WRITE = "digest_write"            # утренний дайджест (§6.5)
    PROACTIVE = "proactive"                  # Pro проактивные подсказки
    IMPORT_BULK = "import_bulk"              # M10 bulk-импорт (§6.8)


class LLMRouterError(Exception):
    """Базовая ошибка роутера (все провайдеры упали / задача не настроена)."""


class ProviderError(Exception):
    """Провайдер вернул 5xx / timeout / некорректный формат.

    Роутер ловит ProviderError и переключается на fallback. Бизнес-логика
    ProviderError напрямую ловить не должна — только LLMRouterError.
    """


@dataclass(slots=True)
class LLMResponse:
    """Унифицированный ответ от LLM-провайдера."""

    content: str
    provider: str                            # 'deepseek' | 'claude-haiku' | ...
    model: str                               # конкретная модель (для логов)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_rub: Decimal = Decimal("0")
    latency_ms: Optional[int] = None
    raw: Optional[dict[str, Any]] = None     # сырой ответ API, для дебага

    @property
    def total_tokens(self) -> Optional[int]:
        if self.input_tokens is None or self.output_tokens is None:
            return None
        return self.input_tokens + self.output_tokens


@dataclass(slots=True)
class ProviderConfig:
    """Конфигурация одного провайдера для конкретной задачи.

    Роутер хранит словарь ``task -> [ProviderConfig, ProviderConfig, ...]`` —
    порядок = приоритет. Первый успешно ответивший выигрывает.
    """

    name: str                                # 'deepseek' | 'claude-haiku' | ...
    provider: "LLMProvider"
    model: str
    # Цена в рублях за 1M входных/выходных токенов. Grok-like оценка,
    # с перестраховкой в большую сторону — подробности в docs/PRODUCT_PLAN.md §18.5.
    price_per_mtok_input_rub: Decimal = Decimal("0")
    price_per_mtok_output_rub: Decimal = Decimal("0")
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Интерфейс провайдера. Реализации — в ``providers/*.py``."""

    async def chat(
        self,
        *,
        system: str,
        user: str,
        model: str,
        json_mode: bool = False,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        extra: Optional[dict[str, Any]] = None,
    ) -> LLMResponse: ...


class LLMRouter:
    """Маршрутизатор с fallback-политикой (§6.0).

    Держит mapping ``task -> [providers]``. ``chat()`` пытается provider'ов
    в порядке очереди, при ``ProviderError`` идёт к следующему. Если
    исчерпаны все — кидает ``LLMRouterError`` (вызывающий покажет юзеру
    graceful-сообщение по §18.2).

    Логирование стоимости — через callable ``usage_logger``, который
    вызывается после каждого удачного ответа. Это позволяет юнит-тестам
    подменять его на заглушку без подтягивания БД.
    """

    def __init__(
        self,
        *,
        providers_by_task: dict[LLMTask, list[ProviderConfig]],
        usage_logger: Optional["UsageLogger"] = None,
    ) -> None:
        self._providers = providers_by_task
        self._usage_logger = usage_logger

    async def chat(
        self,
        *,
        task: LLMTask,
        system: str,
        user: str,
        user_id: Optional[int] = None,
        json_mode: bool = False,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        queue = self._providers.get(task)
        if not queue:
            raise LLMRouterError(f"No providers configured for task={task.value}")

        last_error: Optional[Exception] = None
        import logging

        log = logging.getLogger(__name__)

        for idx, cfg in enumerate(queue):
            try:
                response = await cfg.provider.chat(
                    system=system,
                    user=user,
                    model=cfg.model,
                    json_mode=json_mode,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    extra=cfg.extra,
                )
            except ProviderError as exc:
                log.warning(
                    "LLM provider %s failed for task=%s (attempt %d/%d): %s",
                    cfg.name, task.value, idx + 1, len(queue), exc,
                )
                last_error = exc
                continue

            # Докручиваем цены, если провайдер сам не посчитал.
            if (
                response.cost_rub == 0
                and response.input_tokens is not None
                and response.output_tokens is not None
            ):
                response.cost_rub = (
                    Decimal(response.input_tokens)
                    * cfg.price_per_mtok_input_rub
                    / Decimal("1000000")
                    + Decimal(response.output_tokens)
                    * cfg.price_per_mtok_output_rub
                    / Decimal("1000000")
                )

            if self._usage_logger is not None:
                await self._usage_logger.record(
                    user_id=user_id,
                    task=task,
                    response=response,
                )
            return response

        raise LLMRouterError(
            f"All providers exhausted for task={task.value}"
        ) from last_error


@runtime_checkable
class UsageLogger(Protocol):
    """Интерфейс ``ai_usage``-писателя (§18.4). Конкретная реализация — в
    ``src.services.llm_router.usage``; тесты подставляют in-memory стаб."""

    async def record(
        self,
        *,
        user_id: Optional[int],
        task: LLMTask,
        response: LLMResponse,
    ) -> None: ...
