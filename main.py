# main.py
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from dotenv import load_dotenv

load_dotenv()

from config import (
    TG_BOT_TOKEN, DEEPSEEK_API_KEY_EXISTS, YANDEX_STT_CONFIGURED
)
# Импортируем роутеры из handlers
from handlers import commands as cmd_router
from handlers import notes as notes_router
from handlers import voice as voice_router
from handlers import profile as profile_router  # Предполагаем, что профиль вынесен

import database_setup as db

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s [%(levelname)s] - %(message)s (%(filename)s:%(lineno)d)'
)
logger = logging.getLogger(__name__)  # Основной логгер приложения

# --- Bot Instance ---
if not TG_BOT_TOKEN:
    logger.critical("Переменная окружения TG_BOT_TOKEN не установлена!")
    exit("Критическая ошибка: TG_BOT_TOKEN не найден.")
bot_instance = Bot(token=TG_BOT_TOKEN)


# --- Lifecycle Handlers ---
async def on_startup(dispatcher: Dispatcher):
    """Выполняется при запуске бота."""
    logger.info("Инициализация базы данных...")
    await db.setup_database_on_startup()
    logger.info("Бот запущен и готов к работе!")
    if not DEEPSEEK_API_KEY_EXISTS:
        logger.warning("DEEPSEEK_API_KEY не установлен! Функционал LLM будет недоступен.")
    if not YANDEX_STT_CONFIGURED:
        logger.warning(
            "YANDEX_SPEECHKIT_API_KEY или YANDEX_SPEECHKIT_FOLDER_ID не установлены! "
            "Функционал Яндекс STT будет недоступен."
        )


async def on_shutdown(dispatcher: Dispatcher):
    """Выполняется при остановке бота."""
    logger.info("Остановка бота...")
    await db.shutdown_database_on_shutdown()
    logger.info("Соединения с БД закрыты.")
    # Закрываем сессию бота
    await bot_instance.session.close()
    logger.info("Сессия бота закрыта. Бот остановлен.")


async def main():
    """Основная функция для настройки и запуска бота."""

    storage = MemoryStorage()  # Для FSM
    dp = Dispatcher(storage=storage)

    # Подключаем роутеры из пакета handlers
    dp.include_router(cmd_router.router)
    dp.include_router(notes_router.router)
    dp.include_router(voice_router.router)
    dp.include_router(profile_router.router)  # Роутер для профиля

    # Регистрация lifecycle handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Запуск polling...")
    try:
        # Передаем экземпляр бота в start_polling
        await dp.start_polling(bot_instance, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.critical(f"Ошибка при запуске polling: {e}", exc_info=True)
    finally:
        # Это уже делается в on_shutdown, но для надежности можно и здесь, если on_shutdown не вызовется
        if bot_instance.session and not bot_instance.session.closed:
            await bot_instance.session.close()
        logger.info("Polling завершен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Принудительная остановка бота (KeyboardInterrupt/SystemExit).")
    except Exception as e:
        # Этот блок может не успеть сработать, если ошибка в самом asyncio.run()
        logger.critical(f"Критическая ошибка на верхнем уровне выполнения: {e}", exc_info=True)