# database_setup.py
import json

import asyncpg
import logging
import os
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

load_dotenv()
# --- DATABASE CONNECTION PARAMETERS ---
# Лучше брать из переменных окружения
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "voice_notes_bot_db")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

logger = logging.getLogger(__name__)

# --- SCHEMA DEFINITION ---

CREATE_TABLE_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        telegram_id BIGINT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        language_code TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        custom_profile_data JSONB,
        subscription_status TEXT DEFAULT 'free', -- 'free', 'active_trial', 'active_paid', 'expired', 'cancelled'
        subscription_expires_at TIMESTAMPTZ
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS subscriptions (
        subscription_id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        price_cents INTEGER NOT NULL,
        currency TEXT NOT NULL DEFAULT 'RUB',
        duration_days INTEGER NOT NULL,
        is_active BOOLEAN DEFAULT TRUE
    );
    """,
    # Предзаполним типы подписок, если нужно
    # """
    # INSERT INTO subscriptions (name, description, price_cents, currency, duration_days)
    # VALUES ('Full Месячная', 'Полный доступ ко всем функциям на 1 месяц', 29900, 'RUB', 30)
    # ON CONFLICT (name) DO NOTHING;
    # """,
    """
    CREATE TABLE IF NOT EXISTS notes (
        note_id SERIAL PRIMARY KEY,
        telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
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
    """
    CREATE INDEX IF NOT EXISTS idx_notes_telegram_id ON notes (telegram_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_notes_due_date ON notes (due_date);
    """,
    """
    CREATE TABLE IF NOT EXISTS payments (
        payment_id SERIAL PRIMARY KEY,
        telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        subscription_id INTEGER REFERENCES subscriptions(subscription_id), -- Может быть NULL если платеж не за подписку
        amount_cents INTEGER NOT NULL,
        currency TEXT NOT NULL,
        payment_system TEXT,
        external_payment_id TEXT UNIQUE,
        status TEXT NOT NULL, -- 'pending', 'succeeded', 'failed', 'refunded'
        created_at TIMESTAMPTZ DEFAULT NOW(),
        paid_at TIMESTAMPTZ,
        payment_metadata JSONB
    );
    """,
    # Таблица user_subscriptions нужна для отслеживания истории подписок и активных
    # даже если мы не используем payments сразу для активации
    """
    CREATE TABLE IF NOT EXISTS user_subscriptions (
        user_subscription_id SERIAL PRIMARY KEY,
        telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        subscription_id INTEGER NOT NULL REFERENCES subscriptions(subscription_id) ON DELETE CASCADE,
        start_date TIMESTAMPTZ NOT NULL,
        end_date TIMESTAMPTZ NOT NULL,
        payment_id INTEGER REFERENCES payments(payment_id) ON DELETE SET NULL,
        status TEXT NOT NULL DEFAULT 'active', -- 'active', 'expired', 'cancelled_by_user', 'cancelled_by_admin'
        auto_renew BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_user_subscriptions_telegram_id ON user_subscriptions (telegram_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_user_subscriptions_end_date ON user_subscriptions (end_date);
    """
]

# --- DATABASE POOL ---
db_pool = None

async def get_db_pool():
    """Возвращает пул соединений к БД, создавая его при необходимости."""
    global db_pool
    if db_pool is None:
        try:
            db_pool = await asyncpg.create_pool(dsn=DATABASE_URL, min_size=1, max_size=10)
            logger.info("Пул соединений к PostgreSQL успешно создан.")
        except Exception as e:
            logger.critical(f"Не удалось подключиться к PostgreSQL: {e}", exc_info=True)
            # В реальном приложении здесь может быть более сложная логика (retry, выход)
            raise
    return db_pool

async def close_db_pool():
    """Закрывает пул соединений к БД."""
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None
        logger.info("Пул соединений к PostgreSQL закрыт.")

async def init_db():
    """Инициализирует базу данных, создавая таблицы, если они не существуют."""
    pool = await get_db_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            for statement in CREATE_TABLE_STATEMENTS:
                try:
                    await connection.execute(statement)
                except Exception as e:
                    logger.error(f"Ошибка при выполнении SQL: {statement}\n{e}")
                    # В зависимости от критичности ошибки, можно либо продолжить, либо прервать
            logger.info("Инициализация таблиц БД завершена.")
    # Пример добавления типа подписки по умолчанию
    await add_default_subscription_type()


async def add_default_subscription_type():
    """Добавляет тип подписки по умолчанию, если его нет."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Проверим, существует ли уже такая подписка
        existing = await conn.fetchrow("SELECT subscription_id FROM subscriptions WHERE name = $1", "Full Месячная")
        if not existing:
            await conn.execute(
                """
                INSERT INTO subscriptions (name, description, price_cents, currency, duration_days, is_active)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                "Full Месячная",
                "Полный доступ ко всем функциям на 1 месяц",
                29900,  # 299 рублей
                "RUB",
                30,
                True
            )
            logger.info("Тип подписки 'Full Месячная' добавлен.")


# --- USER OPERATIONS ---

async def add_or_update_user(telegram_id: int, username: str = None, first_name: str = None,
                             last_name: str = None, language_code: str = None) -> dict:
    """
    Добавляет нового пользователя или обновляет существующего.
    Возвращает данные пользователя.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)
        # Используем ON CONFLICT для атомарного UPSERT
        query = """
            INSERT INTO users (telegram_id, username, first_name, last_name, language_code, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $6)
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                language_code = EXCLUDED.language_code,
                updated_at = $6
            RETURNING *;
        """
        user_record = await conn.fetchrow(query, telegram_id, username, first_name, last_name, language_code, now)
        logger.info(f"Пользователь {telegram_id} добавлен/обновлен.")
        return dict(user_record) if user_record else None


async def get_user_profile(telegram_id: int) -> dict | None:
    """Получает профиль пользователя по telegram_id."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user_record = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        return dict(user_record) if user_record else None


async def update_user_custom_data(telegram_id: int, custom_data: dict) -> bool:
    """Обновляет поле custom_profile_data для пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)
        custom_data_json_string = json.dumps(custom_data)
        # Используем jsonb_merge для обновления JSONB поля
        result = await conn.execute(
            """
            UPDATE users
            SET custom_profile_data = COALESCE(custom_profile_data, '{}'::jsonb) || $1::jsonb,
                updated_at = $2
            WHERE telegram_id = $3
            """,
            custom_data_json_string, now, telegram_id
        )
        return result == "UPDATE 1"

async def update_user_subscription_status(telegram_id: int, status: str, expires_at: datetime = None) -> bool:
    """Обновляет статус подписки пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)
        result = await conn.execute(
            """
            UPDATE users
            SET subscription_status = $1,
                subscription_expires_at = $2,
                updated_at = $3
            WHERE telegram_id = $4
            """,
            status, expires_at, now, telegram_id
        )
        return result == "UPDATE 1"


# --- NOTE OPERATIONS ---

async def create_note(
    telegram_id: int,
    corrected_text: str,
    original_stt_text: str = None,
    category: str = 'Общее',
    tags: list[str] = None,
    note_taken_at: datetime = None,
    original_audio_telegram_file_id: str = None,
    llm_analysis_json: dict = None, # <--- Принимаем как dict
    due_date: datetime = None,
    location_info: dict = None      # <--- Принимаем как dict
) -> int | None:
    """
    Создает новую заметку и возвращает ее note_id.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)

        # Преобразуем Python dict в JSON-строку, если они не None
        llm_analysis_json_string = json.dumps(llm_analysis_json) if llm_analysis_json is not None else None # <--- ИЗМЕНЕНИЕ
        location_info_json_string = json.dumps(location_info) if location_info is not None else None       # <--- ИЗМЕНЕНИЕ

        query = """
            INSERT INTO notes (
                telegram_id, original_stt_text, corrected_text, category, tags,
                created_at, updated_at, note_taken_at, original_audio_telegram_file_id,
                llm_analysis_json, due_date, location_info
            )
            VALUES ($1, $2, $3, $4, $5, $6, $6, $7, $8, $9, $10, $11)
            RETURNING note_id;
        """
        try:
            note_id = await conn.fetchval(
                query,
                telegram_id, original_stt_text, corrected_text, category, tags,
                now, # created_at, updated_at
                note_taken_at,
                original_audio_telegram_file_id,
                llm_analysis_json_string, # <--- Передаем JSON-строку
                due_date,
                location_info_json_string  # <--- Передаем JSON-строку
            )
            logger.info(f"Создана заметка {note_id} для пользователя {telegram_id}.")
            return note_id
        except Exception as e:
            logger.error(f"Ошибка при создании заметки для {telegram_id}: {e}", exc_info=True)
            return None


async def get_notes_by_user(telegram_id: int, limit: int = 10, offset: int = 0,
                            archived: bool = False) -> list[dict]:
    """Получает список заметок пользователя с пагинацией."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
            SELECT * FROM notes
            WHERE telegram_id = $1 AND is_archived = $2
            ORDER BY is_pinned DESC, created_at DESC
            LIMIT $3 OFFSET $4;
        """
        notes_records = await conn.fetch(query, telegram_id, archived, limit, offset)
        return [dict(record) for record in notes_records]

async def get_note_by_id(note_id: int, telegram_id: int) -> dict | None:
    """Получает заметку по ее ID и ID пользователя (для проверки прав)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        note_record = await conn.fetchrow(
            "SELECT * FROM notes WHERE note_id = $1 AND telegram_id = $2",
            note_id, telegram_id
        )
        return dict(note_record) if note_record else None

async def update_note_text(note_id: int, telegram_id: int, corrected_text: str,
                           llm_analysis_json: dict = None) -> bool: # <--- Принимаем как dict
    """Обновляет текст заметки и результаты LLM анализа."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)

        # Преобразуем Python dict в JSON-строку, если он не None
        llm_analysis_json_string = json.dumps(llm_analysis_json) if llm_analysis_json is not None else None # <--- ИЗМЕНЕНИЕ

        result = await conn.execute(
            """
            UPDATE notes
            SET corrected_text = $1,
                llm_analysis_json = COALESCE($2, llm_analysis_json),
                updated_at = $3
            WHERE note_id = $4 AND telegram_id = $5
            """,
            corrected_text, llm_analysis_json_string, now, note_id, telegram_id # <--- Передаем JSON-строку
        )
        if result == "UPDATE 1":
            logger.info(f"Текст и LLM анализ для заметки {note_id} обновлены.")
        return result == "UPDATE 1"

async def archive_note(note_id: int, telegram_id: int, archive_status: bool = True) -> bool:
    """Архивирует или разархивирует заметку."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)
        result = await conn.execute(
            "UPDATE notes SET is_archived = $1, updated_at = $2 WHERE note_id = $3 AND telegram_id = $4",
            archive_status, now, note_id, telegram_id
        )
        return result == "UPDATE 1"

async def pin_note(note_id: int, telegram_id: int, pin_status: bool = True) -> bool:
    """Закрепляет или открепляет заметку."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)
        result = await conn.execute(
            "UPDATE notes SET is_pinned = $1, updated_at = $2 WHERE note_id = $3 AND telegram_id = $4",
            pin_status, now, note_id, telegram_id
        )
        return result == "UPDATE 1"

async def delete_note(note_id: int, telegram_id: int) -> bool:
    """Удаляет заметку."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM notes WHERE note_id = $1 AND telegram_id = $2",
            note_id, telegram_id
        )
        # result будет "DELETE N", где N - количество удаленных строк
        return result.startswith("DELETE") and int(result.split(" ")[1]) > 0


# --- SUBSCRIPTION & PAYMENT OPERATIONS (заглушки или базовые) ---

async def get_subscription_type_by_name(name: str) -> dict | None:
    """Получает тип подписки по имени."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        record = await conn.fetchrow("SELECT * FROM subscriptions WHERE name = $1 AND is_active = TRUE", name)
        return dict(record) if record else None


# Функции для создания платежа, активации подписки пользователя будут сложнее
# и потребуют интеграции с платежной системой. Пока это базовые CRUD.

# Пример функции, которая будет вызываться в main.py при запуске бота
async def setup_database_on_startup():
    """Выполняет инициализацию БД при старте приложения."""
    try:
        await init_db() # Создаст таблицы, если их нет
    except Exception as e:
        logger.critical(f"Не удалось инициализировать базу данных: {e}", exc_info=True)
        # В зависимости от политики, можно либо завершить приложение, либо работать без БД (если возможно)
        raise # Перевыбрасываем ошибку, чтобы приложение не стартовало с неработающей БД

# Пример функции, которая будет вызываться в main.py при остановке бота
async def shutdown_database_on_shutdown():
    """Закрывает пул соединений к БД при остановке приложения."""
    await close_db_pool()



async def _test_db_operations():
    logging.basicConfig(level=logging.INFO)
    await setup_database_on_startup()

    # Тест пользователя
    user = await add_or_update_user(12345, "testuser", "Test", "User", "ru")
    print("User:", user)
    profile = await get_user_profile(12345)
    print("Profile:", profile)
    await update_user_custom_data(12345, {"address": "Test Street 1", "city": "Testville"})
    profile_updated = await get_user_profile(12345)
    print("Profile Updated Custom Data:", profile_updated)

    # Тест заметки
    note_id = await create_note(
        telegram_id=12345,
        corrected_text="Это тестовая заметка после LLM.",
        original_stt_text="Эта тиставая замитка после СТТ.",
        llm_analysis_json={"intent": "general_note", "entities": ["тест"]},
        due_date=datetime.now(timezone.utc) + timedelta(days=1)
    )
    print(f"Created note_id: {note_id}")

    if note_id:
        notes = await get_notes_by_user(12345)
        print("User Notes:", notes)
        note_detail = await get_note_by_id(note_id, 12345)
        print("Note Detail:", note_detail)
        await update_note_text(note_id, 12345, "Обновленный текст тестовой заметки.")
        note_detail_updated = await get_note_by_id(note_id, 12345)
        print("Note Detail Updated:", note_detail_updated)
        # await delete_note(note_id, 12345)
        # print(f"Note {note_id} deleted status: {await get_note_by_id(note_id, 12345) is None}")

    await shutdown_database_on_shutdown()

if __name__ == "__main__":
    # Установите переменные окружения для БД перед запуском
    # DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
    # Например:
    # export DB_USER="your_db_user"
    # export DB_PASSWORD="your_db_password"
    # ...
    # Убедитесь, что база данных DB_NAME существует в вашем PostgreSQL
    import asyncio
    asyncio.run(_test_db_operations())