# src/core/logging_setup.py
import logging
import os
from logging.handlers import RotatingFileHandler
from logtail import LogtailHandler
from dotenv import load_dotenv

load_dotenv()

def setup_logging():
    """
    Настраивает систему логирования для проекта.
    Включает обработчики для консоли, файла и опционально для Logtail.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Очищаем существующих обработчиков, чтобы избежать дублирования
    if logger.hasHandlers():
        logger.handlers.clear()

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s [%(levelname)s] - %(message)s'))
    logger.addHandler(console_handler)

    # File Handler
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'bot.log'), maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s [%(levelname)s] - %(message)s (%(filename)s:%(lineno)d)'))
    logger.addHandler(file_handler)

    # Logtail Handler (опционально)
    LOGTAIL_SOURCE_TOKEN = os.environ.get("LOGTAIL_SOURCE_TOKEN")
    LOGTAIL_HOST = os.environ.get("LOGTAIL_HOST")

    if LOGTAIL_SOURCE_TOKEN and LOGTAIL_HOST:
        logtail_handler = LogtailHandler(source_token=LOGTAIL_SOURCE_TOKEN, host=LOGTAIL_HOST)
        logger.addHandler(logtail_handler)
        logger.info("Logtail handler configured successfully.")
    else:
        logger.warning("Logtail configuration not found. Logs will not be sent to Logtail.")

    # Приглушаем слишком "шумные" сторонние библиотеки
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)