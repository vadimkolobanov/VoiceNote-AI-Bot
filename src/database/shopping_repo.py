"""
Repository for shopping lists (Phase 1 of the post-notes split).

Shopping lists are a first-class entity — independent of `notes`. They own
their items, their members (collaborative shopping), and carry invite codes
for joining from the mobile client without any Telegram dependency.
"""
from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone

from .connection import get_db_pool

logger = logging.getLogger(__name__)


INVITE_TTL = timedelta(days=7)
INVITE_ALPHABET = string.ascii_uppercase + string.digits  # 36^6 = ~2.1 млрд комбинаций
INVITE_LENGTH = 6


# ============================================================
# Lists
# ============================================================

async def list_user_lists(user_id: int, include_archived: bool = False) -> list[dict]:
    """Все списки, где пользователь — участник (owner или member)."""
    pool = await get_db_pool()
    archived_clause = "" if include_archived else "AND sl.archived_at IS NULL"
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT sl.id, sl.owner_id, sl.title, sl.created_at, sl.archived_at,
                   (
                       SELECT COUNT(*) FROM shopping_list_items i WHERE i.list_id = sl.id
                   ) AS items_count,
                   (
                       SELECT COUNT(*) FROM shopping_list_items i
                       WHERE i.list_id = sl.id AND i.checked_at IS NOT NULL
                   ) AS checked_count
            FROM shopping_lists sl
            JOIN shopping_list_members m ON m.list_id = sl.id
            WHERE m.user_id = $1 {archived_clause}
            ORDER BY sl.archived_at NULLS FIRST, sl.created_at DESC
            """,
            user_id,
        )
    return [dict(r) for r in rows]


async def get_list(list_id: int, user_id: int) -> dict | None:
    """Получить список с items и participants — если пользователь участник."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        head = await conn.fetchrow(
            """
            SELECT sl.id, sl.owner_id, sl.title, sl.created_at, sl.archived_at
            FROM shopping_lists sl
            JOIN shopping_list_members m ON m.list_id = sl.id AND m.user_id = $2
            WHERE sl.id = $1
            """,
            list_id, user_id,
        )
        if head is None:
            return None

        items = await conn.fetch(
            """
            SELECT id, name, quantity, position, checked_at, checked_by, added_by, created_at
            FROM shopping_list_items
            WHERE list_id = $1
            ORDER BY position, id
            """,
            list_id,
        )
        members = await conn.fetch(
            """
            SELECT m.user_id, m.role, m.joined_at, u.first_name, u.username
            FROM shopping_list_members m
            JOIN users u ON u.telegram_id = m.user_id
            WHERE m.list_id = $1
            ORDER BY m.joined_at
            """,
            list_id,
        )

    return {
        **dict(head),
        "items": [dict(r) for r in items],
        "members": [dict(r) for r in members],
    }


async def create_list(owner_id: int, title: str) -> int:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            new_id = await conn.fetchval(
                """
                INSERT INTO shopping_lists (owner_id, title)
                VALUES ($1, $2)
                RETURNING id
                """,
                owner_id,
                title.strip() or "Список покупок",
            )
            await conn.execute(
                """
                INSERT INTO shopping_list_members (list_id, user_id, role)
                VALUES ($1, $2, 'owner')
                ON CONFLICT DO NOTHING
                """,
                new_id, owner_id,
            )
    return int(new_id)


async def archive_list(list_id: int, user_id: int) -> bool:
    """Archive a list — only the owner can do that."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE shopping_lists
            SET archived_at = NOW()
            WHERE id = $1 AND owner_id = $2 AND archived_at IS NULL
            """,
            list_id, user_id,
        )
    return result.endswith("1")


async def restore_list(list_id: int, user_id: int) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE shopping_lists
            SET archived_at = NULL
            WHERE id = $1 AND owner_id = $2 AND archived_at IS NOT NULL
            """,
            list_id, user_id,
        )
    return result.endswith("1")


async def rename_list(list_id: int, user_id: int, new_title: str) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE shopping_lists sl
            SET title = $3
            FROM shopping_list_members m
            WHERE sl.id = $1 AND m.list_id = sl.id AND m.user_id = $2
            """,
            list_id, user_id, new_title.strip()[:120] or "Список покупок",
        )
    return result.endswith("1")


