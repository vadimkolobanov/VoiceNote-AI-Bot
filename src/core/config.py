# src/core/config.py
import os
import logging
import secrets
from dotenv import load_dotenv

load_dotenv()

# --- Telegram Bot Token ---
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")

# --- Секретный ключ для JWT ---
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 дней

# --- Admin ID ---
ADMIN_TELEGRAM_ID = int(os.environ.get("ADMIN_TELEGRAM_ID")) if os.environ.get("ADMIN_TELEGRAM_ID") else None

# --- API Keys & IDs ---
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL_NAME = "deepseek-chat"
YANDEX_SPEECHKIT_API_KEY = os.environ.get("YANDEX_SPEECHKIT_API_KEY")
YANDEX_SPEECHKIT_FOLDER_ID = os.environ.get("YANDEX_SPEECHKIT_FOLDER_ID")

# --- Database Configuration ---
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "voice_notes_bot_db")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- Redis Configuration ---
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
REDIS_DB = int(os.environ.get("REDIS_DB", 0))
REDIS_USERNAME = os.environ.get("REDIS_USERNAME")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")

if REDIS_USERNAME and REDIS_PASSWORD:
    REDIS_URL = f"redis://{REDIS_USERNAME}:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
elif REDIS_PASSWORD:
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
else:
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"


# --- Application Settings ---
MAX_NOTES_MVP = 5
MIN_VOICE_DURATION_SEC = 1
NOTES_PER_PAGE = 3
MIN_STT_TEXT_CHARS = 5
MIN_STT_TEXT_WORDS = 1
MAX_DAILY_STT_RECOGNITIONS_MVP = 15
MAX_VOICE_DURATION_SEC = 30

NOTE_CATEGORIES = [
    "Общее", "Работа", "Личное", "Задачи", "Идеи", "Покупки"
]

# --- Ссылки на ресурсы ---
NEWS_CHANNEL_URL = os.environ.get("NEWS_CHANNEL_URL")
CHAT_URL = os.environ.get("CHAT_URL")
CREATOR_CONTACT = os.environ.get("CREATOR_CONTACT", "@useranybody")
DONATION_URL = os.environ.get("DONATION_URL")

# --- Конфигурация для сервиса погоды ---
# User-Agent обязателен для соблюдения политики использования Nominatim (OSM)
APP_USER_AGENT = os.environ.get("APP_USER_AGENT", "VoiceNoteAIBot/1.0 (Contact creator for info)")

# --- Feature Flags (based on API key presence) ---
DEEPSEEK_API_KEY_EXISTS = bool(DEEPSEEK_API_KEY)
YANDEX_STT_CONFIGURED = bool(YANDEX_SPEECHKIT_API_KEY and YANDEX_SPEECHKIT_FOLDER_ID)
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY")
# Флаг для включения/выключения функции погоды
WEATHER_SERVICE_ENABLED = True


def check_initial_config():
    """
    Проверяет наличие ключевых переменных окружения при старте.
    """
    logger = logging.getLogger(__name__)
    if not TG_BOT_TOKEN:
        logger.critical("Переменная окружения TG_BOT_TOKEN не установлена!")
        exit("Критическая ошибка: TG_BOT_TOKEN не найден.")
    if not JWT_SECRET_KEY:
        logger.critical("Переменная окружения JWT_SECRET_KEY не установлена! Это небезопасно.")
        exit("Критическая ошибка: JWT_SECRET_KEY не найден.")
    if not ADMIN_TELEGRAM_ID:
        logger.warning("Переменная окружения ADMIN_TELEGRAM_ID не установлена! Админ-команды будут недоступны.")
    if not DEEPSEEK_API_KEY_EXISTS:
        logger.warning("DEEPSEEK_API_KEY не установлен! Функционал LLM будет недоступен.")
    if not YANDEX_STT_CONFIGURED:
        logger.warning(
            "YANDEX_SPEECHKIT_API_KEY или YANDEX_SPEECHKIT_FOLDER_ID не установлены! "
            "Функционал Яндекс STT будет недоступен."
        )