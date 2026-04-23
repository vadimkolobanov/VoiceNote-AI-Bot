"""Unit-тесты LLMRouter — fallback-логика и стоимость (PRODUCT_PLAN.md §6.0, §18).

Провайдеров мокаем через stub-класс; сеть не ходим.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

import pytest

from src.services.llm_router.base import (
    LLMResponse,
    LLMRouter,
    LLMRouterError,
    LLMTask,
    ProviderConfig,
    ProviderError,
)
from src.services.llm_router.usage import InMemoryUsageLogger


class StubProvider:
    """Отвечает заданным response'ом или кидает ProviderError N раз подряд."""

    def __init__(
        self,
        *,
        response: Optional[LLMResponse] = None,
        fail_first_n: int = 0,
    ) -> None:
        self.response = response
        self.calls = 0
        self.fail_first_n = fail_first_n

    async def chat(self, **kwargs: Any) -> LLMResponse:
        self.calls += 1
        if self.calls <= self.fail_first_n:
            raise ProviderError("stub: forced failure")
        if self.response is None:
            raise ProviderError("stub: no response configured")
        return self.response


def _make_response(**overrides: Any) -> LLMResponse:
    defaults = dict(
        content="{}",
        provider="stub",
        model="stub-v1",
        input_tokens=100,
        output_tokens=50,
        latency_ms=200,
    )
    defaults.update(overrides)
    return LLMResponse(**defaults)


def _make_config(name: str, provider: StubProvider, *, in_price="10", out_price="30") -> ProviderConfig:
    return ProviderConfig(
        name=name,
        provider=provider,
        model="test-model",
        price_per_mtok_input_rub=Decimal(in_price),
        price_per_mtok_output_rub=Decimal(out_price),
    )


class TestRouterSuccess:
    async def test_first_provider_wins(self) -> None:
        p = StubProvider(response=_make_response(content="ok"))
        logger = InMemoryUsageLogger()
        router = LLMRouter(
            providers_by_task={LLMTask.FACET_EXTRACT: [_make_config("p1", p)]},
            usage_logger=logger,
        )

        resp = await router.chat(task=LLMTask.FACET_EXTRACT, system="s", user="u")
        assert resp.content == "ok"
        assert p.calls == 1
        assert len(logger.records) == 1
        assert logger.records[0].task == "facet_extract"

    async def test_cost_computed_from_tokens_and_price(self) -> None:
        """100 in × 10₽/M + 50 out × 30₽/M = 0.001 + 0.0015 = 0.0025 ₽."""
        p = StubProvider(response=_make_response(input_tokens=100, output_tokens=50))
        logger = InMemoryUsageLogger()
        router = LLMRouter(
            providers_by_task={
                LLMTask.FACET_EXTRACT: [_make_config("p", p, in_price="10", out_price="30")]
            },
            usage_logger=logger,
        )
        resp = await router.chat(task=LLMTask.FACET_EXTRACT, system="s", user="u")
        assert resp.cost_rub == Decimal("0.0025")
        assert logger.records[0].cost_rub == Decimal("0.0025")

    async def test_provider_own_cost_not_overwritten(self) -> None:
        """Если provider вернул cost_rub != 0 — роутер не пересчитывает."""
        p = StubProvider(response=_make_response(cost_rub=Decimal("1.23")))
        router = LLMRouter(
            providers_by_task={LLMTask.FACET_EXTRACT: [_make_config("p", p)]},
            usage_logger=None,
        )
        resp = await router.chat(task=LLMTask.FACET_EXTRACT, system="s", user="u")
        assert resp.cost_rub == Decimal("1.23")


class TestRouterFallback:
    async def test_first_fails_second_wins(self) -> None:
        p1 = StubProvider(fail_first_n=10)
        p2 = StubProvider(response=_make_response(content="from-p2", provider="p2"))
        router = LLMRouter(
            providers_by_task={
                LLMTask.AGENT_ASK: [_make_config("p1", p1), _make_config("p2", p2)]
            },
            usage_logger=None,
        )
        resp = await router.chat(task=LLMTask.AGENT_ASK, system="s", user="u")
        assert resp.content == "from-p2"
        assert p1.calls == 1
        assert p2.calls == 1

    async def test_all_fail_raises_router_error(self) -> None:
        p1 = StubProvider(fail_first_n=10)
        p2 = StubProvider(fail_first_n=10)
        router = LLMRouter(
            providers_by_task={
                LLMTask.AGENT_ASK: [_make_config("p1", p1), _make_config("p2", p2)]
            },
            usage_logger=None,
        )
        with pytest.raises(LLMRouterError):
            await router.chat(task=LLMTask.AGENT_ASK, system="s", user="u")


class TestRouterConfig:
    async def test_unknown_task_raises(self) -> None:
        router = LLMRouter(providers_by_task={}, usage_logger=None)
        with pytest.raises(LLMRouterError):
            await router.chat(task=LLMTask.FACET_EXTRACT, system="s", user="u")

    async def test_usage_logged_with_user_id(self) -> None:
        p = StubProvider(response=_make_response())
        logger = InMemoryUsageLogger()
        router = LLMRouter(
            providers_by_task={LLMTask.FACET_EXTRACT: [_make_config("p", p)]},
            usage_logger=logger,
        )
        await router.chat(task=LLMTask.FACET_EXTRACT, system="s", user="u", user_id=42)
        assert logger.records[0].user_id == 42


class TestPromptRender:
    """Проверяем, что промпт extract_facets рендерится без StrictUndefined."""

    def test_extract_facets_renders(self) -> None:
        from src.services.llm_router.prompts.loader import render

        out = render(
            "extract_facets",
            raw_text="купить молоко",
            timezone="Europe/Moscow",
            current_datetime_iso="2026-04-23T12:00:00+00:00",
            current_day_of_week="четверг",
            recent_titles=[],
            recent_facts=[],
            tomorrow_15h_utc="2026-04-24T12:00:00+00:00",
        )
        assert "купить молоко" in out
        assert "Europe/Moscow" in out
        # Версия промпта прописана в заголовке (Jinja set), на выходе её нет —
        # просто убеждаемся, что контент валидный.
        assert "Output schema" in out
