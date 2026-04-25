"""V2 billing — auto_renew + payment_method_id на subscriptions.

YooKassa-«подписки» = recurring charge через сохранённый payment_method.
Чтобы фоновый job знал какой метод дёргать и нужно ли вообще, добавляем
два поля.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column(
            "auto_renew",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "subscriptions",
        sa.Column("payment_method_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "payment_method_id")
    op.drop_column("subscriptions", "auto_renew")
