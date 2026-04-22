"""
Polymorphic reminders — single read-model for notes/habits/birthdays.

Phase 3a: таблица используется как агрегированный источник для чтения
(мобильное приложение, API «все мои напоминания»). Запись синхронизируется
через hooks в уже существующих repo (notes, habits, birthdays) и в scheduler.
Сам APScheduler пока продолжает работать по старой схеме — будем
рефакторить в фазе 3b.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable

from .connection import get_db_pool

logger = logging.getLogger(__name__)


# ============================================================
# Upsert / delete helpers — вызываются из синхронизационных hooks
# ============================================================

async def upsert_note_reminder(
    *,
    user_id: int,
    note_id: int,
    title: str,
    due_date: datetime | None,
    recurrence_rule: str | None,
    pre_reminder_minutes: int = 0,
    is_completed: bool = False,
    is_archived: bool = False,
) -> None:
    """Upsert напоминания для заметки. При отсутствии `due_date` — удаляем."""
    if due_date is None:
        await _delete_reminder('note', note_id)
        return

    now = datetime.utcnow().replace(tzinfo=None)
    status = 'completed' if (is_completed or is_archived) else 'active'
    next_fire_at = None if status != 'active' else due_date
    # Для одноразовых просроченных — тоже completed
    if status == 'active' and recurrence_rule is None and due_date.timestamp() < now.timestamp():
        status = 'completed'
        next_fire_at = None

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO reminders (user_id, entity_type, entity_id, title, rrule,
                                   dtstart, next_fire_at, pre_reminder_minutes, status)
            VALUES ($1, 'note', $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (entity_type, entity_id) DO UPDATE SET
                title = EXCLUDED.title,
                rrule = EXCLUDED.rrule,
                dtstart = EXCLUDED.dtstart,
                next_fire_at = EXCLUDED.next_fire_at,
                pre_reminder_minutes = EXCLUDED.pre_reminder_minutes,
                status = EXCLUDED.status,
                updated_at = NOW()
            """,
            user_id, note_id, title[:250], recurrence_rule, due_date,
            next_fire_at, pre_reminder_minutes, status,
        )


async def upsert_habit_reminder(
    *,
    user_id: int,
    habit_id: int,
    name: str,
    frequency_rule: str,
    is_active: bool = True,
    reminder_time=None,
    dtstart: datetime | None = None,
) -> None:
    status = 'active' if is_active else 'paused'
    pool = await get_db_pool()
    dtstart = dtstart or datetime.utcnow()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO reminders (user_id, entity_type, entity_id, title, rrule,
                                   dtstart, next_fire_at, status)
            VALUES ($1, 'habit', $2, $3, $4, $5, NULL, $6)
            ON CONFLICT (entity_type, entity_id) DO UPDATE SET
                title = EXCLUDED.title,
                rrule = EXCLUDED.rrule,
                dtstart = EXCLUDED.dtstart,
                status = EXCLUDED.status,
                updated_at = NOW()
            """,
            user_id, habit_id, name[:250], frequency_rule, dtstart, status,
        )


async def upsert_birthday_reminder(
    *,
    user_id: int,
    birthday_id: int,
    person_name: str,
    birth_month: int,
    birth_day: int,
) -> None:
    rrule = f"FREQ=YEARLY;BYMONTH={birth_month};BYMONTHDAY={birth_day}"
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO reminders (user_id, entity_type, entity_id, title, rrule,
                                   dtstart, next_fire_at, status)
            VALUES ($1, 'birthday', $2, $3, $4, DATE_TRUNC('day', NOW()), NULL, 'active')
            ON CONFLICT (entity_type, entity_id) DO UPDATE SET
                title = EXCLUDED.title,
                rrule = EXCLUDED.rrule,
                updated_at = NOW()
            """,
            user_id, birthday_id, person_name[:250], rrule,
        )


async def _delete_reminder(entity_type: str, entity_id: int) -> None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM reminders WHERE entity_type = $1 AND entity_id = $2",
            entity_type, entity_id,
        )


async def delete_note_reminder(note_id: int) -> None:
    await _delete_reminder('note', note_id)


async def delete_habit_reminder(habit_id: int) -> None:
    await _delete_reminder('habit', habit_id)


async def delete_birthday_reminder(birthday_id: int) -> None:
    await _delete_reminder('birthday', birthday_id)


# ============================================================
# Read API (для /api/v1/reminders)
# ============================================================

async def list_user_reminders(
    user_id: int,
    *,
    statuses: Iterable[str] | None = None,
    entity_types: Iterable[str] | None = None,
    limit: int = 200,
) -> list[dict]:
    """Все напоминания пользователя, отсортированные по next_fire_at.

    :param statuses: по умолчанию 'active' — только активные.
    :param entity_types: фильтр по типу (note/habit/birthday).
    """
    statuses = list(statuses) if statuses else ['active']
    entity_types_list = list(entity_types) if entity_types else ['note', 'habit', 'birthday']

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, user_id, entity_type, entity_id, title, rrule,
                   dtstart, next_fire_at, last_fired_at, pre_reminder_minutes,
                   status, created_at, updated_at
            FROM reminders
            WHERE user_id = $1
              AND status = ANY($2)
              AND entity_type = ANY($3)
            ORDER BY
                CASE WHEN next_fire_at IS NULL THEN 1 ELSE 0 END,
                next_fire_at ASC,
                created_at DESC
            LIMIT $4
            """,
            user_id, statuses, entity_types_list, limit,
        )
    return [dict(r) for r in rows]
