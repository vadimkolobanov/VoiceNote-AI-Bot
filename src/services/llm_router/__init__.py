"""LLMRouter — единая точка вызова LLM-провайдеров (PRODUCT_PLAN.md §6.0).

Прямых импортов ``anthropic``/``deepseek``/``yandexcloud`` в бизнес-логике
больше быть не должно. Всё — через ``LLMRouter.chat(task=..., ...)``.

Почему роутер, а не просто функции:
- единая fallback-политика (§6.0 таблица primary/fallback-1/fallback-2);
- единый учёт стоимости каждого вызова в таблице ``ai_usage`` (§18.4);
- возможность в M4+ воткнуть rate-limit слой и budget-gate (§18.2).
"""
from .base import LLMRouter, LLMTask, LLMResponse, ProviderError  # noqa: F401
from .router import build_default_router  # noqa: F401
