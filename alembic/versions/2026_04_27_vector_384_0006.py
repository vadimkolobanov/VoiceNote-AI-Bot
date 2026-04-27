"""V6 vector dim 256 → 384: переключение на self-hosted multilingual-e5-small.

Yandex Foundation Models embeddings требуют отдельный ключ (SpeechKit-ключ
не подходит). Чтобы не блокировать развитие, перешли на fastembed/onnx
с моделью intfloat/multilingual-e5-small (384d, CPU, без ключей).

Колонки на момент V6 пусты (V5 ничего не записывал) → ALTER безопасен.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-27
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE moments ALTER COLUMN embedding TYPE vector(384)")
    op.execute("ALTER TABLE facts ALTER COLUMN embedding TYPE vector(384)")


def downgrade() -> None:
    op.execute("ALTER TABLE moments ALTER COLUMN embedding TYPE vector(256)")
    op.execute("ALTER TABLE facts ALTER COLUMN embedding TYPE vector(256)")
