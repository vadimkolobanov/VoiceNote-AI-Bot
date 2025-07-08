# src/bot/dispatcher.py
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Импортируем "главные" роутеры из каждого модуля
from .modules.admin import router as admin_router
from .modules.birthdays import router as birthdays_router
from .modules.common import router as common_router
from .modules.notes import router as notes_router
from .modules.profile import router as profile_router


def get_dispatcher() -> Dispatcher:
    """
    Создает, настраивает и возвращает корневой экземпляр Dispatcher.
    """
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # --- Порядок подключения роутеров (очень важен!) ---
    #
    # 1. Админские команды. Они должны иметь высший приоритет, чтобы
    #    перехватывать команды до того, как их обработают другие хендлеры.
    dp.include_router(admin_router)

    # 2. Модули с основной функциональностью, которые срабатывают
    #    по конкретным колбэкам или командам.
    dp.include_router(profile_router)
    dp.include_router(birthdays_router)

    # 3. Модуль заметок. Он содержит все свои хендлеры, собранные
    #    в правильном порядке внутри своего __init__.py.
    dp.include_router(notes_router)

    # 4. Общие команды (/start, /help) и колбэки (go_to_main_menu).
    #    Они должны иметь самый низкий приоритет, чтобы не мешать
    #    FSM-состояниям и другим командам.
    dp.include_router(common_router)

    return dp