async def delete_list(list_id: int, user_id: int) -> bool:
    """Полное удаление — только owner."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM shopping_lists WHERE id = $1 AND owner_id = $2",
            list_id, user_id,
        )
    return result.endswith("1")


# ============================================================
# Items
# ============================================================

async def _ensure_member(conn, list_id: int, user_id: int) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM shopping_list_members WHERE list_id = $1 AND user_id = $2",
        list_id, user_id,
    )
    return row is not None


async def add_item(list_id: int, user_id: int, name: str, quantity: str | None) -> dict | None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if not await _ensure_member(conn, list_id, user_id):
            return None
        next_pos = await conn.fetchval(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM shopping_list_items WHERE list_id = $1",
            list_id,
        )
        row = await conn.fetchrow(
            """
            INSERT INTO shopping_list_items (list_id, name, quantity, position, added_by)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, name, quantity, position, checked_at, checked_by, added_by, created_at
            """,
            list_id, name.strip()[:200], (quantity or "").strip()[:60] or None, next_pos, user_id,
        )
    return dict(row)


async def toggle_item(item_id: int, user_id: int, checked: bool) -> dict | None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Проверяем, что юзер — участник того списка, которому принадлежит item.
        is_member = await conn.fetchval(
            """
            SELECT 1
            FROM shopping_list_items i
            JOIN shopping_list_members m ON m.list_id = i.list_id AND m.user_id = $2
            WHERE i.id = $1
            """,
            item_id, user_id,
        )
        if not is_member:
            return None

        if checked:
            row = await conn.fetchrow(
                """
                UPDATE shopping_list_items
                SET checked_at = NOW(), checked_by = $2
                WHERE id = $1
                RETURNING id, list_id, name, quantity, position, checked_at, checked_by, added_by, created_at
                """,
                item_id, user_id,
            )
        else:
            row = await conn.fetchrow(
                """
                UPDATE shopping_list_items
                SET checked_at = NULL, checked_by = NULL
                WHERE id = $1
                RETURNING id, list_id, name, quantity, position, checked_at, checked_by, added_by, created_at
                """,
                item_id,
            )
    return dict(row) if row else None


async def delete_item(item_id: int, user_id: int) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM shopping_list_items i
            USING shopping_list_members m
            WHERE i.id = $1 AND m.list_id = i.list_id AND m.user_id = $2
            """,
            item_id, user_id,
        )
    return result.endswith("1")


# ============================================================
# Invites / members
# ============================================================

def _generate_code() -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(INVITE_LENGTH))


async def create_invite(list_id: int, user_id: int) -> dict | None:
    """Создаёт одноразовый 6-значный код для вступления в список."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if not await _ensure_member(conn, list_id, user_id):
            return None

        # На всякий случай, если по невероятному совпадению код уже есть — повторим
        for _ in range(5):
            code = _generate_code()
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO shopping_list_invites (list_id, code, created_by, expires_at)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, code, expires_at
                    """,
                    list_id,
                    code,
                    user_id,
                    datetime.now(timezone.utc) + INVITE_TTL,
                )
                return dict(row)
            except Exception as e:  # UniqueViolation
                logger.warning("Invite code collision, retrying: %s", e)
                continue
    return None


async def consume_invite(code: str, user_id: int) -> dict | None:
    """Юзер вступает в список по коду. Возвращает сам список или None."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            invite = await conn.fetchrow(
                """
                SELECT id, list_id, expires_at, consumed_at
                FROM shopping_list_invites
                WHERE UPPER(code) = UPPER($1)
                FOR UPDATE
                """,
                code.strip(),
            )
            if invite is None:
                return {"error": "not_found"}
            if invite["consumed_at"] is not None:
                return {"error": "already_used"}
            if invite["expires_at"] < datetime.now(timezone.utc):
                return {"error": "expired"}

            # Добавляем участника (если не owner и не уже в списке)
            await conn.execute(
                """
                INSERT INTO shopping_list_members (list_id, user_id, role)
                VALUES ($1, $2, 'member')
                ON CONFLICT DO NOTHING
                """,
                invite["list_id"], user_id,
            )
            await conn.execute(
                """
                UPDATE shopping_list_invites
                SET consumed_at = NOW(), consumed_by = $2
                WHERE id = $1
                """,
                invite["id"], user_id,
            )
        return {"list_id": int(invite["list_id"])}


async def remove_member(list_id: int, owner_id: int, target_user_id: int) -> bool:
    """Owner может удалить участника (кроме самого себя)."""
    if owner_id == target_user_id:
        return False
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM shopping_list_members
            WHERE list_id = $1
              AND user_id = $2
              AND EXISTS (
                  SELECT 1 FROM shopping_lists sl
                  WHERE sl.id = $1 AND sl.owner_id = $3
              )
            """,
            list_id, target_user_id, owner_id,
        )
    return result.endswith("1")


async def leave_list(list_id: int, user_id: int) -> bool:
    """Участник (не owner) выходит из списка сам."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM shopping_list_members
            WHERE list_id = $1 AND user_id = $2 AND role <> 'owner'
            """,
            list_id, user_id,
        )
    return result.endswith("1")
