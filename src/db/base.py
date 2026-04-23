"""Декларативная база SQLAlchemy с единой конвенцией имён констрейнтов.

Конвенции имён важны для alembic autogenerate: без них генератор каждый раз
пересоздаёт индексы/констрейнты, потому что не может сопоставить БД и модели.
"""
from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Конвенция имён — см. https://alembic.sqlalchemy.org/en/latest/naming.html
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей проекта."""

    metadata = metadata
