# src/database/connection.py
import asyncio
import logging

import asyncpg

from src.core.config import DATABASE_URL

logger = logging.getLogger(__name__)

CREATE_AND_UPDATE_TABLES_STATEMENTS = [
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
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='has_completed_onboarding') THEN
            ALTER TABLE users ADD COLUMN has_completed_onboarding BOOLEAN DEFAULT FALSE;
        END IF;
    END;
    $$;
    """,
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
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='daily_digest_time') THEN
            ALTER TABLE users ADD COLUMN daily_digest_time TIME DEFAULT '09:00:00';
        END IF;
    END;
    $$;
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='xp') THEN
            ALTER TABLE users ADD COLUMN xp BIGINT DEFAULT 0;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='level') THEN
            ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1;
        END IF;
    END;
    $$;
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='city_name') THEN
            ALTER TABLE users ADD COLUMN city_name TEXT;
        END IF;
    END;
    $$;
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='viewed_guides') THEN
            ALTER TABLE users ADD COLUMN viewed_guides JSONB DEFAULT '[]'::jsonb;
        END IF;
    END;
    $$;
    """,
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
        is_completed BOOLEAN DEFAULT FALSE,
        snooze_count INTEGER DEFAULT 0
    );
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='notes' AND column_name='summary_text') THEN
            ALTER TABLE notes ADD COLUMN summary_text TEXT;
        END IF;
    END;
    $$;
    """,
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
    """
    CREATE TABLE IF NOT EXISTS achievements
    (
        id SERIAL PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        icon TEXT,
        xp_reward INTEGER DEFAULT 0
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS user_achievements
    (
        id SERIAL PRIMARY KEY,
        user_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        achievement_code TEXT NOT NULL REFERENCES achievements(code) ON DELETE CASCADE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (user_telegram_id, achievement_code)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS mobile_activation_codes (
        telegram_id BIGINT PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
        code TEXT NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS user_devices (
        id SERIAL PRIMARY KEY,
        user_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        fcm_token TEXT UNIQUE NOT NULL,
        platform TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        last_used_at TIMESTAMPTZ
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_notes_telegram_id ON notes (telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_notes_due_date ON notes (due_date);",
    "CREATE INDEX IF NOT EXISTS idx_birthdays_user_id ON birthdays (user_telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_user_actions_user_id ON user_actions (user_telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_user_actions_action_type ON user_actions (action_type);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_alice_user_id ON users(alice_user_id) WHERE alice_user_id IS NOT NULL;",
    "CREATE INDEX IF NOT EXISTS idx_note_shares_note_id ON note_shares (note_id);",
    "CREATE INDEX IF NOT EXISTS idx_note_shares_shared_with ON note_shares (shared_with_telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_share_tokens_token ON share_tokens (token);",
    "CREATE INDEX IF NOT EXISTS idx_user_achievements_user_id ON user_achievements (user_telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_mobile_activation_codes_code ON mobile_activation_codes(code);",
    "CREATE INDEX IF NOT EXISTS idx_user_devices_user_id ON user_devices(user_telegram_id);",
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
    from src.services.gamification_service import ACHIEVEMENTS_LIST
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

            logger.info("Синхронизация справочника достижений...")
            for ach in ACHIEVEMENTS_LIST:
                await connection.execute(
                    """
                    INSERT INTO achievements (code, name, description, icon, xp_reward)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (code) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        icon = EXCLUDED.icon,
                        xp_reward = EXCLUDED.xp_reward;
                    """,
                    ach.code, ach.name, ach.description, ach.icon, ach.xp_reward
                )

            logger.info("Схема базы данных актуальна.")


async def setup_database_on_startup():
    """Выполняется при запуске приложения для инициализации БД."""
    await init_db()


async def shutdown_database_on_shutdown():
    """Выполняется при остановке приложения для закрытия пула соединений."""
    await close_db_pool()