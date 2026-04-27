"""Moment — docs/PRODUCT_PLAN.md §4.1 + §4.2.

Единственная сущность продукта: все заметки/напоминания/привычки/покупки/ДР
— это moments с различными ``facets.kind`` и наличием ``occurs_at`` / ``rrule``.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base

# Размерность multilingual-e5-small (self-hosted CPU). M3 BGE-M3 = 1024 — апгрейд позже.
EMBEDDING_DIM = 384


class Moment(Base):
    __tablename__ = "moments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- Сырые данные ---
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    # 'voice' | 'text' | 'forward' | 'alice' | 'manual'
    audio_url: Mapped[Optional[str]] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8), server_default="ru")

    # --- Структурированные данные от LLM ---
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    facets: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # --- Временные грани (дублируют facets для индексов) ---
    occurs_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rrule: Mapped[Optional[str]] = mapped_column(Text)
    rrule_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # --- Статус ---
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="active"
    )  # 'active' | 'done' | 'archived' | 'trashed'
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # --- Эмбеддинг (BGE-M3, self-hosted, §6.0 / §6.7.6) ---
    embedding: Mapped[Optional[Any]] = mapped_column(Vector(EMBEDDING_DIM))

    # --- Метаданные ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    created_via: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="mobile"
    )  # 'mobile' | 'bot' | 'alice' | 'system'
    llm_version: Mapped[Optional[str]] = mapped_column(String(64))
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), unique=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Moment id={self.id} user={self.user_id} title={self.title!r}>"
