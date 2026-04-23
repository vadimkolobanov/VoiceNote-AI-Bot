"""Сборка default-роутера для prod по таблице §6.0.

Бизнес-код должен получать роутер через ``build_default_router()`` и
переиспользовать один экземпляр (предпочтительно через FastAPI dependency).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from .base import LLMRouter, LLMTask, ProviderConfig
from .providers.claude_hetzner import ClaudeHetznerProvider
from .providers.deepseek import DeepSeekProvider
from .usage import DbUsageLogger, InMemoryUsageLogger


# Цены на 2026-04: консервативные оценки из PRODUCT_PLAN.md §18.5.
# Единицы — ₽ за 1M токенов. Меняются только централизованно, чтобы
# сохранялась предсказуемость бюджета.
DEEPSEEK_PRICE_IN_RUB = Decimal("25")    # ~0.27 $ при курсе ~92; с запасом
DEEPSEEK_PRICE_OUT_RUB = Decimal("100")

CLAUDE_HAIKU_PRICE_IN_RUB = Decimal("95")
CLAUDE_HAIKU_PRICE_OUT_RUB = Decimal("475")


def build_default_router(
    *,
    usage_logger_kind: str = "db",
) -> LLMRouter:
    """Создать роутер с prod-таблицей провайдеров.

    ``usage_logger_kind`` — 'db' (пишет в ai_usage) или 'memory' (для тестов
    без БД, удобно в CI smoke).
    """
    deepseek = DeepSeekProvider()
    claude = ClaudeHetznerProvider()

    deepseek_cfg = ProviderConfig(
        name="deepseek",
        provider=deepseek,
        model="deepseek-chat",
        price_per_mtok_input_rub=DEEPSEEK_PRICE_IN_RUB,
        price_per_mtok_output_rub=DEEPSEEK_PRICE_OUT_RUB,
    )
    claude_cfg = ProviderConfig(
        name="claude-haiku",
        provider=claude,
        model="claude-haiku-4-5-20251001",
        price_per_mtok_input_rub=CLAUDE_HAIKU_PRICE_IN_RUB,
        price_per_mtok_output_rub=CLAUDE_HAIKU_PRICE_OUT_RUB,
    )

    # §6.0 таблица. Пока без GigaChat-Lite / YandexGPT Lite (M11+).
    providers_by_task = {
        LLMTask.FACET_EXTRACT: [deepseek_cfg],
        LLMTask.FACTS_EXTRACT: [deepseek_cfg],
        # Primary — Claude, fallback — DeepSeek (graceful degradation §18.2).
        LLMTask.AGENT_ASK: [claude_cfg, deepseek_cfg],
        LLMTask.DIGEST_WRITE: [deepseek_cfg],
        LLMTask.PROACTIVE: [deepseek_cfg],
        LLMTask.IMPORT_BULK: [deepseek_cfg],
    }

    usage_logger: Optional[DbUsageLogger | InMemoryUsageLogger]
    if usage_logger_kind == "db":
        usage_logger = DbUsageLogger()
    elif usage_logger_kind == "memory":
        usage_logger = InMemoryUsageLogger()
    else:
        usage_logger = None

    return LLMRouter(
        providers_by_task=providers_by_task,
        usage_logger=usage_logger,
    )
