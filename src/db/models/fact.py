"""Fact — docs/PRODUCT_PLAN.md §4.4.

Накопленная ИИ-память о пользователе: люди, места, предпочтения, расписание.
Извлекается только для Pro-юзеров (§6.4), но таблица общая.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from .moment import EMBEDDING_DIM


class Fact(Base):
    __tablename__ = "facts"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "key", name="uq_facts_user_kind_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # 'person' | 'place' | 'preference' | 'schedule' | 'other'
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.5")

    source_moment_ids: Mapped[list[int]] = mapped_column(
        ARRAY(BigInteger), nullable=False, server_default="{}"
    )

    embedding: Mapped[Optional[Any]] = mapped_column(Vector(EMBEDDING_DIM))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
