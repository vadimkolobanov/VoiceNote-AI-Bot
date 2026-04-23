"""
Unified reminders read-model API (Phase 3a).

GET /api/v1/reminders — возвращает все напоминания пользователя
(notes + habits + birthdays в единой ленте, отсортировано по next_fire_at).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.database import reminder_repo
from .dependencies import get_current_user

router = APIRouter(prefix="/reminders", tags=["Reminders"])


class Reminder(BaseModel):
    id: int
    entity_type: str             # 'note' | 'habit' | 'birthday'
    entity_id: int
    title: str
    rrule: str | None = None
    dtstart: str
    next_fire_at: str | None = None
    last_fired_at: str | None = None
    pre_reminder_minutes: int = 0
    status: str                  # 'active' | 'paused' | 'completed'


def _to_iso(v) -> str | None:
    return v.isoformat() if v else None


def _serialize(row: dict) -> dict:
    return {
        "id": row["id"],
        "entity_type": row["entity_type"],
        "entity_id": row["entity_id"],
        "title": row["title"],
        "rrule": row.get("rrule"),
        "dtstart": _to_iso(row["dtstart"]),
        "next_fire_at": _to_iso(row.get("next_fire_at")),
        "last_fired_at": _to_iso(row.get("last_fired_at")),
        "pre_reminder_minutes": row.get("pre_reminder_minutes", 0),
        "status": row["status"],
    }


@router.get("", response_model=list[Reminder])
async def list_reminders(
    status: list[str] = Query(default=['active']),
    entity_type: list[str] = Query(default=['note', 'habit', 'birthday']),
    limit: int = Query(default=200, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    rows = await reminder_repo.list_user_reminders(
        current_user['telegram_id'],
        statuses=status,
        entity_types=entity_type,
        limit=limit,
    )
    return [_serialize(r) for r in rows]
