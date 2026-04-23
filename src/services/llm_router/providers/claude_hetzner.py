"""Claude Haiku 4.5 через свой Hetzner-прокси (§6.0 agent_ask).

В M1/M2 — stub: провайдер возвращает ProviderError, роутер в M3
переключится на fallback (DeepSeek). Реальная реализация — в M3, когда
встанет Caddy на Hetzner и ``ANTHROPIC_BASE_URL`` будет в env.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from ..base import LLMResponse, ProviderError


class ClaudeHetznerProvider:
    """Пока не сконфигурирован — всегда кидает ProviderError.

    Тесты должны проверять fallback-поведение роутера именно через этот
    класс: он гарантированно не ходит в сеть.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL")

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
        # M3 todo: Anthropic Messages API через self._base_url.
        # Для M2 явный фейл — роутер уйдёт в fallback.
        raise ProviderError(
            "ClaudeHetznerProvider not yet configured "
            "(Hetzner proxy lands in M3, see PRODUCT_PLAN.md §14.M3)"
        )
