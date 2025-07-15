# src/main.py
import asyncio
import logging
import os
import sys

import uvicorn
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

# --- Setup ---
# Добавляем корень проекта в системный путь
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..')
sys.path.insert(0, project_root)

# Явно устанавливаем переменную окружения для учетных данных Google
service_account_key_path = os.path.join(project_root, 'firebase-service-account.json')
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = service_account_key_path

# Импортируем модули ПОСЛЕ установки переменной окружения
from src.core.config import check_initial_config, TG_BOT_TOKEN
from src.core.logging_setup import setup_logging
from src.database.connection import init_db, close_db_pool
from src.bot.dispatcher import get_dispatcher
from src.services.scheduler import scheduler, load_reminders_on_startup, setup_daily_jobs
from src.services.push_service import initialize_firebase  # <-- ИМПОРТИРУЕМ НАШУ ФУНКЦИЮ
from src.web.app import get_fastapi_app

setup_logging()
check_initial_config()
logger = logging.getLogger(__name__)


# --- Startup/Shutdown Events ---
async def on_startup(bot: Bot):
    """Выполняется при запуске бота."""
    logger.info("Starting bot...")

    # Инициализируем Firebase SDK
    initialize_firebase()

    await bot.delete_webhook(drop_pending_updates=True)
    await init_db()

    logger.info("Starting scheduler...")
    await load_reminders_on_startup(bot)
    await setup_daily_jobs(bot)
    scheduler.start()

    logger.info("Scheduler started.")
    logger.info("Bot is running!")


async def on_shutdown(bot: Bot):
    """Выполняется при остановке бота."""
    logger.info("Stopping bot...")
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")

    await close_db_pool()

    if bot and bot.session and not bot.session.is_closed():
        await bot.session.close()

    logger.info("Bot stopped.")


# --- Main Execution ---
async def main():
    """Главная функция запуска приложения."""
    bot = Bot(token=TG_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = get_dispatcher()

    fastapi_app = get_fastapi_app(bot)
    fastapi_app.state.bot = bot

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    uvicorn_config = uvicorn.Config(
        app=fastapi_app,
        host="0.0.0.0",
        port=8000,
        log_config=None
    )
    server = uvicorn.Server(uvicorn_config)

    try:
        logger.info("Launching Bot Polling and Web Server...")
        await asyncio.gather(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
            server.serve()
        )
    finally:
        await on_shutdown(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot execution stopped manually.")