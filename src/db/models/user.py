"""User — docs/PRODUCT_PLAN.md §4.3.

Единая сущность для mobile-пользователей (email/password) и legacy-пользователей
бота (telegram_id). Для mobile-only ``telegram_id`` = NULL; для bot-only
``email`` = NULL. Флаг ``is_pro`` не хранится — вычисляется из ``pro_until``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # --- Идентификация ---
    email: Mapped[Optional[str]] = mapped_column(String(320), unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))  # argon2id
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True)

    # --- Профиль ---
    display_name: Mapped[Optional[str]] = mapped_column(String(128))
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="Europe/Moscow"
    )
    locale: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default="ru"
    )
    digest_hour: Mapped[Optional[int]] = mapped_column(SmallInteger, server_default="8")

    # --- Подписка ---
    pro_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # --- Метаданные ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def is_pro(self, now: Optional[datetime] = None) -> bool:
        """Истина, если у пользователя активная Pro-подписка в момент ``now``."""
        if self.pro_until is None:
            return False
        ref = now or datetime.now(self.pro_until.tzinfo)
        return self.pro_until > ref

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r} tg={self.telegram_id}>"
