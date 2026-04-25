"""Pydantic-схемы для /api/v1/moments (PRODUCT_PLAN.md §5.2, §5.3)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Source = Literal["voice", "text", "forward", "alice", "manual"]
CreatedVia = Literal["mobile", "bot", "alice", "system"]
Status = Literal["active", "done", "archived", "trashed"]
View = Literal["today", "timeline", "rhythm"]


# --- Moment DTO ------------------------------------------------------------


class MomentOut(BaseModel):
    """Ответ по §5.3.

    `occurs_at` всегда UTC (для расчётов на клиенте). `occurs_at_local` —
    naive ISO-строка (без offset) в TZ профиля пользователя; мобилка
    использует её для отображения, чтобы не зависеть от TZ устройства.
    То же — для `rrule_until` / `rrule_until_local`.
    """

    id: int
    client_id: Optional[uuid.UUID] = None
    raw_text: str
    title: str
    summary: Optional[str] = None
    facets: dict[str, Any] = Field(default_factory=dict)
    occurs_at: Optional[datetime] = None
    occurs_at_local: Optional[str] = None
    rrule: Optional[str] = None
    rrule_until: Optional[datetime] = None
    rrule_until_local: Optional[str] = None
    status: Status
    source: Source
    audio_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_via: CreatedVia


# --- POST /moments ---------------------------------------------------------


class MomentCreateIn(BaseModel):
    client_id: Optional[uuid.UUID] = None
    raw_text: str = Field(min_length=1, max_length=8000)
    source: Source = "text"
    occurs_at: Optional[datetime] = None
    rrule: Optional[str] = Field(default=None, max_length=200)
    audio_url: Optional[str] = Field(default=None, max_length=512)


class MomentBulkIn(BaseModel):
    items: list[MomentCreateIn] = Field(min_length=1, max_length=500)


class MomentsBulkOut(BaseModel):
    items: list[MomentOut]


# --- PATCH /moments/{id} ---------------------------------------------------


class MomentPatchIn(BaseModel):
    raw_text: Optional[str] = Field(default=None, max_length=8000)
    title: Optional[str] = Field(default=None, max_length=120)
    summary: Optional[str] = Field(default=None, max_length=8000)
    occurs_at: Optional[datetime] = None
    rrule: Optional[str] = Field(default=None, max_length=200)
    rrule_until: Optional[datetime] = None
    status: Optional[Status] = None
    facets: Optional[dict[str, Any]] = None


class MomentSnoozeIn(BaseModel):
    until: datetime


# --- GET list --------------------------------------------------------------


class MomentsListOut(BaseModel):
    items: list[MomentOut]
    next_cursor: Optional[int] = None
