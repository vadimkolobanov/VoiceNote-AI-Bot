# src/main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
import uvicorn

# --- 1. Импорты из папки `core` ---
# Это ядро нашего приложения, отсюда импортируем первыми.
from core.logging_setup import setup_logging
from core.config import TG_BOT_TOKEN, check_initial_config

# --- 2. Импорты из папки `database` ---
# Функции для инициализации и закрытия соединений с БД.
from database.core import setup_database_on_startup, shutdown_database_on_shutdown

# --- 3. Импорты из папки `services` ---
# Планировщик, который нужно настроить при старте.
from services.scheduler import scheduler, load_reminders_on_startup, setup_daily_jobs

# --- 4. Импорты из папки `bot` ---
# Главный диспетчер, который собирает все роутеры.
from bot.dispatcher import get_dispatcher

# --- 5. Импорты из папки `web` ---
# Приложение FastAPI для вебхука Алисы.
from web.app import get_fastapi_app

# --- Начальная настройка ---
# Настраиваем логирование в самом начале, чтобы видеть все последующие шаги.
setup_logging()
# Проверяем наличие критически важных переменных окружения.
check_initial_config()

# Получаем главный логгер.
logger = logging.getLogger(__name__)

# --- Основные экземпляры ---
# Создаем экземпляр бота.
bot_instance = Bot(token=TG_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
# Создаем и настраиваем диспетчер со всеми роутерами.
dp = get_dispatcher()
# Создаем приложение FastAPI и передаем ему экземпляр бота.
fastapi_app = get_fastapi_app(bot_instance)


# --- Функции жизненного цикла ---
async def on_startup(bot: Bot, dispatcher: Dispatcher):
    """Выполняется при старте бота."""
    logger.info("Starting up...")

    # Удаляем вебхук, если он был установлен, и работаем в режиме поллинга.
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook deleted, starting in polling mode.")

    # Инициализируем базу данных.
    await setup_database_on_startup()

    # Запускаем планировщик.
    logger.info("Starting scheduler...")
    await load_reminders_on_startup(bot)
    await setup_daily_jobs(bot)
    scheduler.start()
    logger.info("Scheduler started.")

    logger.info("Bot has been started successfully!")


async def on_shutdown(bot: Bot, dispatcher: Dispatcher):
    """Выполняется при остановке бота."""
    logger.info("Shutting down...")

    # Останавливаем планировщик.
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")

    # Закрываем соединения с базой данных.
    await shutdown_database_on_shutdown()

    # Закрываем сессию бота.
    await bot.session.close()

    logger.info("Bot has been shut down gracefully.")


# --- Точка входа ---
async def main():
    """Главная асинхронная функция для запуска всего приложения."""
    # Регистрируем функции жизненного цикла в диспетчере.
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Конфигурация для веб-сервера uvicorn.
    uvicorn_config = uvicorn.Config(
        app=fastapi_app,
        host="0.0.0.0",  # Слушаем на всех интерфейсах
        port=8000,
        log_config=None,  # Используем нашу настройку логирования
    )
    server = uvicorn.Server(uvicorn_config)

    logger.info("Launching Bot (polling) and Web Server (uvicorn)...")

    # Запускаем бота и веб-сервер параллельно.
    await asyncio.gather(
        dp.start_polling(bot_instance),
        server.serve()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application stopped by user.")