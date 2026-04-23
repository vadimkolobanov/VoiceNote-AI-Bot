"""Async engine + session factory + FastAPI dependency.

Используем драйвер asyncpg (он уже в requirements). Для alembic-миграций
предоставляем sync-URL через ту же функцию ``sync_database_url()``, чтобы не
держать две переменные окружения.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import DATABASE_URL

logger = logging.getLogger(__name__)


def async_database_url() -> str:
    """Возвращает DSN в формате ``postgresql+asyncpg://...``.

    ``src.core.config.DATABASE_URL`` исторически имеет схему ``postgresql://``.
    Нормализуем её, чтобы SQLAlchemy подхватил драйвер asyncpg.
    """
    url = DATABASE_URL
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    return url


def sync_database_url() -> str:
    """DSN для alembic (sync-миграции через psycopg/psycopg2-binary)."""
    url = DATABASE_URL
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url[len("postgresql+asyncpg://") :]
    return url


async_engine: AsyncEngine = create_async_engine(
    async_database_url(),
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    autoflush=False,
)


async def init_engine() -> None:
    """Стартовая проверка соединения (использовать в on_startup FastAPI)."""
    from sqlalchemy import text

    async with async_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("PostgreSQL (async) connection established")


async def shutdown_engine() -> None:
    """Закрыть пул соединений (on_shutdown)."""
    await async_engine.dispose()


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: коммитит при успешном ответе, откатывает при ошибке."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
