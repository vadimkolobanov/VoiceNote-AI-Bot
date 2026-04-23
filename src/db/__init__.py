"""Новый слой БД на SQLAlchemy 2.0 (async).

Старые прямо-asyncpg репозитории в ``src/database/*`` остаются в переходном
состоянии до M2: они обслуживают legacy-код, который уже не вызывается после
удаления bot-модулей. Вся новая функциональность (moments, auth, agent, facts,
billing, push) работает исключительно через этот пакет.

Структура:
    base        — Declarative ``Base`` + единые конвенции имён.
    session     — async engine + session factory + FastAPI dependency.
    models/*    — ORM-модели по спецификации docs/PRODUCT_PLAN.md §4.
"""

from .base import Base  # noqa: F401
from .session import (  # noqa: F401
    AsyncSessionLocal,
    async_engine,
    get_session,
    init_engine,
    shutdown_engine,
)
