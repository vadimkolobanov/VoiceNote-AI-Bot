"""Rate-limiter + daily quotas (PRODUCT_PLAN.md §5.1, §18.2).

Два слоя:

1. ``RateLimiter.check(key, limit, window_sec)`` — запрос/мин (sliding-fixed).
   Используется в FastAPI-middleware для /moments, /agent/ask, /voice/recognize.
2. ``DailyQuota.check_and_inc(user_id, metric)`` — дневные лимиты (моменты,
   минуты STT, вопросы к агенту; reset в 00:00 UTC).

Бэкенд — Redis по плану, но приложение должно работать и без Redis
(«graceful degradation», §3). Если Redis недоступен — лимитер даёт
«разрешено», но пишет warning раз в минуту.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class KVStore(Protocol):
    """Интерфейс Redis-совместимого KV. Чтобы тесты могли подсунуть in-memory."""

    async def incr(self, key: str) -> int: ...
    async def expire(self, key: str, seconds: int) -> None: ...
    async def get(self, key: str) -> Optional[str]: ...


class InMemoryKV:
    """Локальный KV для тестов и для случая отсутствия Redis.

    Не потокобезопасен для мульти-процессного деплоя — значит, лимит
    в разных воркерах будет считаться отдельно. В проде надо Redis.
    """

    def __init__(self) -> None:
        self._store: dict[str, int] = {}
        self._expires: dict[str, float] = {}

    def _evict_expired(self) -> None:
        now = time.time()
        stale = [k for k, exp in self._expires.items() if exp < now]
        for k in stale:
            self._store.pop(k, None)
            self._expires.pop(k, None)

    async def incr(self, key: str) -> int:
        self._evict_expired()
        v = self._store.get(key, 0) + 1
        self._store[key] = v
        return v

    async def expire(self, key: str, seconds: int) -> None:
        self._expires[key] = time.time() + seconds

    async def get(self, key: str) -> Optional[str]:
        self._evict_expired()
        v = self._store.get(key)
        return None if v is None else str(v)


@dataclass(slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    limit: int
    reset_at_unix: int


class RateLimiter:
    """Фиксированное окно. Не «sliding», но достаточно для наших уровней."""

    def __init__(self, kv: KVStore) -> None:
        self._kv = kv

    async def check(
        self,
        *,
        key: str,
        limit: int,
        window_sec: int,
    ) -> RateLimitDecision:
        bucket = int(time.time() // window_sec)
        full_key = f"rl:{key}:{bucket}"
        try:
            count = await self._kv.incr(full_key)
            if count == 1:
                await self._kv.expire(full_key, window_sec)
        except Exception as exc:  # noqa: BLE001 — KV не должен ронять запрос
            logger.warning("RateLimiter KV failure (allowing request): %s", exc)
            return RateLimitDecision(
                allowed=True, remaining=limit, limit=limit,
                reset_at_unix=int(time.time() + window_sec),
            )
        reset_at = (bucket + 1) * window_sec
        remaining = max(0, limit - count)
        return RateLimitDecision(
            allowed=count <= limit,
            remaining=remaining,
            limit=limit,
            reset_at_unix=reset_at,
        )


# --- Daily quotas (§5.1 table) ---------------------------------------------


@dataclass(frozen=True)
class QuotaSpec:
    free_per_day: int
    pro_per_day: int


# §5.1 таблица. Значения не trivially превращаются в сек-окно — нужен
# отдельный механизм дневных счётчиков.
DAILY_QUOTAS: dict[str, QuotaSpec] = {
    "moments_created": QuotaSpec(free_per_day=30, pro_per_day=200),
    "agent_questions": QuotaSpec(free_per_day=0, pro_per_day=20),
    "stt_server_minutes": QuotaSpec(free_per_day=2, pro_per_day=30),
}


class DailyQuota:
    """Reset в 00:00 UTC. Ключ: `quota:{metric}:{user_id}:{YYYYMMDD}`."""

    def __init__(self, kv: KVStore) -> None:
        self._kv = kv

    async def check_and_inc(
        self,
        *,
        user_id: int,
        metric: str,
        is_pro: bool,
        amount: int = 1,
    ) -> RateLimitDecision:
        spec = DAILY_QUOTAS.get(metric)
        if spec is None:
            raise ValueError(f"Unknown daily quota metric: {metric}")
        limit = spec.pro_per_day if is_pro else spec.free_per_day

        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        key = f"quota:{metric}:{user_id}:{day}"

        try:
            # incr идёт на `amount`, а не всегда +1 (для STT-минут это важно).
            new_value = 0
            for _ in range(amount):
                new_value = await self._kv.incr(key)
            # Срок жизни 48 часов — с запасом на смену суток в часовых поясах.
            await self._kv.expire(key, 48 * 3600)
        except Exception as exc:  # noqa: BLE001
            logger.warning("DailyQuota KV failure (allowing request): %s", exc)
            return RateLimitDecision(
                allowed=True, remaining=limit, limit=limit,
                reset_at_unix=_next_midnight_utc(),
            )
        remaining = max(0, limit - new_value)
        return RateLimitDecision(
            allowed=new_value <= limit,
            remaining=remaining,
            limit=limit,
            reset_at_unix=_next_midnight_utc(),
        )


def _next_midnight_utc() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = tomorrow.replace(day=tomorrow.day) + _one_day()
    return int(tomorrow.timestamp())


def _one_day():
    from datetime import timedelta
    return timedelta(days=1)
