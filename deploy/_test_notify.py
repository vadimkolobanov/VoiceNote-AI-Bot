import asyncio
import sys

sys.path.insert(0, "/opt/methodex")

from dotenv import load_dotenv

load_dotenv("/opt/methodex/.env")

from src.services.admin_notify import notify_admin

asyncio.run(
    notify_admin(
        "<b>🟢 admin_notify подключён</b>\n\n"
        "Если видишь это — Telegram-канал к боту работает. "
        "Все feedback и регистрации теперь будут приходить сюда."
    )
)
print("sent")
