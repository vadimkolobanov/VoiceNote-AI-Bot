# src/database/core.py
import logging
import asyncpg
from ..core.config import DATABASE_URL

logger = logging.getLogger(__name__)

# Все DDL-запросы для создания и обновления схемы БД
CREATE_AND_UPDATE_TABLES_STATEMENTS = [
    # --- Таблица Users ---
    """
    CREATE TABLE IF NOT EXISTS users
    (
        telegram_id BIGINT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        language_code TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        is_vip BOOLEAN DEFAULT FALSE,
        timezone TEXT DEFAULT 'UTC',
        default_reminder_time TIME DEFAULT '09:00:00',
        pre_reminder_minutes INTEGER DEFAULT 60,
        daily_stt_recognitions_count INTEGER DEFAULT 0,
        last_stt_reset_date DATE,
        daily_digest_enabled BOOLEAN DEFAULT TRUE
    );
    """,
    # --- Поля для интеграции с Алисой ---
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='alice_user_id') THEN
            ALTER TABLE users ADD COLUMN alice_user_id TEXT;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='alice_activation_code') THEN
            ALTER TABLE users ADD COLUMN alice_activation_code TEXT;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='alice_code_expires_at') THEN
            ALTER TABLE users ADD COLUMN alice_code_expires_at TIMESTAMPTZ;
        END IF;
    END;
    $$;
    """,

    # --- Таблица Notes ---
    """
    CREATE TABLE IF NOT EXISTS notes
    (
        note_id SERIAL PRIMARY KEY,
        telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        summary_text TEXT,
        original_stt_text TEXT,
        corrected_text TEXT NOT NULL,
        category TEXT DEFAULT 'Общее',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        note_taken_at TIMESTAMPTZ,
        original_audio_telegram_file_id TEXT,
        llm_analysis_json JSONB,
        due_date TIMESTAMPTZ,
        recurrence_rule TEXT,
        is_archived BOOLEAN DEFAULT FALSE,
        is_completed BOOLEAN DEFAULT FALSE
    );
    """,
    # --- Безопасное добавление поля summary_text ---
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='notes' AND column_name='summary_text') THEN
            ALTER TABLE notes ADD COLUMN summary_text TEXT;
        END IF;
    END;
    $$;
    """,

    # --- Таблица Note Shares (Для совместного доступа) ---
    """
    CREATE TABLE IF NOT EXISTS note_shares
    (
        id SERIAL PRIMARY KEY,
        note_id BIGINT NOT NULL REFERENCES notes(note_id) ON DELETE CASCADE,
        owner_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        shared_with_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(note_id, shared_with_telegram_id)
    );
    """,

    # --- Таблица Shared Note Messages (Для синхронизации) ---
    """
    CREATE TABLE IF NOT EXISTS shared_note_messages
    (
        id SERIAL PRIMARY KEY,
        note_id BIGINT NOT NULL REFERENCES notes(note_id) ON DELETE CASCADE,
        user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        message_id BIGINT NOT NULL,
        UNIQUE(note_id, user_id)
    );
    """,

    # --- Таблица Share Tokens (Для deep-link шаринга) ---
    """
    CREATE TABLE IF NOT EXISTS share_tokens
    (
        id SERIAL PRIMARY KEY,
        token TEXT UNIQUE NOT NULL,
        note_id BIGINT NOT NULL REFERENCES notes(note_id) ON DELETE CASCADE,
        owner_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        expires_at TIMESTAMPTZ NOT NULL,
        is_used BOOLEAN DEFAULT FALSE
    );
    """,

    # --- Таблица Birthdays ---
    """
    CREATE TABLE IF NOT EXISTS birthdays
    (
        id SERIAL PRIMARY KEY,
        user_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        person_name TEXT NOT NULL,
        birth_day INTEGER NOT NULL,
        birth_month INTEGER NOT NULL,
        birth_year INTEGER,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,

    # --- Таблица User Actions (для аналитики) ---
    """
    CREATE TABLE IF NOT EXISTS user_actions
    (
        id SERIAL PRIMARY KEY,
        user_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        action_type TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        metadata JSONB
    );
    """,

    # --- Индексы ---
    "CREATE INDEX IF NOT EXISTS idx_notes_telegram_id ON notes (telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_notes_due_date ON notes (due_date);",
    "CREATE INDEX IF NOT EXISTS idx_birthdays_user_id ON birthdays (user_telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_user_actions_user_id ON user_actions (user_telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_user_actions_action_type ON user_actions (action_type);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_alice_user_id ON users(alice_user_id) WHERE alice_user_id IS NOT NULL;",
    "CREATE INDEX IF NOT EXISTS idx_note_shares_note_id ON note_shares (note_id);",
    "CREATE INDEX IF NOT EXISTS idx_note_shares_shared_with ON note_shares (shared_with_telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_share_tokens_token ON share_tokens (token);",
]


db_pool: asyncpg.Pool | None = None


async def get_db_pool() -> asyncpg.Pool:
    """Возвращает существующий пул соединений или создает новый."""
    global db_pool
    if db_pool is None or db_pool.is_closing():
        try:
            db_pool = await asyncpg.create_pool(dsn=DATABASE_URL, min_size=2, max_size=10)
            logger.info("Пул соединений к PostgreSQL успешно создан.")
        except Exception as e:
            logger.critical(f"Не удалось подключиться к PostgreSQL: {e}", exc_info=True)
            raise
    return db_pool


async def close_db_pool():
    """Закрывает пул соединений с базой данных."""
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None
        logger.info("Пул соединений к PostgreSQL закрыт.")


async def init_db():
    """Инициализирует схему базы данных, выполняя все DDL-запросы."""
    pool = await get_db_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            logger.info("Проверка и обновление схемы базы данных...")
            for statement in CREATE_AND_UPDATE_TABLES_STATEMENTS:
                try:
                    await connection.execute(statement)
                except Exception as e:
                    logger.error(f"Ошибка при выполнении SQL-запроса:\n{statement}\nОшибка: {e}")
                    raise
            logger.info("Схема базы данных актуальна.")


async def setup_database_on_startup():
    """Функция для вызова при запуске приложения."""
    await init_db()


async def shutdown_database_on_shutdown():
    """Функция для вызова при остановке приложения."""
    await close_db_pool()