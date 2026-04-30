"""V7 utility-колонки: pre_reminder_minutes на user + last_digest_sent_on.

- ``users.pre_reminder_minutes`` — за сколько минут до ``moments.occurs_at``
  слать пуш. NULL/0 = ровно в момент. Поддерживаемые значения через UI:
  0/5/10/15/30/60 — но БД хранит любое неотрицательное число.
- ``users.last_digest_sent_on`` — дата (в TZ юзера) последней отправленной
  утренней сводки. Используется в scheduler, чтобы не слать дайджест дважды.

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-28
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "pre_reminder_minutes",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column("last_digest_sent_on", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_digest_sent_on")
    op.drop_column("users", "pre_reminder_minutes")
