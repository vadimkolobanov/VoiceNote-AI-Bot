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

# Firebase Admin: указываем путь к service account, чтобы push_service мог
# инициализироваться на dev-сервере (в проде это делает src/main.py).
_project_root = os.path.dirname(os.path.abspath(__file__))
_fb_creds = os.path.join(_project_root, "firebase-service-account.json")
if os.path.exists(_fb_creds):
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", _fb_creds)

from src.services.push_service import initialize_firebase  # noqa: E402
from src.web.app import get_fastapi_app  # noqa: E402

initialize_firebase()

_token = os.environ.get("TG_BOT_TOKEN") or "123:fake_for_dev_only"
_bot = Bot(token=_token, default=DefaultBotProperties(parse_mode="HTML"))

app = get_fastapi_app(_bot)
