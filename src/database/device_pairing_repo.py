"""
Unified device pairing codes (Phase 5).

Заменяет mobile_activation_codes + users.alice_activation_code и готовит почву
для будущих каналов входа (Telegram login code, Госуслуги, MAX, email).

Старые таблицы/колонки пока остаются (deprecated) чтобы не ломать бот. Новый
код работает ТОЛЬКО с этой таблицей.
"""
from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone

from .connection import get_db_pool

logger = logging.getLogger(__name__)

CODE_ALPHABET = string.ascii_uppercase + string.digits
DEFAULT_TTL_MINUTES = 15


def _generate_code(length: int = 6) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


async def create_pairing(
    *,
    user_telegram_id: int,
    platform: str,
    ttl_minutes: int = DEFAULT_TTL_MINUTES,
    device_metadata: dict | None = None,
    length: int = 6,
) -> dict:
    """Issue a new pairing code for a user on a given platform.

    Returns a dict with `code`, `expires_at`, `platform`.
    """
    pool = await get_db_pool()
    expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    # In the extremely unlikely event of a collision retry a few times.
    async with pool.acquire() as conn:
        for _ in range(5):
            code = _generate_code(length)
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO device_pairings (user_telegram_id, platform, code, expires_at,
                                                 device_metadata)
                    VALUES ($1, $2, $3, $4, $5::jsonb)
                    RETURNING code, expires_at, platform
                    """,
                    user_telegram_id, platform, code, expires,
                    _dumps(device_metadata or {}),
                )
                return dict(row)
            except Exception as e:
                logger.warning("device_pairings code collision, retrying: %s", e)
                continue
    raise RuntimeError("Не удалось сгенерировать уникальный код сопряжения")


async def consume_pairing(platform: str, code: str) -> int | None:
    """Пытается потребить код. Возвращает telegram_id пользователя или None."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, user_telegram_id, expires_at, consumed_at
                FROM device_pairings
                WHERE platform = $1 AND UPPER(code) = UPPER($2)
                FOR UPDATE
                """,
                platform, code.strip(),
            )
            if row is None or row["consumed_at"] is not None:
                return None
            if row["expires_at"] < datetime.now(timezone.utc):
                return None
            await conn.execute(
                "UPDATE device_pairings SET consumed_at = NOW() WHERE id = $1",
                row["id"],
            )
            return int(row["user_telegram_id"])


async def revoke_user_pairings(user_telegram_id: int, platform: str | None = None) -> int:
    """Marks all unused pairings as consumed (admin/user-initiated revoke)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if platform is None:
            result = await conn.execute(
                """
                UPDATE device_pairings
                SET consumed_at = NOW()
                WHERE user_telegram_id = $1 AND consumed_at IS NULL
                """,
                user_telegram_id,
            )
        else:
            result = await conn.execute(
                """
                UPDATE device_pairings
                SET consumed_at = NOW()
                WHERE user_telegram_id = $1 AND platform = $2 AND consumed_at IS NULL
                """,
                user_telegram_id, platform,
            )
    return int(result.split(" ")[1])


def _dumps(v: dict) -> str:
    import json
    return json.dumps(v)
