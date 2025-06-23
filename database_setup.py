# database_setup.py
import json
import asyncpg
import logging
from datetime import datetime, timezone, date, time

from config import DATABASE_URL, NOTES_PER_PAGE

logger = logging.getLogger(__name__)

# --- СХЕМА ОБНОВЛЕНИЯ БАЗЫ ДАННЫХ ---
# Этот массив содержит все SQL-запросы для создания и обновления таблиц.
# Они написаны таким образом, чтобы быть безопасными для повторного выполнения.
# (IF NOT EXISTS, ALTER TABLE ... ADD COLUMN IF NOT EXISTS)
CREATE_AND_UPDATE_TABLES_STATEMENTS = [
    # --- Таблица Users ---
    """
    CREATE TABLE IF NOT EXISTS users
    (
        telegram_id
        BIGINT
        PRIMARY
        KEY,
        username
        TEXT,
        first_name
        TEXT,
        last_name
        TEXT,
        language_code
        TEXT,
        created_at
        TIMESTAMPTZ
        DEFAULT
        NOW
    (
    ),
        updated_at TIMESTAMPTZ DEFAULT NOW
    (
    ),
        is_vip BOOLEAN DEFAULT FALSE,
        timezone TEXT DEFAULT 'UTC',
        default_reminder_time TIME DEFAULT '09:00:00',
        pre_reminder_minutes INTEGER DEFAULT 60,
        daily_stt_recognitions_count INTEGER DEFAULT 0,
        last_stt_reset_date DATE,
        daily_digest_enabled BOOLEAN DEFAULT TRUE
        );
    """,
    # --- Новые поля для интеграции с Алисой ---
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
        note_id
        SERIAL
        PRIMARY
        KEY,
        telegram_id
        BIGINT
        NOT
        NULL
        REFERENCES
        users
    (
        telegram_id
    ) ON DELETE CASCADE,
        original_stt_text TEXT,
        corrected_text TEXT NOT NULL,
        category TEXT DEFAULT 'Общее',
        created_at TIMESTAMPTZ DEFAULT NOW
    (
    ),
        updated_at TIMESTAMPTZ DEFAULT NOW
    (
    ),
        note_taken_at TIMESTAMPTZ,
        original_audio_telegram_file_id TEXT,
        llm_analysis_json JSONB,
        due_date TIMESTAMPTZ,
        recurrence_rule TEXT,
        is_archived BOOLEAN DEFAULT FALSE,
        is_completed BOOLEAN DEFAULT FALSE
        );
    """,

    # --- Таблица Birthdays ---
    """
    CREATE TABLE IF NOT EXISTS birthdays
    (
        id
        SERIAL
        PRIMARY
        KEY,
        user_telegram_id
        BIGINT
        NOT
        NULL
        REFERENCES
        users
    (
        telegram_id
    ) ON DELETE CASCADE,
        person_name TEXT NOT NULL,
        birth_day INTEGER NOT NULL,
        birth_month INTEGER NOT NULL,
        birth_year INTEGER,
        created_at TIMESTAMPTZ DEFAULT NOW
    (
    )
        );
    """,

    # --- Таблица User Actions (для аналитики) ---
    """
    CREATE TABLE IF NOT EXISTS user_actions
    (
        id
        SERIAL
        PRIMARY
        KEY,
        user_telegram_id
        BIGINT
        NOT
        NULL
        REFERENCES
        users
    (
        telegram_id
    ) ON DELETE CASCADE,
        action_type TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW
    (
    ),
        metadata JSONB
        );
    """,

    # --- Индексы для ускорения запросов ---
    "CREATE INDEX IF NOT EXISTS idx_notes_telegram_id ON notes (telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_notes_due_date ON notes (due_date);",
    "CREATE INDEX IF NOT EXISTS idx_birthdays_user_id ON birthdays (user_telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_user_actions_user_id ON user_actions (user_telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_user_actions_action_type ON user_actions (action_type);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_alice_user_id ON users(alice_user_id) WHERE alice_user_id IS NOT NULL;",
]

# --- DATABASE POOL ---
db_pool: asyncpg.Pool | None = None


async def get_db_pool() -> asyncpg.Pool:
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
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None
        logger.info("Пул соединений к PostgreSQL закрыт.")


async def init_db():
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


# --- USER OPERATIONS ---
async def add_or_update_user(telegram_id: int, username: str = None, first_name: str = None, last_name: str = None,
                             language_code: str = None) -> dict | None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)
        query = """
                INSERT INTO users (telegram_id, username, first_name, last_name, language_code, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $6) ON CONFLICT (telegram_id) DO
                UPDATE SET
                    username = EXCLUDED.username, first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name, language_code = EXCLUDED.language_code,
                    updated_at = $6
                    RETURNING *; \
                """
        user_record = await conn.fetchrow(query, telegram_id, username, first_name, last_name, language_code, now)
        return dict(user_record) if user_record else None


async def get_user_profile(telegram_id: int) -> dict | None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user_record = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        return dict(user_record) if user_record else None


async def set_user_vip_status(telegram_id: int, is_vip: bool) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("UPDATE users SET is_vip = $1, updated_at = NOW() WHERE telegram_id = $2", is_vip,
                                    telegram_id)
        return int(result.split(" ")[1]) > 0


async def reset_user_vip_settings(telegram_id: int) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET default_reminder_time = DEFAULT, pre_reminder_minutes = DEFAULT, updated_at = NOW() WHERE telegram_id = $1"
        result = await conn.execute(query, telegram_id)
        return int(result.split(" ")[1]) > 0


async def get_all_users_paginated(page: int = 1, per_page: int = 5) -> tuple[list[dict], int]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total_items = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
        offset = (page - 1) * per_page
        users_records = await conn.fetch(
            "SELECT telegram_id, username, first_name, is_vip FROM users ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            per_page, offset)
        return [dict(record) for record in users_records], total_items


async def update_user_stt_counters(telegram_id: int, new_count: int, reset_date: date) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET daily_stt_recognitions_count = $1, last_stt_reset_date = $2, updated_at = NOW() WHERE telegram_id = $3",
            new_count, reset_date, telegram_id)
        return int(result.split(" ")[1]) > 0


async def set_user_daily_digest_status(telegram_id: int, enabled: bool) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET daily_digest_enabled = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, enabled, telegram_id)
        return int(result.split(" ")[1]) > 0


async def get_vip_users_for_digest() -> list[dict]: # <-- Убираем параметр current_utc_hour
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Этот запрос уже делает всё, что нужно: находит пользователей,
        # у которых сейчас 9 утра в их локальной таймзоне.
        query = """
        SELECT telegram_id, first_name, timezone
        FROM users
        WHERE is_vip = TRUE
          AND daily_digest_enabled = TRUE
          AND EXTRACT(HOUR FROM (NOW() AT TIME ZONE timezone)) = 9;
        """
        records = await conn.fetch(query) # <-- Вызываем без параметров
        return [dict(rec) for rec in records]


async def set_user_timezone(telegram_id: int, timezone_name: str) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET timezone = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, timezone_name, telegram_id)
        return int(result.split(" ")[1]) > 0


async def set_user_default_reminder_time(telegram_id: int, reminder_time: time) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET default_reminder_time = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, reminder_time, telegram_id)
        return int(result.split(" ")[1]) > 0


async def set_user_pre_reminder_minutes(telegram_id: int, minutes: int) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET pre_reminder_minutes = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, minutes, telegram_id)
        return int(result.split(" ")[1]) > 0


# --- ALICE INTEGRATION OPERATIONS ---
async def set_alice_activation_code(telegram_id: int, code: str, expires_at: datetime) -> bool:
    """Устанавливает код активации для пользователя Telegram."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET alice_activation_code = $1, alice_code_expires_at = $2 WHERE telegram_id = $3"
        result = await conn.execute(query, code, expires_at, telegram_id)
        return int(result.split(" ")[1]) > 0


