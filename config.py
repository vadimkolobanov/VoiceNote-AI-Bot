# config.py
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# --- Telegram Bot Token ---
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")

# --- API Keys & IDs ---
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
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
MAX_NOTES_MVP = 5  # Лимит заметок на пользователя в MVP
MIN_VOICE_DURATION_SEC = 1  # Минимальная длительность голосового сообщения
NOTES_PER_PAGE = 3 # Количество заметок на одной странице при пагинации
MIN_STT_TEXT_CHARS = 5 # Минимальная длина текста после STT для обработки
MIN_STT_TEXT_WORDS = 1 # Минимальное кол-во слов после STT для обработки
MAX_DAILY_STT_RECOGNITIONS_MVP = 2

# --- Feature Flags (based on API key presence) ---
DEEPSEEK_API_KEY_EXISTS = bool(DEEPSEEK_API_KEY)
YANDEX_STT_CONFIGURED = bool(YANDEX_SPEECHKIT_API_KEY and YANDEX_SPEECHKIT_FOLDER_ID)


# --- Logging Configuration ---

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Глобальный логгер для config, если нужен