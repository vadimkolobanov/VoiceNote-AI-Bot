# src/bot/dispatcher.py
from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from src.core.config import REDIS_URL

# Импортируем "главные" роутеры из каждого модуля
from .modules.admin import router as admin_router
from .modules.onboarding import router as onboarding_router
from .modules.birthdays import router as birthdays_router
from .modules.habits import router as habits_router # <-- НОВЫЙ ИМПОРТ
from .modules.common import router as common_router
from .modules.notes import router as notes_router
from .modules.profile import router as profile_router


def get_dispatcher() -> Dispatcher:
    """
    Создает, настраивает и возвращает корневой экземпляр Dispatcher.
    """
    storage = RedisStorage.from_url(REDIS_URL)
    dp = Dispatcher(storage=storage)

    # --- Порядок подключения роутеров (очень важен!) ---
    #
    # 1. Админские команды. Они должны иметь высший приоритет.
    dp.include_router(admin_router)

    # 2. Обучение. Оно должно перехватывать ввод пользователя,
    #    если он находится в состоянии обучения, ДО основной логики.
    dp.include_router(onboarding_router)

    # 3. Модули с основной функциональностью, которые срабатывают
    #    по конкретным колбэкам или командам.
    dp.include_router(profile_router)
    dp.include_router(birthdays_router)
    dp.include_router(habits_router) # <-- ДОБАВЛЕНО ЗДЕСЬ

    # 4. Модуль заметок. Он содержит все свои хендлеры, собранные
    #    в правильном порядке внутри своего __init__.py.
    #    Он должен идти ПОСЛЕ обучения, чтобы не перехватывать сообщения.
    dp.include_router(notes_router)

    # 5. Общие команды (/start, /help) и колбэки (go_to_main_menu).
    #    Они должны иметь самый низкий приоритет, чтобы не мешать
    #    FSM-состояниям и другим командам.
    dp.include_router(common_router)

    return dp