# main.py
import asyncio
import logging
import os
# --- НОВЫЕ ИМПОРТЫ ---
from logging.handlers import RotatingFileHandler
from logtail import LogtailHandler

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

# --- НОВЫЙ БЛОК КОНФИГУРАЦИИ ---
# Загружаем переменные для Logtail из окружения
LOGTAIL_SOURCE_TOKEN = os.environ.get("LOGTAIL_SOURCE_TOKEN")
LOGTAIL_HOST = os.environ.get("LOGTAIL_HOST")

# --- ПРОФЕССИОНАЛЬНАЯ НАСТРОЙКА ЛОГИРОВАНИЯ ---
# 1. Создаем "корневой" логгер. Не используем basicConfig, чтобы иметь полный контроль.
logger = logging.getLogger()
logger.setLevel(logging.INFO) # Устанавливаем минимальный уровень для ВСЕХ обработчиков.

# 2. Убираем все стандартные обработчики, чтобы избежать дублирования
if logger.hasHandlers():
    logger.handlers.clear()

# 3. Настраиваем обработчик для вывода в консоль (удобно для локальной разработки)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s [%(levelname)s] - %(message)s'))
logger.addHandler(console_handler)

# 4. Настраиваем обработчик для записи в файл (надежный бэкап)
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
file_handler = RotatingFileHandler(
    os.path.join(log_dir, 'bot.log'),
    maxBytes=5*1024*1024,
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s [%(levelname)s] - %(message)s (%(filename)s:%(lineno)d)'))
logger.addHandler(file_handler)

# 5. Настраиваем обработчик для отправки логов в Logtail
if LOGTAIL_SOURCE_TOKEN and LOGTAIL_HOST:
    logtail_handler = LogtailHandler(source_token=LOGTAIL_SOURCE_TOKEN, host=LOGTAIL_HOST)
    logger.addHandler(logtail_handler)
    logger.info("Logtail handler configured successfully.")
else:
    logger.warning("Logtail configuration not found. Logs will not be sent to Logtail.")

# 6. Уменьшаем "шум" от сторонних библиотек
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


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
    await load_reminders_on_startup(bot)
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