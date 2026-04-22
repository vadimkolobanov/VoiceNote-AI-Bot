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
    """
    CREATE TABLE IF NOT EXISTS habits (
        id SERIAL PRIMARY KEY,
        user_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        description TEXT,
        frequency_rule TEXT NOT NULL,
        reminder_time TIME,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        is_active BOOLEAN DEFAULT TRUE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS habit_trackings (
        id SERIAL PRIMARY KEY,
        habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
        user_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        track_date DATE NOT NULL,
        status TEXT NOT NULL,
        tracked_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(habit_id, track_date)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_topic_settings (
        id SERIAL PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        topic_id INTEGER NOT NULL,
        function_type TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(chat_id, topic_id, function_type)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS refresh_tokens (
        id SERIAL PRIMARY KEY,
        token_hash TEXT UNIQUE NOT NULL,
        user_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        expires_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        revoked_at TIMESTAMPTZ
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);",
    "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_telegram_id);",
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
    "CREATE INDEX IF NOT EXISTS idx_habits_user_id ON habits(user_telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_habit_trackings_habit_id ON habit_trackings(habit_id);",
    "CREATE INDEX IF NOT EXISTS idx_chat_topic_settings_chat_topic ON chat_topic_settings(chat_id, topic_id);",

    # --- Mobile auth (email/password) ---
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='email') THEN
            ALTER TABLE users ADD COLUMN email TEXT UNIQUE;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='password_hash') THEN
            ALTER TABLE users ADD COLUMN password_hash TEXT;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='email_verified') THEN
            ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='auth_provider') THEN
            ALTER TABLE users ADD COLUMN auth_provider TEXT NOT NULL DEFAULT 'telegram';
        END IF;
    END;
    $$;
    """,
    "CREATE INDEX IF NOT EXISTS idx_users_email ON users (LOWER(email)) WHERE email IS NOT NULL;",
    "CREATE SEQUENCE IF NOT EXISTS mobile_user_id_seq START WITH 1 INCREMENT BY 1;",

    # --- Mobile subscriptions & payments (YooKassa) ---
    # Префикс `mobile_` чтобы не конфликтовать с существующими таблицами бота.
    """
    CREATE TABLE IF NOT EXISTS mobile_subscriptions (
        id BIGSERIAL PRIMARY KEY,
        user_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        plan TEXT NOT NULL CHECK (plan IN ('monthly','yearly')),
        status TEXT NOT NULL CHECK (status IN ('active','cancelled','expired','pending')),
        started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMPTZ NOT NULL,
        auto_renew BOOLEAN NOT NULL DEFAULT TRUE,
        cancelled_at TIMESTAMPTZ
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_mobile_subscriptions_user ON mobile_subscriptions (user_telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_mobile_subscriptions_active ON mobile_subscriptions (status, expires_at);",
    """
    CREATE TABLE IF NOT EXISTS mobile_payments (
        id BIGSERIAL PRIMARY KEY,
        yookassa_payment_id TEXT UNIQUE NOT NULL,
        user_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
        amount NUMERIC(12,2) NOT NULL,
        currency TEXT NOT NULL DEFAULT 'RUB',
        status TEXT NOT NULL,
        plan TEXT NOT NULL,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_mobile_payments_user ON mobile_payments (user_telegram_id);",

    # --- Phase 1: shopping lists as first-class entity ---
    """
    CREATE TABLE IF NOT EXISTS shopping_lists (
        id           BIGSERIAL PRIMARY KEY,
        owner_id     BIGINT NOT NULL REFERENCES users (telegram_id) ON DELETE CASCADE,
        title        TEXT   NOT NULL DEFAULT 'Список покупок',
        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        archived_at  TIMESTAMPTZ,
        legacy_note_id BIGINT UNIQUE  -- pointer to the original notes row we migrated from
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_shopping_lists_owner ON shopping_lists (owner_id);",
    "CREATE INDEX IF NOT EXISTS idx_shopping_lists_active ON shopping_lists (owner_id) WHERE archived_at IS NULL;",

    """
    CREATE TABLE IF NOT EXISTS shopping_list_items (
        id          BIGSERIAL PRIMARY KEY,
        list_id     BIGINT NOT NULL REFERENCES shopping_lists (id) ON DELETE CASCADE,
        name        TEXT   NOT NULL,
        quantity    TEXT,                          -- '1 кг', '2 шт' и т.п., опционально
        position    INTEGER NOT NULL DEFAULT 0,    -- порядок в списке
        checked_at  TIMESTAMPTZ,
        checked_by  BIGINT REFERENCES users (telegram_id) ON DELETE SET NULL,
        added_by    BIGINT NOT NULL REFERENCES users (telegram_id) ON DELETE CASCADE,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_shopping_items_list ON shopping_list_items (list_id, position);",

    """
    CREATE TABLE IF NOT EXISTS shopping_list_members (
        list_id    BIGINT NOT NULL REFERENCES shopping_lists (id) ON DELETE CASCADE,
        user_id    BIGINT NOT NULL REFERENCES users (telegram_id) ON DELETE CASCADE,
        role       TEXT   NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'member')),
        joined_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (list_id, user_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_shopping_members_user ON shopping_list_members (user_id);",

    """
    CREATE TABLE IF NOT EXISTS shopping_list_invites (
        id          BIGSERIAL PRIMARY KEY,
        list_id     BIGINT NOT NULL REFERENCES shopping_lists (id) ON DELETE CASCADE,
        code        TEXT   NOT NULL UNIQUE,          -- 6-символьный код
        created_by  BIGINT NOT NULL REFERENCES users (telegram_id) ON DELETE CASCADE,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        expires_at  TIMESTAMPTZ NOT NULL,
        consumed_at TIMESTAMPTZ,
        consumed_by BIGINT REFERENCES users (telegram_id) ON DELETE SET NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_shopping_invites_code ON shopping_list_invites (code) WHERE consumed_at IS NULL;",

    # --- Phase 2: notes typing ---
    # Добавляем строгий enum type: 'note' (обычная), 'task' (с due_date),
    # 'reminder' (одноразовое напоминание), 'idea'. category остаётся для обратной
    # совместимости с ботом, но теперь это free-form подсказка, а не источник правды.
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='notes' AND column_name='type') THEN
            ALTER TABLE notes ADD COLUMN type TEXT;
            -- Backfill на основе существующих данных:
            UPDATE notes SET type =
                CASE
                    WHEN due_date IS NOT NULL THEN 'task'
                    WHEN LOWER(COALESCE(category, '')) LIKE 'задач%' THEN 'task'
                    WHEN LOWER(COALESCE(category, '')) LIKE 'напомин%' THEN 'task'
                    WHEN LOWER(COALESCE(category, '')) LIKE 'иде%' THEN 'idea'
                    WHEN LOWER(COALESCE(category, '')) LIKE 'покуп%' THEN 'shopping'
                    ELSE 'note'
                END
            WHERE type IS NULL;
            ALTER TABLE notes ALTER COLUMN type SET NOT NULL;
            ALTER TABLE notes ALTER COLUMN type SET DEFAULT 'note';
        END IF;
        -- Добавляем CHECK constraint только если ещё нет
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE constraint_name = 'notes_type_check' AND table_name = 'notes'
        ) THEN
            ALTER TABLE notes ADD CONSTRAINT notes_type_check
                CHECK (type IN ('note', 'task', 'idea', 'shopping'));
        END IF;
    END $$;
    """,
    "CREATE INDEX IF NOT EXISTS idx_notes_type ON notes (telegram_id, type, is_archived);",
    "CREATE INDEX IF NOT EXISTS idx_notes_due_date_task ON notes (telegram_id, due_date) WHERE type = 'task' AND is_archived = FALSE AND is_completed = FALSE;",

    # --- Phase 3a: unified reminders read-model ---
    # Polymorphic таблица напоминаний. entity_type указывает на источник
    # (note | habit | birthday), entity_id — ID в соответствующей таблице.
    # FK намеренно нет (polymorphic). Синхронизацию поддерживает приложение:
    # bootstrap-миграция при старте + sync-hooks в repo/scheduler.
    """
    CREATE TABLE IF NOT EXISTS reminders (
        id                    BIGSERIAL PRIMARY KEY,
        user_id               BIGINT NOT NULL REFERENCES users (telegram_id) ON DELETE CASCADE,
        entity_type           TEXT   NOT NULL CHECK (entity_type IN ('note', 'habit', 'birthday')),
        entity_id             BIGINT NOT NULL,
        title                 TEXT   NOT NULL,
        rrule                 TEXT,                                -- NULL = one-shot
        dtstart               TIMESTAMPTZ NOT NULL,
        next_fire_at          TIMESTAMPTZ,
        last_fired_at         TIMESTAMPTZ,
        pre_reminder_minutes  INTEGER NOT NULL DEFAULT 0,
        status                TEXT   NOT NULL DEFAULT 'active'
                               CHECK (status IN ('active', 'paused', 'completed')),
        created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (entity_type, entity_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_reminders_fire ON reminders (next_fire_at) WHERE status = 'active';",
    "CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders (user_id, status);",

    # --- Phase 5: unified device pairings ---
    # Единая таблица одноразовых кодов для сопряжения устройств / каналов входа.
    # Заменяет mobile_activation_codes и users.alice_activation_code.
    # platform: 'telegram' | 'alice' | 'mobile_app' | 'gosuslugi' | 'max'
    """
    CREATE TABLE IF NOT EXISTS device_pairings (
        id                BIGSERIAL PRIMARY KEY,
        user_telegram_id  BIGINT NOT NULL REFERENCES users (telegram_id) ON DELETE CASCADE,
        platform          TEXT   NOT NULL CHECK (platform IN (
                              'telegram', 'alice', 'mobile_app', 'gosuslugi', 'max', 'email'
                          )),
        code              TEXT   NOT NULL,
        expires_at        TIMESTAMPTZ NOT NULL,
        consumed_at       TIMESTAMPTZ,
        device_metadata   JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (platform, code)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_device_pairings_user ON device_pairings (user_telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_device_pairings_code_active ON device_pairings (platform, code) WHERE consumed_at IS NULL;",
]


# --- Phase 5: backfill device_pairings from legacy tables ---
DEVICE_PAIRINGS_BACKFILL_STATEMENT = """
INSERT INTO device_pairings (user_telegram_id, platform, code, expires_at, consumed_at, created_at)
SELECT telegram_id, 'mobile_app', code, expires_at, NULL, NOW()
FROM mobile_activation_codes
WHERE expires_at > NOW() - INTERVAL '30 days'
ON CONFLICT (platform, code) DO NOTHING;

INSERT INTO device_pairings (user_telegram_id, platform, code, expires_at, consumed_at, created_at)
SELECT telegram_id, 'alice', alice_activation_code, alice_code_expires_at, NULL, NOW()
FROM users
WHERE alice_activation_code IS NOT NULL
  AND alice_code_expires_at IS NOT NULL
  AND alice_code_expires_at > NOW() - INTERVAL '30 days'
ON CONFLICT (platform, code) DO NOTHING;
"""


# --- Phase 3a: one-time backfill of reminders from notes/habits/birthdays ---
# Idempotent: полагается на UNIQUE (entity_type, entity_id).
REMINDERS_BACKFILL_STATEMENT = """
-- Заметки с due_date -> reminders (one-shot или recurring)
INSERT INTO reminders (user_id, entity_type, entity_id, title, rrule,
                       dtstart, next_fire_at, pre_reminder_minutes, status)
SELECT
    n.telegram_id,
    'note',
    n.note_id,
    COALESCE(NULLIF(n.summary_text, ''), LEFT(n.corrected_text, 120)),
    n.recurrence_rule,
    n.due_date,
    CASE
        WHEN n.is_archived OR n.is_completed THEN NULL
        WHEN n.due_date < NOW() AND n.recurrence_rule IS NULL THEN NULL
        ELSE n.due_date
    END,
    COALESCE(u.pre_reminder_minutes, 0),
    CASE
        WHEN n.is_archived OR n.is_completed THEN 'completed'
        WHEN n.due_date < NOW() AND n.recurrence_rule IS NULL THEN 'completed'
        ELSE 'active'
    END
FROM notes n
JOIN users u ON u.telegram_id = n.telegram_id
WHERE n.due_date IS NOT NULL
ON CONFLICT (entity_type, entity_id) DO NOTHING;

-- Привычки -> reminders
INSERT INTO reminders (user_id, entity_type, entity_id, title, rrule,
                       dtstart, next_fire_at, status)
SELECT
    h.user_telegram_id,
    'habit',
    h.id,
    h.name,
    h.frequency_rule,
    -- dtstart берём как created_at (без времени — пусть scheduler сам разберёт)
    h.created_at,
    NULL,                                 -- вычислит scheduler / repo при следующем старте
    CASE WHEN h.is_active THEN 'active' ELSE 'paused' END
FROM habits h
ON CONFLICT (entity_type, entity_id) DO NOTHING;

-- Дни рождения -> reminders (RRULE=YEARLY)
INSERT INTO reminders (user_id, entity_type, entity_id, title, rrule,
                       dtstart, next_fire_at, status)
SELECT
    b.user_telegram_id,
    'birthday',
    b.id,
    b.person_name,
    'FREQ=YEARLY;BYMONTH=' || b.birth_month::text || ';BYMONTHDAY=' || b.birth_day::text,
    -- dtstart — ближайшая дата рождения в будущем либо сегодня
    (date_trunc('day', NOW()))::timestamptz,
    NULL,
    'active'
FROM birthdays b
ON CONFLICT (entity_type, entity_id) DO NOTHING;
"""


# --- One-time data migration: notes with category='Покупки' → shopping_lists ---
# Выполняется отдельно (не в CREATE_AND_UPDATE_TABLES_STATEMENTS), один раз,
# после того как таблицы созданы.
SHOPPING_MIGRATION_STATEMENT = """
DO $$
DECLARE
    rec RECORD;
    new_list_id BIGINT;
    item_rec JSONB;
    pos INT;
BEGIN
    -- 1) Создаём shopping_lists из notes с категорией "покупки" (любой регистр)
    FOR rec IN
        SELECT n.note_id,
               n.telegram_id,
               COALESCE(NULLIF(n.summary_text, ''), 'Список покупок') AS title,
               n.created_at,
               n.is_archived,
               n.updated_at,
               COALESCE(n.llm_analysis_json -> 'items', '[]'::jsonb) AS items
        FROM notes n
        WHERE LOWER(n.category) LIKE 'покуп%'
          AND NOT EXISTS (
              SELECT 1 FROM shopping_lists sl WHERE sl.legacy_note_id = n.note_id
          )
    LOOP
        INSERT INTO shopping_lists (owner_id, title, created_at, archived_at, legacy_note_id)
        VALUES (
            rec.telegram_id,
            rec.title,
            rec.created_at,
            CASE WHEN rec.is_archived THEN COALESCE(rec.updated_at, NOW()) ELSE NULL END,
            rec.note_id
        )
        RETURNING id INTO new_list_id;

        -- Owner → member с role='owner'
        INSERT INTO shopping_list_members (list_id, user_id, role, joined_at)
        VALUES (new_list_id, rec.telegram_id, 'owner', rec.created_at)
        ON CONFLICT DO NOTHING;

        -- 2) Товары из llm_analysis_json.items -> shopping_list_items
        pos := 0;
        FOR item_rec IN SELECT * FROM jsonb_array_elements(rec.items)
        LOOP
            INSERT INTO shopping_list_items (
                list_id, name, quantity, position,
                checked_at, checked_by, added_by, created_at
            )
            VALUES (
                new_list_id,
                COALESCE(item_rec ->> 'item_name', item_rec ->> 'name', 'Без названия'),
                item_rec ->> 'quantity',
                pos,
                CASE WHEN COALESCE((item_rec ->> 'checked')::boolean, FALSE)
                     THEN rec.updated_at ELSE NULL END,
                CASE WHEN COALESCE((item_rec ->> 'checked')::boolean, FALSE)
                     THEN (item_rec ->> 'added_by')::BIGINT ELSE NULL END,
                COALESCE((item_rec ->> 'added_by')::BIGINT, rec.telegram_id),
                rec.created_at
            );
            pos := pos + 1;
        END LOOP;

        -- 3) Участников из note_shares
        INSERT INTO shopping_list_members (list_id, user_id, role, joined_at)
        SELECT new_list_id, ns.shared_with_telegram_id, 'member', ns.created_at
        FROM note_shares ns
        WHERE ns.note_id = rec.note_id
        ON CONFLICT DO NOTHING;
    END LOOP;
