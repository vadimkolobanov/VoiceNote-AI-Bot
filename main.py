# main.py
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

from config import TG_BOT_TOKEN, DEEPSEEK_API_KEY_EXISTS, YANDEX_STT_CONFIGURED
from handlers import (
    commands as cmd_router,
    notes as notes_router,
    voice as voice_router,
    profile as profile_router,
    settings as settings_router,
    admin as admin_router,
    info as info_router,
    birthdays as birthdays_router
)
import database_setup as db
from services.scheduler import scheduler, load_reminders_on_startup, setup_daily_jobs

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s [%(levelname)s] - %(message)s (%(filename)s:%(lineno)d)'
)
logger = logging.getLogger(__name__)
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# --- Bot Instance ---
if not TG_BOT_TOKEN:
    logger.critical("Переменная окружения TG_BOT_TOKEN не установлена!")
    exit("Критическая ошибка: TG_BOT_TOKEN не найден.")
bot_instance = Bot(token=TG_BOT_TOKEN)


# --- Lifecycle Handlers ---
async def on_startup(dispatcher: Dispatcher, bot: Bot):
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Вебхук успешно удален. Начинаем работу в режиме polling")
    except Exception as e:
        logger.error(f"Ошибка при удалении вебхука: {e}")

    logger.info("Инициализация базы данных...")
    await db.setup_database_on_startup()

    logger.info("Запуск планировщика задач (APScheduler)...")
    scheduler.configure(job_defaults={'kwargs': {'bot': bot}})

    # 1. Загружаем разовые напоминания по заметкам
    await load_reminders_on_startup(bot)

    # 2. Устанавливаем повторяющиеся ежедневные задачи
    await setup_daily_jobs(bot)

    scheduler.start()
    logger.info("Планировщик запущен, все задачи загружены.")

    logger.info("Бот запущен и готов к работе!")
    if not DEEPSEEK_API_KEY_EXISTS:
        logger.warning("DEEPSEEK_API_KEY не установлен! Функционал LLM будет недоступен.")
    if not YANDEX_STT_CONFIGURED:
        logger.warning(
            "YANDEX_SPEECHKIT_API_KEY или YANDEX_SPEECHKIT_FOLDER_ID не установлены! "
            "Функционал Яндекс STT будет недоступен."
        )


async def on_shutdown(dispatcher: Dispatcher):
    logger.info("Остановка планировщика...")
    scheduler.shutdown(wait=False)
    logger.info("Планировщик остановлен.")

    logger.info("Остановка бота...")
    await db.shutdown_database_on_shutdown()
    logger.info("Соединения с БД закрыты.")

    await bot_instance.session.close()
    logger.info("Сессия бота закрыта. Бот остановлен.")


async def main():
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(admin_router.router)
    dp.include_router(info_router.router)
    dp.include_router(birthdays_router.router)
    dp.include_router(settings_router.router)
    dp.include_router(profile_router.router)
    dp.include_router(notes_router.router)
    dp.include_router(voice_router.router)
    dp.include_router(cmd_router.router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Запуск polling...")
    try:
        if await bot_instance.get_webhook_info():
            logger.warning("Обнаружен активный вебхук! Принудительное удаление...")
            await bot_instance.delete_webhook()

        await dp.start_polling(bot_instance, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.critical(f"Ошибка при запуске polling: {e}", exc_info=True)
    finally:
        if bot_instance.session and not bot_instance.session.closed:
            await bot_instance.session.close()
        logger.info("Polling завершен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Принудительная остановка бота (KeyboardInterrupt/SystemExit).")
    except Exception as e:
        logger.critical(f"Критическая ошибка на верхнем уровне выполнения: {e}", exc_info=True)