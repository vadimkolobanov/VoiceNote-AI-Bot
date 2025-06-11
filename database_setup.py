# database_setup.py
import json
import asyncpg
import logging
import os
from datetime import datetime, timezone, date, time

# Импортируем константы из config.py
from config import DATABASE_URL, MAX_NOTES_MVP, NOTES_PER_PAGE

logger = logging.getLogger(__name__)

# --- SCHEMA DEFINITION ---
CREATE_TABLE_STATEMENTS = [
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
        custom_profile_data JSONB,
        subscription_status TEXT DEFAULT 'free',
        subscription_expires_at TIMESTAMPTZ
    );
    """,
    # Безопасное добавление колонок в таблицу users
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_stt_recognitions_count INTEGER DEFAULT 0;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_stt_reset_date DATE;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'UTC';",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_vip BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS default_reminder_time TIME DEFAULT '09:00:00';",
    """
    CREATE TABLE IF NOT EXISTS subscriptions
    (
        subscription_id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        price_cents INTEGER NOT NULL,
        currency TEXT NOT NULL DEFAULT 'RUB',
        duration_days INTEGER NOT NULL,
        is_active BOOLEAN DEFAULT TRUE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS notes
    (
        note_id SERIAL PRIMARY KEY,
        telegram_id BIGINT NOT NULL REFERENCES users (telegram_id) ON DELETE CASCADE,
        original_stt_text TEXT,
        corrected_text TEXT NOT NULL,
        category TEXT DEFAULT 'Общее',
        tags TEXT[],
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        note_taken_at TIMESTAMPTZ,
        original_audio_telegram_file_id TEXT,
        llm_analysis_json JSONB,
        due_date TIMESTAMPTZ,
        location_info JSONB,
        is_archived BOOLEAN DEFAULT FALSE,
        is_pinned BOOLEAN DEFAULT FALSE
    );
    """,
    # Безопасное добавление новой колонки в таблицу notes
    "ALTER TABLE notes ADD COLUMN IF NOT EXISTS is_completed BOOLEAN DEFAULT FALSE;",
    # Индексы
    "CREATE INDEX IF NOT EXISTS idx_notes_telegram_id ON notes (telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_notes_due_date ON notes (due_date);",
    "CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes (created_at DESC);",
    """
    CREATE TABLE IF NOT EXISTS payments
    (
        payment_id SERIAL PRIMARY KEY,
        telegram_id BIGINT NOT NULL REFERENCES users (telegram_id) ON DELETE CASCADE,
        subscription_id INTEGER REFERENCES subscriptions (subscription_id),
        amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL,
        payment_system TEXT,
        external_payment_id TEXT UNIQUE,
        status TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        paid_at TIMESTAMPTZ,
        payment_metadata JSONB
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS user_subscriptions
    (
        user_subscription_id SERIAL PRIMARY KEY,
        telegram_id BIGINT NOT NULL REFERENCES users (telegram_id) ON DELETE CASCADE,
        subscription_id INTEGER NOT NULL REFERENCES subscriptions (subscription_id) ON DELETE CASCADE,
        start_date TIMESTAMPTZ NOT NULL,
        end_date TIMESTAMPTZ NOT NULL,
        payment_id INTEGER REFERENCES payments (payment_id) ON DELETE SET NULL,
        status TEXT NOT NULL DEFAULT 'active',
        auto_renew BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_user_subscriptions_telegram_id ON user_subscriptions (telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_user_subscriptions_end_date ON user_subscriptions (end_date);"
]

# --- DATABASE POOL ---
db_pool: asyncpg.Pool | None = None


async def get_db_pool() -> asyncpg.Pool:
    global db_pool
    if db_pool is None:
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
            for statement in CREATE_TABLE_STATEMENTS:
                try:
                    await connection.execute(statement)
                except Exception as e:
                    logger.error(f"Ошибка при выполнении SQL: {statement}\n{e}")
            logger.info("Инициализация таблиц БД завершена.")
    await add_default_subscription_type()


async def add_default_subscription_type():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT subscription_id FROM subscriptions WHERE name = $1", "Full Месячная")
        if not existing:
            await conn.execute(
                """
                INSERT INTO subscriptions (name, description, price_cents, currency, duration_days, is_active)
                VALUES ($1, $2, $3, $4, $5, $6)
                """, "Full Месячная", "Полный доступ ко всем функциям на 1 месяц", 29900, "RUB", 30, True
            )
            logger.info("Тип подписки 'Full Месячная' добавлен.")


# --- USER OPERATIONS ---
async def add_or_update_user(telegram_id: int, username: str = None, first_name: str = None,
                             last_name: str = None, language_code: str = None) -> dict | None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)
        query = """
                INSERT INTO users (telegram_id, username, first_name, last_name, language_code, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $6) ON CONFLICT (telegram_id) DO \
                UPDATE SET
                    username = EXCLUDED.username, \
                    first_name = EXCLUDED.first_name, \
                    last_name = EXCLUDED.last_name, \
                    language_code = EXCLUDED.language_code, \
                    updated_at = $6 \
                    RETURNING *; \
                """
        user_record = await conn.fetchrow(query, telegram_id, username, first_name, last_name, language_code, now)
        return dict(user_record) if user_record else None


async def get_user_profile(telegram_id: int) -> dict | None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user_record = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        return dict(user_record) if user_record else None


async def set_user_timezone(telegram_id: int, timezone_str: str) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET timezone = $1, updated_at = NOW() WHERE telegram_id = $2",
            timezone_str, telegram_id
        )
        updated_count = int(result.split(" ")[1]) if result.startswith("UPDATE ") else 0
        if updated_count > 0:
            logger.info(f"Для пользователя {telegram_id} установлен часовой пояс: {timezone_str}")
        return updated_count > 0


async def set_user_default_reminder_time(telegram_id: int, reminder_time: time) -> bool:
    """Устанавливает время напоминания по умолчанию для пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET default_reminder_time = $1, updated_at = NOW() WHERE telegram_id = $2",
            reminder_time, telegram_id
        )
        updated_count = int(result.split(" ")[1]) if result.startswith("UPDATE ") else 0
        if updated_count > 0:
            logger.info(
                f"Для пользователя {telegram_id} установлено время напоминаний по умолчанию: {reminder_time.strftime('%H:%M')}")
        return updated_count > 0


async def get_all_users_paginated(page: int = 1, per_page: int = 10) -> tuple[list[dict], int]:
    """
    Получает список всех пользователей с пагинацией.
    Возвращает список пользователей на странице и общее количество пользователей.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total_items = await conn.fetchval("SELECT COUNT(*) FROM users")
        total_items = total_items or 0
        offset = (page - 1) * per_page
        users_query = """
            SELECT telegram_id, username, first_name, is_vip, created_at
            FROM users
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2;
        """
        users_records = await conn.fetch(users_query, per_page, offset)
        return [dict(record) for record in users_records], total_items


async def set_user_vip_status(telegram_id: int, is_vip: bool) -> bool:
    """Устанавливает VIP-статус для пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET is_vip = $1, updated_at = NOW() WHERE telegram_id = $2",
            is_vip, telegram_id
        )
        updated_count = int(result.split(" ")[1]) if result.startswith("UPDATE ") else 0
        if updated_count > 0:
            status = "активирован" if is_vip else "деактивирован"
            logger.info(f"VIP-статус для пользователя {telegram_id} был {status}.")
        return updated_count > 0


async def count_active_notes_for_user(telegram_id: int) -> int:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM notes WHERE telegram_id = $1 AND is_archived = FALSE AND is_completed = FALSE",
            telegram_id
        )
        return count or 0


async def get_paginated_notes_for_user(
        telegram_id: int,
        page: int = 1,
        per_page: int = NOTES_PER_PAGE,
        archived: bool = False
) -> tuple[list[dict], int]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if archived:
            extra_filter = ""
        else:
            extra_filter = "AND is_completed = FALSE"

        archived_filter_sql = "is_archived = TRUE" if archived else "is_archived = FALSE"

        total_query = f"SELECT COUNT(*) FROM notes WHERE telegram_id = $1 AND {archived_filter_sql} {extra_filter}"
        total_items = await conn.fetchval(total_query, telegram_id)
        total_items = total_items or 0
        offset = (page - 1) * per_page
        notes_query = f"""
            SELECT * FROM notes
            WHERE telegram_id = $1 AND {archived_filter_sql} {extra_filter}
            ORDER BY is_pinned DESC, due_date ASC, created_at DESC
            LIMIT $2 OFFSET $3;
        """
        notes_records = await conn.fetch(notes_query, telegram_id, per_page, offset)
        return [dict(record) for record in notes_records], total_items


# --- NOTE OPERATIONS ---
async def create_note(
        telegram_id: int, corrected_text: str, original_stt_text: str = None, category: str = 'Общее',
        tags: list[str] = None, note_taken_at: datetime = None, original_audio_telegram_file_id: str = None,
        llm_analysis_json: dict = None, due_date: datetime = None, location_info: dict = None
) -> int | None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)
        llm_analysis_json_string = json.dumps(llm_analysis_json) if llm_analysis_json is not None else None
        location_info_json_string = json.dumps(location_info) if location_info is not None else None
        query = """
                INSERT INTO notes (telegram_id, original_stt_text, corrected_text, category, tags, \
                                   created_at, updated_at, note_taken_at, original_audio_telegram_file_id, \
                                   llm_analysis_json, due_date, location_info) \
                VALUES ($1, $2, $3, $4, $5, $6, $6, $7, $8, $9, $10, $11) RETURNING note_id; \
                """
        try:
            note_id = await conn.fetchval(
                query, telegram_id, original_stt_text, corrected_text, category, tags, now,
                note_taken_at, original_audio_telegram_file_id, llm_analysis_json_string,
                due_date, location_info_json_string
            )
            logger.info(f"Создана заметка #{note_id} для пользователя {telegram_id}.")
            return note_id
        except Exception as e:
            logger.error(f"Ошибка при создании заметки для {telegram_id}: {e}", exc_info=True)
            return None


async def get_note_by_id(note_id: int, telegram_id: int) -> dict | None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        note_record = await conn.fetchrow(
            "SELECT * FROM notes WHERE note_id = $1 AND telegram_id = $2", note_id, telegram_id
        )
        return dict(note_record) if note_record else None


async def delete_note(note_id: int, telegram_id: int) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM notes WHERE note_id = $1 AND telegram_id = $2", note_id, telegram_id
        )
        deleted_count = int(result.split(" ")[1]) if result.startswith("DELETE ") else 0
        if deleted_count > 0:
            logger.info(f"Удалена (навсегда) заметка #{note_id} пользователя {telegram_id}.")
        return deleted_count > 0


async def update_note_text(note_id: int, new_text: str, telegram_id: int) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notes SET corrected_text = $1, updated_at = NOW() WHERE note_id = $2 AND telegram_id = $3",
            new_text, note_id, telegram_id
        )
        updated_count = int(result.split(" ")[1]) if result.startswith("UPDATE ") else 0
        if updated_count > 0:
            logger.info(f"Текст заметки #{note_id} обновлен пользователем {telegram_id}.")
        return updated_count > 0


async def set_note_archived_status(note_id: int, telegram_id: int, archived: bool) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notes SET is_archived = $1, updated_at = NOW() WHERE note_id = $2 AND telegram_id = $3",
            archived, note_id, telegram_id
        )
        updated_count = int(result.split(" ")[1]) if result.startswith("UPDATE ") else 0
        if updated_count > 0:
            status = "архивирована" if archived else "восстановлена из архива"
            logger.info(f"Заметка #{note_id} была {status} пользователем {telegram_id}.")
        return updated_count > 0


async def set_note_completed_status(note_id: int, telegram_id: int, completed: bool) -> bool:
    """Устанавливает статус выполнения для заметки. Если выполнена - также архивирует."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        is_archived = True if completed else False
        result = await conn.execute(
            "UPDATE notes SET is_completed = $1, is_archived = $2, updated_at = NOW() WHERE note_id = $3 AND telegram_id = $4",
            completed, is_archived, note_id, telegram_id
        )
        updated_count = int(result.split(" ")[1]) if result.startswith("UPDATE ") else 0
        if updated_count > 0:
            status = "выполнена и архивирована" if completed else "возвращена в активные"
            logger.info(f"Заметка #{note_id} была помечена как '{status}' пользователем {telegram_id}.")
        return updated_count > 0


async def update_note_category(note_id: int, new_category: str, telegram_id: int) -> bool:
    """Обновляет категорию заметки."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notes SET category = $1, updated_at = NOW() WHERE note_id = $2 AND telegram_id = $3",
            new_category, note_id, telegram_id
        )
        updated_count = int(result.split(" ")[1]) if result.startswith("UPDATE ") else 0
        if updated_count > 0:
            logger.info(f"Категория заметки #{note_id} обновлена на '{new_category}'.")
        return updated_count > 0


async def get_notes_with_reminders() -> list[dict]:
    """Получает все активные, неархивированные и невыполненные заметки с due_date в будущем."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)
        query = """
            SELECT n.note_id, n.telegram_id, n.corrected_text, n.due_date, u.default_reminder_time, u.timezone
            FROM notes n
            JOIN users u ON n.telegram_id = u.telegram_id
            WHERE n.is_archived = FALSE 
              AND n.is_completed = FALSE 
              AND n.due_date IS NOT NULL 
              AND n.due_date > $1;
        """
        notes_records = await conn.fetch(query, now)
        return [dict(record) for record in notes_records]


async def update_user_stt_counters(telegram_id: int, new_count: int, reset_date: date):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET daily_stt_recognitions_count = $1, last_stt_reset_date = $2, updated_at = NOW()
            WHERE telegram_id = $3
            """, new_count, reset_date, telegram_id
        )


async def setup_database_on_startup():
    try:
        await init_db()
    except Exception as e:
        logger.critical(f"Не удалось инициализировать базу данных: {e}", exc_info=True)
        raise


async def shutdown_database_on_shutdown():
    await close_db_pool()