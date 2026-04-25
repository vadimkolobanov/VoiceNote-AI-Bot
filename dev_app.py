"""Dev-only ASGI factory: подаёт ``get_fastapi_app(bot)`` с fake-ботом.

Запуск:
    .venv/Scripts/python.exe -m uvicorn dev_app:app --host 127.0.0.1 --port 8765

Используется ТОЛЬКО для локального smoke-тестирования v1 endpoints
(auth/moments/etc.). В прод поднимается через src/main.py с реальным ботом.
"""
from __future__ import annotations

import os

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from src.web.app import get_fastapi_app

_token = os.environ.get("TG_BOT_TOKEN") or "123:fake_for_dev_only"
_bot = Bot(token=_token, default=DefaultBotProperties(parse_mode="HTML"))

app = get_fastapi_app(_bot)
