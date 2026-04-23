"""AiUsage — docs/PRODUCT_PLAN.md §18.4.

Лог каждого вызова LLMRouter/STTRouter для Grafana-дашборда «AI economy» (§18.3)
и детекции абьюза в cost-ceiling-слое (§18.2).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class AiUsage(Base):
    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )

    task: Mapped[str] = mapped_column(String(32), nullable=False)
    # 'facet_extract' | 'agent_ask' | 'stt_server' | ...
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # 'deepseek' | 'claude-haiku' | 'salute' | ...

    input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    audio_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    cost_rub: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
