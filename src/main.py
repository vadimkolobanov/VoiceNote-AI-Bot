# src/main.py
import asyncio
import logging
import uvicorn
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from src.core.config import check_initial_config, TG_BOT_TOKEN
from src.core.logging_setup import setup_logging
from src.database.connection import init_db, close_db_pool
from src.bot.dispatcher import get_dispatcher
from src.services.scheduler import scheduler, load_reminders_on_startup, setup_daily_jobs
from src.web.app import get_fastapi_app

# --- Setup ---
setup_logging()
check_initial_config()
logger = logging.getLogger(__name__)


# --- Startup/Shutdown Events ---
async def on_startup(bot: Bot):
    """Выполняется при запуске бота."""
    logger.info("Starting bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await init_db()

    logger.info("Starting scheduler...")
    # --- ИСПРАВЛЕНИЕ ОШИБКИ 1 ---
    # Передаем kwargs с ботом в функции, которые добавляют задачи.
    # Метод modify_job_defaults удален в APScheduler 4.x
    await load_reminders_on_startup(bot)
    await setup_daily_jobs(bot)
    scheduler.start()
    # ---------------------------

    logger.info("Scheduler started.")
    logger.info("Bot is running!")


async def on_shutdown(bot: Bot):
    """Выполняется при остановке бота."""
    logger.info("Stopping bot...")
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")

    await close_db_pool()

    # --- ИСПРАВЛЕНИЕ ОШИБКИ 2 ---
    # В Aiogram 3.x проверка сессии изменилась
    if bot and bot.session and not bot.session.is_closed():
        await bot.session.close()
    # ---------------------------
    logger.info("Bot stopped.")


# --- Main Execution ---
async def main():
    """Главная функция запуска приложения."""
    bot = Bot(token=TG_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = get_dispatcher()

    fastapi_app = get_fastapi_app(bot)

    # Сохраняем экземпляр бота в состояние приложения FastAPI
    fastapi_app.state.bot = bot

    # Регистрируем функции запуска и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Конфигурация веб-сервера Uvicorn
    uvicorn_config = uvicorn.Config(
        app=fastapi_app,
        host="0.0.0.0",
        port=8000,
        log_config=None
    )
    server = uvicorn.Server(uvicorn_config)

    try:
        logger.info("Launching Bot Polling and Web Server...")
        # Запускаем одновременно и поллинг бота, и веб-сервер
        await asyncio.gather(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
            server.serve()
        )
    finally:
        # Корректно завершаем работу при остановке
        await on_shutdown(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot execution stopped manually.")