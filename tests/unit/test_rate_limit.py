"""Unit-тесты RateLimiter + DailyQuota (PRODUCT_PLAN.md §5.1)."""
from __future__ import annotations

import pytest

from src.services.rate_limit import (
    DAILY_QUOTAS,
    DailyQuota,
    InMemoryKV,
    RateLimiter,
)


@pytest.fixture
def kv() -> InMemoryKV:
    return InMemoryKV()


# --- RateLimiter -----------------------------------------------------------


class TestRateLimiter:
    async def test_under_limit_allowed(self, kv: InMemoryKV) -> None:
        rl = RateLimiter(kv)
        for i in range(5):
            d = await rl.check(key="u1:moments", limit=10, window_sec=60)
            assert d.allowed
            assert d.remaining == 10 - (i + 1)

    async def test_over_limit_denied(self, kv: InMemoryKV) -> None:
        rl = RateLimiter(kv)
        for _ in range(3):
            await rl.check(key="u1", limit=3, window_sec=60)
        d = await rl.check(key="u1", limit=3, window_sec=60)
        assert not d.allowed
        assert d.remaining == 0

    async def test_separate_keys_independent(self, kv: InMemoryKV) -> None:
        rl = RateLimiter(kv)
        for _ in range(3):
            await rl.check(key="u1", limit=3, window_sec=60)
        # u2 НЕ использовал свой лимит
        d = await rl.check(key="u2", limit=3, window_sec=60)
        assert d.allowed


class _FailingKV:
    """Имитация Redis-недоступности: все вызовы падают."""

    async def incr(self, key: str) -> int:
        raise RuntimeError("redis down")

    async def expire(self, key: str, seconds: int) -> None:
        raise RuntimeError("redis down")

    async def get(self, key: str) -> str | None:
        raise RuntimeError("redis down")


class TestRateLimiterGracefulDegradation:
    async def test_kv_down_allows_request(self) -> None:
        """§18.2: Redis-рабочий, не обязательный — graceful degradation."""
        rl = RateLimiter(_FailingKV())
        d = await rl.check(key="u1", limit=5, window_sec=60)
        assert d.allowed


# --- DailyQuota ------------------------------------------------------------


class TestDailyQuota:
    async def test_free_user_moments_limit(self, kv: InMemoryKV) -> None:
        q = DailyQuota(kv)
        limit = DAILY_QUOTAS["moments_created"].free_per_day
        # Все попытки в пределах лимита — allowed
        for _ in range(limit):
            d = await q.check_and_inc(
                user_id=1, metric="moments_created", is_pro=False
            )
            assert d.allowed
        # Следующая — denied
        d = await q.check_and_inc(
            user_id=1, metric="moments_created", is_pro=False
        )
        assert not d.allowed

    async def test_pro_user_has_higher_limit(self, kv: InMemoryKV) -> None:
        q = DailyQuota(kv)
        # Берём free limit + 1 — free отрубился бы, pro пропустит
        free_limit = DAILY_QUOTAS["moments_created"].free_per_day
        for _ in range(free_limit + 1):
            d = await q.check_and_inc(
                user_id=5, metric="moments_created", is_pro=True
            )
            assert d.allowed

    async def test_agent_free_zero_quota(self, kv: InMemoryKV) -> None:
        """§5.1: агенту на free — 0 вопросов (paywall)."""
        q = DailyQuota(kv)
        d = await q.check_and_inc(
            user_id=9, metric="agent_questions", is_pro=False
        )
        assert not d.allowed

    async def test_stt_minutes_counter_by_amount(self, kv: InMemoryKV) -> None:
        """STT-минуты инкрементятся не +1, а +N (минуты)."""
        q = DailyQuota(kv)
        d = await q.check_and_inc(
            user_id=7, metric="stt_server_minutes", is_pro=False, amount=2
        )
        # free = 2 мин/день, поэтому +2 — последняя allowed
        assert d.allowed
        d2 = await q.check_and_inc(
            user_id=7, metric="stt_server_minutes", is_pro=False, amount=1
        )
        assert not d2.allowed

    async def test_unknown_metric_raises(self, kv: InMemoryKV) -> None:
        q = DailyQuota(kv)
        with pytest.raises(ValueError):
            await q.check_and_inc(
                user_id=1, metric="bogus_metric", is_pro=False
            )


# --- Middleware smoke ------------------------------------------------------


class TestMiddleware:
    async def test_path_bucketing(self) -> None:
        from src.web.middleware.rate_limit import _path_bucket

        assert _path_bucket("/api/v1/moments") == "moments"
        assert _path_bucket("/api/v1/moments/42/complete") == "moments"
        assert _path_bucket("/api/v1/agent/ask") == "agent"
        assert _path_bucket("/api/v1/voice/moment") == "voice"
        assert _path_bucket("/api/v1/profile") is None
        assert _path_bucket("/health") is None
