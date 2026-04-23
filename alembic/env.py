"""Alembic environment (async).

Использует одну и ту же SQLAlchemy metadata, что и runtime (``src.db.Base``),
и тот же DATABASE_URL из ``src.core.config``. В offline-режиме пишет DDL как
plain SQL, в online — подключается к БД через asyncpg.

Команды:
    alembic revision --autogenerate -m "..."    # сгенерить новую миграцию
    alembic upgrade head                         # накатить
    alembic downgrade -1                         # откатить на шаг
"""
from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Делаем src/ импортируемым, чтобы подхватить Base.metadata и DATABASE_URL.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db.base import Base  # noqa: E402
from src.db import models  # noqa: E402,F401  — загружает все модели в Base.metadata
from src.db.session import async_database_url  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ConfigParser у alembic трактует ``%`` как интерполяцию. Удваиваем, чтобы
# URL-encoded пароли (``%3D``, ``%40``) не ломали парсинг.
config.set_main_option("sqlalchemy.url", async_database_url().replace("%", "%%"))

target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to) -> bool:
    """Исключаем legacy-таблицы старого слоя (до миграции §4.9)."""
    legacy = {
        "notes",
        "reminders",
        "habits",
        "habit_entries",
        "shopping_lists",
        "shopping_items",
        "birthdays",
        "user_achievements",
        "achievements",
        "chat_topics",
        "device_pairings",
    }
    if type_ == "table" and name in legacy:
        return False
    return True


def run_migrations_offline() -> None:
    """Генерация SQL без подключения (для вывода в файл)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
