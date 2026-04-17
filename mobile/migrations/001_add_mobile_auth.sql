-- Миграция: добавление email/password аутентификации для мобильного приложения
-- Мобильное приложение работает независимо от Telegram.
-- Для мобильных пользователей генерируется синтетический telegram_id (отрицательные значения),
-- чтобы сохранить совместимость существующей схемы БД, где telegram_id - PK таблицы users.

BEGIN;

-- 1) Добавляем колонки email/password к таблице users.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email          TEXT UNIQUE,
    ADD COLUMN IF NOT EXISTS password_hash  TEXT,
    ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS auth_provider  TEXT NOT NULL DEFAULT 'telegram' -- 'telegram' | 'email'
    ;

CREATE INDEX IF NOT EXISTS idx_users_email ON users (LOWER(email)) WHERE email IS NOT NULL;

-- 2) Последовательность для синтетических telegram_id мобильных пользователей.
--    Используем отрицательные значения, чтобы не пересечься с реальными Telegram ID.
CREATE SEQUENCE IF NOT EXISTS mobile_user_id_seq START WITH 1 INCREMENT BY 1;

-- 3) Таблицы для платежей/подписок/AI-памяти (из ТЗ).
CREATE TABLE IF NOT EXISTS subscriptions (
    id                  BIGSERIAL PRIMARY KEY,
    user_telegram_id    BIGINT NOT NULL REFERENCES users (telegram_id) ON DELETE CASCADE,
    plan                TEXT   NOT NULL CHECK (plan IN ('monthly', 'yearly')),
    status              TEXT   NOT NULL CHECK (status IN ('active', 'cancelled', 'expired', 'pending')),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL,
    auto_renew          BOOLEAN NOT NULL DEFAULT TRUE,
    cancelled_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions (user_telegram_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_active ON subscriptions (status, expires_at);

CREATE TABLE IF NOT EXISTS payments (
    id                    BIGSERIAL PRIMARY KEY,
    yookassa_payment_id   TEXT UNIQUE NOT NULL,
    user_telegram_id      BIGINT NOT NULL REFERENCES users (telegram_id) ON DELETE CASCADE,
    amount                NUMERIC(12, 2) NOT NULL,
    currency              TEXT   NOT NULL DEFAULT 'RUB',
    status                TEXT   NOT NULL,
    plan                  TEXT   NOT NULL,
    metadata              JSONB  NOT NULL DEFAULT '{}'::jsonb,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payments_user ON payments (user_telegram_id);

-- 4) pgvector (опционально, если расширение доступно)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS note_embeddings (
    note_id        BIGINT PRIMARY KEY REFERENCES notes (note_id) ON DELETE CASCADE,
    embedding      vector(1536) NOT NULL,
    model_version  TEXT NOT NULL DEFAULT 'text-embedding-3-small',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_note_embeddings_hnsw
    ON note_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id                BIGSERIAL PRIMARY KEY,
    user_telegram_id  BIGINT NOT NULL REFERENCES users (telegram_id) ON DELETE CASCADE,
    role              TEXT   NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content           TEXT   NOT NULL,
    context_note_ids  BIGINT[] NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_conversations_user ON ai_conversations (user_telegram_id, created_at DESC);

CREATE TABLE IF NOT EXISTS user_memory_facts (
    id                BIGSERIAL PRIMARY KEY,
    user_telegram_id  BIGINT NOT NULL REFERENCES users (telegram_id) ON DELETE CASCADE,
    fact_text         TEXT   NOT NULL,
    source_type       TEXT   NOT NULL, -- 'note' | 'chat' | 'manual'
    embedding         vector(1536),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_memory_facts_user ON user_memory_facts (user_telegram_id);
CREATE INDEX IF NOT EXISTS idx_user_memory_facts_hnsw
    ON user_memory_facts USING hnsw (embedding vector_cosine_ops);

COMMIT;
