"""HabitCompletion — отметка выполнения привычки за конкретный день.

Привычка (`Moment.rrule is not None`) не имеет терминального состояния:
выполнена «на сегодня», завтра снова в списке. Каждое нажатие «Выполнить»
вставляет строку. UNIQUE(moment_id, completed_on) — идемпотентность.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class HabitCompletion(Base):
    __tablename__ = "habit_completions"
    __table_args__ = (
        UniqueConstraint("moment_id", "completed_on", name="uq_habit_completion_day"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    moment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("moments.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    completed_on: Mapped[date] = mapped_column(Date, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
