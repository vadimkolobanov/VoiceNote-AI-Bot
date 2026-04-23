"""Subscription — docs/PRODUCT_PLAN.md §4.6.

YooKassa-подписки. ``users.pro_until`` — derived-поле; источник истины — здесь.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # 'yookassa'
    external_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    plan: Mapped[str] = mapped_column(String(32), nullable=False)
    # 'pro_monthly' | 'pro_yearly'
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # 'pending' | 'active' | 'cancelled' | 'failed'

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