END $$;
"""


db_pool: asyncpg.Pool | None = None


async def get_db_pool() -> asyncpg.Pool:
    """Возвращает существующий пул соединений или создает новый."""
    global db_pool
    if db_pool is None or db_pool.is_closing():
        try:
            db_pool = await asyncpg.create_pool(dsn=DATABASE_URL, min_size=2, max_size=10, ssl=False)
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

            # Idempotent: переносит notes с категорией "Покупки" в shopping_lists,
            # затем следующие запуски скипают их через legacy_note_id UNIQUE constraint.
            logger.info("Миграция списков покупок из notes в shopping_lists...")
            try:
                await connection.execute(SHOPPING_MIGRATION_STATEMENT)
            except Exception as e:
                logger.error("Миграция shopping_lists провалилась: %s", e, exc_info=True)
                raise

            # Phase 3a: backfill единой таблицы reminders из notes/habits/birthdays
            logger.info("Синхронизация таблицы reminders из существующих источников...")
            try:
                await connection.execute(REMINDERS_BACKFILL_STATEMENT)
            except Exception as e:
                logger.error("Backfill reminders провалился: %s", e, exc_info=True)
                raise

            # Phase 5: backfill device_pairings
            logger.info("Миграция кодов сопряжения в device_pairings...")
            try:
                await connection.execute(DEVICE_PAIRINGS_BACKFILL_STATEMENT)
            except Exception as e:
                logger.error("Backfill device_pairings провалился: %s", e, exc_info=True)
                raise

            logger.info("Схема базы данных актуальна.")


async def setup_database_on_startup():
    """Выполняется при запуске приложения для инициализации БД."""
    await init_db()


async def shutdown_database_on_shutdown():
    """Выполняется при остановке приложения для закрытия пула соединений."""
    await close_db_pool()