async def find_user_by_alice_code(code: str) -> dict | None:
    """Находит пользователя по коду активации, если он не истек."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM users WHERE alice_activation_code = $1 AND alice_code_expires_at > NOW()"
        record = await conn.fetchrow(query, code)
        return dict(record) if record else None


async def link_alice_user(telegram_id: int, alice_id: str) -> bool:
    """Связывает аккаунт Alice с аккаунтом Telegram и очищает код."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET alice_user_id = $1, alice_activation_code = NULL, alice_code_expires_at = NULL, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, alice_id, telegram_id)
        return int(result.split(" ")[1]) > 0


async def find_user_by_alice_id(alice_id: str) -> dict | None:
    """Находит пользователя по его Alice ID."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM users WHERE alice_user_id = $1"
        record = await conn.fetchrow(query, alice_id)
        return dict(record) if record else None


# --- NOTE OPERATIONS ---
async def count_active_notes_for_user(telegram_id: int) -> int:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM notes WHERE telegram_id = $1 AND is_archived = FALSE AND is_completed = FALSE",
            telegram_id) or 0


async def get_paginated_notes_for_user(telegram_id: int, page: int = 1, per_page: int = NOTES_PER_PAGE,
                                       archived: bool = False) -> tuple[list[dict], int]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        archived_filter_sql = "is_archived = TRUE" if archived else "is_archived = FALSE AND is_completed = FALSE"
        total_items = await conn.fetchval(
            f"SELECT COUNT(*) FROM notes WHERE telegram_id = $1 AND {archived_filter_sql}", telegram_id) or 0
        offset = (page - 1) * per_page
        notes_records = await conn.fetch(
            f"SELECT * FROM notes WHERE telegram_id = $1 AND {archived_filter_sql} ORDER BY due_date ASC NULLS LAST, created_at DESC LIMIT $2 OFFSET $3;",
            telegram_id, per_page, offset)
        return [dict(record) for record in notes_records], total_items


async def create_note(telegram_id: int, corrected_text: str, **kwargs) -> int | None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                INSERT INTO notes (telegram_id, corrected_text, original_stt_text, llm_analysis_json,
                                   original_audio_telegram_file_id, note_taken_at, due_date, recurrence_rule)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING note_id; \
                """
        try:
            llm_json_str = json.dumps(kwargs.get("llm_analysis_json")) if kwargs.get("llm_analysis_json") else None
            note_id = await conn.fetchval(
                query, telegram_id, corrected_text, kwargs.get("original_stt_text"), llm_json_str,
                kwargs.get("original_audio_telegram_file_id"), kwargs.get("note_taken_at"), kwargs.get("due_date"),
                kwargs.get("recurrence_rule")
            )
            return note_id
        except Exception as e:
            logger.error(f"Ошибка при создании заметки для {telegram_id}: {e}", exc_info=True)
            return None


