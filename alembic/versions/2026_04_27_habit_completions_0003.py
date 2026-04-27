"""V3 habit_completions — отметки выполнения для рекуррентных моментов.

Привычка (`moments.rrule != null`) при «Выполнить» не уходит в `done`, а пишет
строку в `habit_completions(moment_id, completed_on)` за конкретный день.
Это позволяет показывать прогресс по привычке день-за-днём, а на завтра она
снова появится в Сегодня как невыполненная.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-27
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "habit_completions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "moment_id",
            sa.BigInteger(),
            sa.ForeignKey("moments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("completed_on", sa.Date(), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("moment_id", "completed_on", name="uq_habit_completion_day"),
    )
    op.create_index(
        "ix_habit_completions_user_day",
        "habit_completions",
        ["user_id", "completed_on"],
    )


def downgrade() -> None:
    op.drop_index("ix_habit_completions_user_day", table_name="habit_completions")
    op.drop_table("habit_completions")
