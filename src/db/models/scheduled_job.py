"""ScheduledJob — docs/PRODUCT_PLAN.md §4.8.

Дублирует состояние APScheduler для аудита и восстановления после рестарта.
Настоящие джобы живут в APScheduler-job-store (Memory для MVP, см. §3).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    # id — строковый, формата "moment:{id}:remind" | "user:{id}:digest" (см. §4.8)
    id: Mapped[str] = mapped_column(Text, primary_key=True)

    user_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    moment_id: Mapped[Optional[int]] = mapped_column(BigInteger)

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # 'reminder' | 'digest' | 'pre_reminder' | 'habit_check'

    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