async def get_note_by_id(note_id: int, telegram_id: int) -> dict | None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        record = await conn.fetchrow("SELECT * FROM notes WHERE note_id = $1 AND telegram_id = $2", note_id,
                                     telegram_id)
        return dict(record) if record else None


async def get_notes_for_today_digest(telegram_id: int, user_timezone: str) -> list[dict]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                SELECT corrected_text, due_date
                FROM notes
                WHERE telegram_id = $1
                  AND is_archived = FALSE
                  AND is_completed = FALSE
                  AND due_date IS NOT NULL
                  AND (due_date AT TIME ZONE $2)::date = (NOW() AT TIME ZONE $2):: date
                ORDER BY due_date ASC; \
                """
        records = await conn.fetch(query, telegram_id, user_timezone)
        return [dict(rec) for rec in records]


async def delete_note(note_id: int, telegram_id: int) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM notes WHERE note_id = $1 AND telegram_id = $2", note_id, telegram_id)
        return int(result.split(" ")[1]) > 0


async def set_note_completed_status(note_id: int, telegram_id: int, completed: bool) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notes SET is_completed = $1, is_archived = $1, updated_at = NOW() WHERE note_id = $2 AND telegram_id = $3",
            completed, note_id, telegram_id)
        return int(result.split(" ")[1]) > 0


async def update_note_due_date(note_id: int, new_due_date: datetime) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("UPDATE notes SET due_date = $1, updated_at = NOW() WHERE note_id = $2",
                                    new_due_date, note_id)
        return int(result.split(" ")[1]) > 0


async def set_note_recurrence_rule(note_id: int, telegram_id: int, rule: str | None) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE notes SET recurrence_rule = $1, updated_at = NOW() WHERE note_id = $2 AND telegram_id = $3"
        result = await conn.execute(query, rule, note_id, telegram_id)
        return int(result.split(" ")[1]) > 0


async def get_notes_with_reminders() -> list[dict]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                SELECT n.*, u.default_reminder_time, u.timezone, u.pre_reminder_minutes, u.is_vip
                FROM notes n \
                         JOIN users u ON n.telegram_id = u.telegram_id
                WHERE n.is_archived = FALSE
                  AND n.is_completed = FALSE
                  AND n.due_date IS NOT NULL
                  AND n.due_date > NOW(); \
                """
        return [dict(rec) for rec in await conn.fetch(query)]


async def update_note_text(note_id: int, new_text: str, telegram_id: int) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notes SET corrected_text = $1, updated_at = NOW() WHERE note_id = $2 AND telegram_id = $3",
            new_text, note_id, telegram_id)
        return int(result.split(" ")[1]) > 0


