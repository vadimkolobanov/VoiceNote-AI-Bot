# main.py
import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler
from logtail import LogtailHandler

import uvicorn
# --- ИЗМЕНЕНИЕ: Добавляем импорт ---
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
# --------------------------------
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
    birthdays as birthdays_router,
    text_processor as text_router
)
import database_setup as db
from services.scheduler import scheduler, load_reminders_on_startup, setup_daily_jobs
from alice_webhook import app as fastapi_app, set_bot_instance

# --- ПРОФЕССИОНАЛЬНАЯ НАСТРОЙКА ЛОГИРОВАНИЯ ---
# (Ваш блок настройки логирования остается здесь без изменений)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s [%(levelname)s] - %(message)s'))
logger.addHandler(console_handler)
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
file_handler = RotatingFileHandler(
    os.path.join(log_dir, 'bot.log'), maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8'
)
file_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s [%(levelname)s] - %(message)s (%(filename)s:%(lineno)d)'))
logger.addHandler(file_handler)
LOGTAIL_SOURCE_TOKEN = os.environ.get("LOGTAIL_SOURCE_TOKEN")
LOGTAIL_HOST = os.environ.get("LOGTAIL_HOST")
if LOGTAIL_SOURCE_TOKEN and LOGTAIL_HOST:
    logtail_handler = LogtailHandler(source_token=LOGTAIL_SOURCE_TOKEN, host=LOGTAIL_HOST)
    logger.addHandler(logtail_handler)
    logger.info("Logtail handler configured successfully.")
else:
    logger.warning("Logtail configuration not found. Logs will not be sent to Logtail.")
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)

# --- Bot Instance ---
if not TG_BOT_TOKEN:
    logger.critical("Переменная окружения TG_BOT_TOKEN не установлена!")
    exit("Критическая ошибка: TG_BOT_TOKEN не найден.")

# --- ИЗМЕНЕНИЕ: Новый способ инициализации ---
bot_instance = Bot(token=TG_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))


# -------------------------------------------


# --- Lifecycle Handlers ---
async def on_startup(bot: Bot):
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Вебхук успешно удален. Начинаем работу в режиме polling")
    except Exception as e:
        logger.error(f"Ошибка при удалении вебхука: {e}")

    logger.info("Инициализация базы данных...")
    await db.setup_database_on_startup()

    logger.info("Запуск планировщика задач (APScheduler)...")
    scheduler.configure(job_defaults={'kwargs': {'bot': bot}})
    await load_reminders_on_startup(bot)
    await setup_daily_jobs(bot)
    scheduler.start()
    logger.info("Планировщик запущен, все задачи загружены.")

    set_bot_instance(bot)

    logger.info("Бот запущен и готов к работе!")
    if not DEEPSEEK_API_KEY_EXISTS:
        logger.warning("DEEPSEEK_API_KEY не установлен! Функционал LLM будет недоступен.")
    if not YANDEX_STT_CONFIGURED:
        logger.warning(
            "YANDEX_SPEECHKIT_API_KEY или YANDEX_SPEECHKIT_FOLDER_ID не установлены! "
            "Функционал Яндекс STT будет недоступен."
        )


async def on_shutdown():
    logger.info("Остановка планировщика...")
    scheduler.shutdown(wait=False)
    logger.info("Планировщик остановлен.")

    logger.info("Остановка бота...")
    await db.shutdown_database_on_shutdown()
    logger.info("Соединения с БД закрыты.")

    # Проверяем, что сессия существует и не закрыта, перед закрытием
    if bot_instance.session and not bot_instance.session.closed:
        await bot_instance.session.close()
    logger.info("Сессия бота закрыта. Бот остановлен.")


async def main():
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.startup.register(on_startup)

    # Роутеры
    dp.include_router(admin_router.router)
    dp.include_router(info_router.router)
    dp.include_router(birthdays_router.router)
    dp.include_router(settings_router.router)
    dp.include_router(profile_router.router)
    dp.include_router(notes_router.router)
    dp.include_router(voice_router.router)
    dp.include_router(text_router.router)
    dp.include_router(cmd_router.router)

    # Настраиваем Uvicorn
    uvicorn_config = uvicorn.Config(
        app=fastapi_app,
        host="0.0.0.0",
        port=8000,
        log_config=None,
    )
    server = uvicorn.Server(uvicorn_config)

    try:
        logger.info("Запуск Telegram-бота и веб-сервера для Алисы...")
        await asyncio.gather(
            dp.start_polling(bot_instance, allowed_updates=dp.resolve_used_update_types()),
            server.serve()
        )
    finally:
        await on_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Принудительная остановка бота (KeyboardInterrupt/SystemExit).")
    except Exception as e:
        logger.critical(f"Критическая ошибка на верхнем уровне выполнения: {e}", exc_info=True)