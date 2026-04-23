"""DeepSeek-V3 провайдер (primary для §6.0 facet_extract, digest_write, ...).

Вызывает OpenAI-compatible /v1/chat/completions endpoint. Ключ и URL — из
``src.core.config``. На сетевых/5xx ошибках кидает ``ProviderError`` —
роутер переходит к следующему провайдеру.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import aiohttp

from src.core.config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME

from ..base import LLMResponse, ProviderError

logger = logging.getLogger(__name__)

# Защита от залипания: 30 сек — верхняя граница с ретраями у fallback.
DEFAULT_TIMEOUT_SEC = 30


class DeepSeekProvider:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    ) -> None:
        self._api_key = api_key or DEEPSEEK_API_KEY
        self._api_url = api_url or DEEPSEEK_API_URL
        self._timeout = aiohttp.ClientTimeout(total=timeout_sec)

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
    ) -> LLMResponse:
        if not self._api_key or not self._api_url:
            raise ProviderError("DeepSeek API not configured (missing API key or URL)")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model or DEEPSEEK_MODEL_NAME,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        started = time.monotonic()
        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.post(
                    self._api_url, headers=headers, json=payload
                ) as resp:
                    if resp.status >= 500:
                        text = await resp.text()
                        raise ProviderError(
                            f"DeepSeek 5xx: {resp.status} {text[:200]}"
                        )
                    if resp.status >= 400:
                        text = await resp.text()
                        # 4xx — не ретраим (некорректный запрос), но с точки
                        # зрения роутера это всё равно ProviderError, чтобы
                        # fallback отработал.
                        raise ProviderError(
                            f"DeepSeek {resp.status}: {text[:200]}"
                        )
                    data = await resp.json()
        except aiohttp.ClientError as exc:
            raise ProviderError(f"DeepSeek network error: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ProviderError(f"DeepSeek bad JSON: {exc}") from exc

        latency_ms = int((time.monotonic() - started) * 1000)

        try:
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {}) or {}
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"DeepSeek malformed response: {exc}") from exc

        return LLMResponse(
            content=content,
            provider="deepseek",
            model=payload["model"],
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            latency_ms=latency_ms,
            raw=data,
        )
