"""Rate-limit middleware (PRODUCT_PLAN.md §5.1 per-minute limits).

Дневные лимиты (§5.1 моменты/день, агент/день и т.д.) — отдельно через
``DailyQuota`` в самих эндпоинтах, потому что требуют is_pro проверки и
зависят от специфики метрики (STT — минуты, не вызовы).

Ключ лимита — ``(user_id|ip, path_bucket)``. path_bucket — укрупнённая
группа роутов:
    moments   -> POST/GET /api/v1/moments*
    agent     -> POST /api/v1/agent/ask
    voice     -> POST /api/v1/voice/*     (появится в M2-slice-2)
    default   -> всё остальное (не лимитируется)
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from src.services.rate_limit import InMemoryKV, KVStore, RateLimiter
from src.services.security import decode_access_token

logger = logging.getLogger(__name__)

# §5.1 Rate limit (per user): 60/min на /moments, 20/min на /agent/ask,
# 10/min на /voice/recognize.
DEFAULT_LIMITS_PER_MIN = {
    "moments": 60,
    "agent": 20,
    "voice": 10,
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, limiter: RateLimiter) -> None:
        super().__init__(app)
        self._limiter = limiter

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        bucket = _path_bucket(request.url.path)
        if bucket is None:
            return await call_next(request)

        identity = _extract_identity(request)
        key = f"{bucket}:{identity}"
        limit = DEFAULT_LIMITS_PER_MIN[bucket]

        decision = await self._limiter.check(
            key=key, limit=limit, window_sec=60
        )
        if not decision.allowed:
            return _too_many_requests_response(decision)

        response = await call_next(request)
        # Прозрачные rate-limit headers для клиента.
        response.headers["X-RateLimit-Limit"] = str(decision.limit)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        response.headers["X-RateLimit-Reset"] = str(decision.reset_at_unix)
        return response


def _path_bucket(path: str) -> str | None:
    if path.startswith("/api/v1/moments"):
        return "moments"
    if path.startswith("/api/v1/agent/ask"):
        return "agent"
    if path.startswith("/api/v1/voice"):
        return "voice"
    return None


def _extract_identity(request: Request) -> str:
    """Из Bearer-token user_id, иначе client IP."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        user_id = decode_access_token(token)
        if user_id is not None:
            return f"u{user_id}"
    ip = request.client.host if request.client else "unknown"
    return f"ip{ip}"


def _too_many_requests_response(decision) -> Response:
    import json
    body = json.dumps(
        {"error": {"code": "RATE_LIMITED", "message": "Слишком много запросов"}}
    )
    return Response(
        content=body,
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        media_type="application/json",
        headers={
            "X-RateLimit-Limit": str(decision.limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(decision.reset_at_unix),
            "Retry-After": "60",
        },
    )


# --- setup helper ----------------------------------------------------------


def setup_rate_limiting(app: FastAPI, *, kv: KVStore | None = None) -> None:
    """Подключает middleware + хранит KV в ``app.state``.

    В проде передаётся Redis-обёртка. Если не передано — InMemoryKV (ok для
    single-worker dev; для мульти-процесса даст расхождения, см. §18.2 Redis
    graceful degradation).
    """
    store: KVStore = kv or InMemoryKV()
    app.state.rate_limit_kv = store
    limiter = RateLimiter(store)
    app.add_middleware(RateLimitMiddleware, limiter=limiter)
