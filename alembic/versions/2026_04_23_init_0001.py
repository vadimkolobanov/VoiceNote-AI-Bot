"""V1 init — новая схема v1.0 (docs/PRODUCT_PLAN.md §4)

Создаёт 9 таблиц целевой архитектуры: users, moments, facts, agent_messages,
subscriptions, push_tokens, scheduled_jobs, ai_usage, refresh_tokens. Плюс
pgvector extension и все индексы из §4.1.

Legacy-таблицы (notes/reminders/habits/...) не трогаются — с ними работает
V2__import_legacy, который запускается отдельно после смоук-теста V1.

Revision ID: 0001
Revises:
Create Date: 2026-04-23
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EMBEDDING_DIM = 1024


def upgrade() -> None:
    # --- pgvector extension (требуется для Vector колонок) ---
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- users (§4.3) ---
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="Europe/Moscow",
        ),
        sa.Column(
            "locale", sa.String(length=8), nullable=False, server_default="ru"
        ),
        sa.Column("digest_hour", sa.SmallInteger(), server_default="8"),
        sa.Column("pro_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )

    # --- moments (§4.1) ---
    op.create_table(
        "moments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_moments_user_id_users"),
            nullable=False,
        ),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("audio_url", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=8), server_default="ru"),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "facets",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("occurs_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rrule", sa.Text(), nullable=True),
        sa.Column("rrule_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="active",
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_via",
            sa.String(length=16),
            nullable=False,
            server_default="mobile",
        ),
        sa.Column("llm_version", sa.String(length=64), nullable=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("client_id", name="uq_moments_client_id"),
    )

    # Индексы moments (§4.1)
    op.execute(
        "CREATE INDEX idx_moments_user_occurs ON moments(user_id, occurs_at) "
        "WHERE status='active'"
    )
    op.create_index(
        "idx_moments_user_created",
        "moments",
        ["user_id", sa.text("created_at DESC")],
    )
    op.execute(
        "CREATE INDEX idx_moments_user_rrule ON moments(user_id) "
        "WHERE rrule IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_moments_facets_gin ON moments USING gin(facets)"
    )
    op.execute(
        "CREATE INDEX idx_moments_embedding ON moments "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    # FK-индекс на user_id (не покрывается частичным indexes выше)
    op.create_index("ix_moments_user_id", "moments", ["user_id"])

    # --- facts (§4.4) ---
    op.create_table(
        "facts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_facts_user_id_users"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column(
            "value", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "confidence", sa.Float(), nullable=False, server_default="0.5"
        ),
        sa.Column(
            "source_moment_ids",
            postgresql.ARRAY(sa.BigInteger()),
            nullable=False,
            server_default=sa.text("'{}'::bigint[]"),
        ),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "kind", "key", name="uq_facts_user_kind_key"),
    )
    op.create_index("ix_facts_user_id", "facts", ["user_id"])

    # --- agent_messages (§4.5) ---
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "users.id", ondelete="CASCADE", name="fk_agent_messages_user_id_users"
            ),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("cited_moment_ids", postgresql.ARRAY(sa.BigInteger()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_agent_msgs_user", "agent_messages", ["user_id", "created_at"]
    )

    # --- subscriptions (§4.6) ---
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", name="fk_subscriptions_user_id_users"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("plan", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("external_id", name="uq_subscriptions_external_id"),
    )

    # --- push_tokens (§4.7) ---
    op.create_table(
        "push_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "users.id", ondelete="CASCADE", name="fk_push_tokens_user_id_users"
            ),
            nullable=False,
        ),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "token", name="uq_push_tokens_user_token"),
    )

    # --- scheduled_jobs (§4.8) ---
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("moment_id", sa.BigInteger(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- ai_usage (§18.4) ---
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", name="fk_ai_usage_user_id_users"),
            nullable=True,
        ),
        sa.Column("task", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("audio_seconds", sa.Integer(), nullable=True),
        sa.Column("cost_rub", sa.Numeric(10, 4), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_ai_usage_user_day", "ai_usage", ["user_id", "created_at"])
    op.create_index("idx_ai_usage_task_day", "ai_usage", ["task", "created_at"])

    # --- refresh_tokens (supports §5.2 JWT refresh flow) ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "users.id", ondelete="CASCADE", name="fk_refresh_tokens_user_id_users"
            ),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("idx_ai_usage_task_day", table_name="ai_usage")
    op.drop_index("idx_ai_usage_user_day", table_name="ai_usage")
    op.drop_table("ai_usage")

    op.drop_table("scheduled_jobs")

    op.drop_table("push_tokens")

    op.drop_table("subscriptions")

    op.drop_index("idx_agent_msgs_user", table_name="agent_messages")
    op.drop_table("agent_messages")

    op.drop_index("ix_facts_user_id", table_name="facts")
    op.drop_table("facts")

    op.drop_index("ix_moments_user_id", table_name="moments")
    op.execute("DROP INDEX IF EXISTS idx_moments_embedding")
    op.execute("DROP INDEX IF EXISTS idx_moments_facets_gin")
    op.execute("DROP INDEX IF EXISTS idx_moments_user_rrule")
    op.drop_index("idx_moments_user_created", table_name="moments")
    op.execute("DROP INDEX IF EXISTS idx_moments_user_occurs")
    op.drop_table("moments")

    op.drop_table("users")

    # pgvector extension не удаляется — другие миграции/другие схемы могут её
    # использовать. Оставляем.