async def update_note_category(note_id: int, new_category: str, telegram_id: int) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notes SET category = $1, updated_at = NOW() WHERE note_id = $2 AND telegram_id = $3", new_category,
            note_id, telegram_id)
        return int(result.split(" ")[1]) > 0


async def set_note_archived_status(note_id: int, telegram_id: int, archived: bool) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notes SET is_archived = $1, updated_at = NOW() WHERE note_id = $2 AND telegram_id = $3", archived,
            note_id, telegram_id)
        return int(result.split(" ")[1]) > 0


# --- BIRTHDAY OPERATIONS ---
async def count_birthdays_for_user(telegram_id: int) -> int:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM birthdays WHERE user_telegram_id = $1", telegram_id) or 0


async def get_birthdays_for_user(telegram_id: int, page: int = 1, per_page: int = 5) -> tuple[list[dict], int]:
    pool = await get_db_pool()
    offset = (page - 1) * per_page
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM birthdays WHERE user_telegram_id = $1", telegram_id) or 0
        query = """
                SELECT * \
                FROM birthdays
                WHERE user_telegram_id = $1
                ORDER BY CASE
                             WHEN (birth_month, birth_day) < (EXTRACT(MONTH FROM NOW()), EXTRACT(DAY FROM NOW())) THEN 1
                             ELSE 0 END,
                         birth_month, birth_day
                    LIMIT $2
                OFFSET $3; \
                """
        records = await conn.fetch(query, telegram_id, per_page, offset)
    return [dict(rec) for rec in records], total


async def get_birthdays_for_upcoming_digest(telegram_id: int) -> list[dict]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                SELECT person_name, birth_day, birth_month, birth_year
                FROM birthdays
                WHERE user_telegram_id = $1
                  AND to_date(
                        to_char(NOW(), 'YYYY') || '-' || to_char(birth_month, 'FM00') || '-' || \
                        to_char(birth_day, 'FM00'),
                        'YYYY-MM-DD'
                      ) BETWEEN date_trunc('day', NOW()) AND date_trunc('day', NOW()) + \
                    interval '7 days'
                ORDER BY birth_month, birth_day; \
                """
        records = await conn.fetch(query, telegram_id)
        return [dict(rec) for rec in records]


async def add_birthday(user_telegram_id: int, person_name: str, day: int, month: int, year: int | None) -> dict | None:
    pool = await get_db_pool()
    query = "INSERT INTO birthdays (user_telegram_id, person_name, birth_day, birth_month, birth_year) VALUES ($1, $2, $3, $4, $5) RETURNING *;"
    async with pool.acquire() as conn:
        record = await conn.fetchrow(query, user_telegram_id, person_name, day, month, year)
        return dict(record) if record else None


async def delete_birthday(birthday_id: int, user_telegram_id: int) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM birthdays WHERE id = $1 AND user_telegram_id = $2", birthday_id,
                                    user_telegram_id)
        return int(result.split(" ")[1]) > 0


async def add_birthdays_bulk(user_telegram_id: int, birthdays_data: list[tuple]) -> int:
    pool = await get_db_pool()
    query = "INSERT INTO birthdays (user_telegram_id, person_name, birth_day, birth_month, birth_year) VALUES ($1, $2, $3, $4, $5);"
    data_to_insert = [(user_telegram_id, *b) for b in birthdays_data]
    async with pool.acquire() as conn:
        await conn.executemany(query, data_to_insert)
    return len(data_to_insert)


async def get_all_birthdays_for_reminders() -> list[dict]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return [dict(rec) for rec in await conn.fetch("SELECT * FROM birthdays")]


# --- USER ACTIONS (ANALYTICS) ---
async def log_user_action(user_telegram_id: int, action_type: str, metadata: dict = None):
    pool = await get_db_pool()
    metadata_json = json.dumps(metadata) if metadata else None
    query = "INSERT INTO user_actions (user_telegram_id, action_type, metadata) VALUES ($1, $2, $3);"
    try:
        async with pool.acquire() as conn:
            await conn.execute(query, user_telegram_id, action_type, metadata_json)
    except Exception as e:
        logger.error(f"Ошибка логирования действия '{action_type}' для {user_telegram_id}: {e}")


# --- LIFECYCLE FUNCTIONS ---
async def setup_database_on_startup():
    await init_db()


async def shutdown_database_on_shutdown():
    await close_db_pool()