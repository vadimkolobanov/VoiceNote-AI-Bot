# config.py
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# --- Telegram Bot Token ---
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")

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


# --- Application Settings ---
MAX_NOTES_MVP = 5
MIN_VOICE_DURATION_SEC = 1
NOTES_PER_PAGE = 3
MIN_STT_TEXT_CHARS = 5
MIN_STT_TEXT_WORDS = 1
MAX_DAILY_STT_RECOGNITIONS_MVP = 15

NOTE_CATEGORIES = [
    "Общее", "Работа", "Личное", "Задачи", "Идеи", "Покупки"
]

# --- Ссылки на ресурсы ---
NEWS_CHANNEL_URL = os.environ.get("NEWS_CHANNEL_URL")
CHAT_URL = os.environ.get("CHAT_URL")
CREATOR_CONTACT = os.environ.get("CREATOR_CONTACT", "@useranybody")
# --- ДОБАВЛЕНО ---
DONATION_URL = os.environ.get("DONATION_URL") # Ссылка на ЮMoney


# --- Feature Flags (based on API key presence) ---
DEEPSEEK_API_KEY_EXISTS = bool(DEEPSEEK_API_KEY)
YANDEX_STT_CONFIGURED = bool(YANDEX_SPEECHKIT_API_KEY and YANDEX_SPEECHKIT_FOLDER_ID)


# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if not ADMIN_TELEGRAM_ID:
    logger.warning("Переменная окружения ADMIN_TELEGRAM_ID не установлена! Админ-команды будут недоступны.")