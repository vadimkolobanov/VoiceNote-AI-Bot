# src/bot/dispatcher.py
#
# Telegram-бот понижен до legacy-канала ввода без экранов (см. docs/PRODUCT_PLAN.md §16).
# Старые модули (notes/habits/birthdays/shopping_list/profile/admin/onboarding) удалены.
# В M2 здесь появятся только handlers для capture (voice.py, text.py, forward.py)
# и notifications.py для inline-кнопок на push-уведомлениях.
from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from src.core.config import REDIS_URL


def get_dispatcher() -> Dispatcher:
    """Возвращает диспетчер-заглушку без роутеров. Capture-handlers добавятся в M2."""
    storage = RedisStorage.from_url(REDIS_URL)
    dp = Dispatcher(storage=storage)
    return dp
