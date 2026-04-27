"""V4 moments.notified_at — отметка отправленного reminder-push.

Чтобы scheduler не слал один и тот же reminder дважды, ставим timestamp
после успешной отправки FCM-сообщения. NULL = ещё не уведомили.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-27
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "moments",
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_moments_due_reminders",
        "moments",
        ["occurs_at"],
        postgresql_where=sa.text("notified_at IS NULL AND status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("ix_moments_due_reminders", table_name="moments")
    op.drop_column("moments", "notified_at")
