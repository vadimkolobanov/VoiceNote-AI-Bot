"""V5 vector dim 1024 → 256: переходим на Yandex Foundation Models embeddings.

Изначально схема была заточена под BGE-M3 (1024d, M3 / Hetzner). Но self-hosted
BGE-M3 на паузе, а у юзера уже есть Yandex IAM (text-search-doc — 256d), который
работает прямо сейчас. Когда поднимем M3 — сделаем V_? с обратной миграцией.

На момент V5 в `moments.embedding` и `facts.embedding` нет данных (они никогда
не записывались), поэтому ALTER COLUMN безопасен.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-27
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgvector: ALTER COLUMN ... TYPE vector(N) поддерживается с pgvector 0.5+.
    # Колонки сейчас пусты, так что данных не теряем.
    op.execute("ALTER TABLE moments ALTER COLUMN embedding TYPE vector(256)")
    op.execute("ALTER TABLE facts ALTER COLUMN embedding TYPE vector(256)")


def downgrade() -> None:
    op.execute("ALTER TABLE moments ALTER COLUMN embedding TYPE vector(1024)")
    op.execute("ALTER TABLE facts ALTER COLUMN embedding TYPE vector(1024)")
