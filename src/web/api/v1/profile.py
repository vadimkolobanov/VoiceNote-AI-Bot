"""/api/v1/profile — GET/PATCH (PRODUCT_PLAN.md §5.2)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    AgentMessage,
    AiUsage,
    Fact,
    HabitCompletion,
    Moment,
    PushToken,
    RefreshToken,
    Subscription,
    User,
)
from src.db.session import get_session

from .dependencies import get_current_user
from .schemas import UserPublic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfilePatchIn(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=128)
    timezone: Optional[str] = Field(default=None, max_length=64)
    locale: Optional[str] = Field(default=None, pattern="^(ru|en)$")
    digest_hour: Optional[int] = Field(default=None, ge=0, le=23)


def _to_public(u: User) -> UserPublic:
    return UserPublic(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        timezone=u.timezone,
        locale=u.locale,
        digest_hour=u.digest_hour,
        is_pro=u.is_pro(),
        created_at=u.created_at,
    )


@router.get("", response_model=UserPublic)
async def get_profile(user: User = Depends(get_current_user)) -> UserPublic:
    return _to_public(user)


@router.patch("", response_model=UserPublic)
async def patch_profile(
    payload: ProfilePatchIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserPublic:
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip() or None
    if payload.timezone is not None:
        user.timezone = payload.timezone
    if payload.locale is not None:
        user.locale = payload.locale
    if payload.digest_hour is not None:
        user.digest_hour = payload.digest_hour
    return _to_public(user)


# --- Stats -----------------------------------------------------------------


class HabitStreakOut(BaseModel):
    moment_id: int
    title: str
    streak_days: int


class StatsOut(BaseModel):
    total_moments: int
    active_count: int
    done_today: int
    overdue_count: int
    week_completed: int
    week_planned: int
    habit_streaks: list[HabitStreakOut]


def _user_tz(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone)
    except (ZoneInfoNotFoundError, AttributeError, TypeError):
        return ZoneInfo("Europe/Moscow")


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StatsOut:
    tz = _user_tz(user)
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)
    today = now_local.date()
    today_start_utc = datetime.combine(today, datetime.min.time(), tz).astimezone(timezone.utc)
    week_start_utc = (
        datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time(), tz)
        .astimezone(timezone.utc)
    )

    # Total moments (исключая trashed)
    total = await session.scalar(
        select(func.count(Moment.id)).where(
            Moment.user_id == user.id, Moment.status != "trashed"
        )
    ) or 0

    active_count = await session.scalar(
        select(func.count(Moment.id)).where(
            Moment.user_id == user.id, Moment.status == "active"
        )
    ) or 0

    overdue_count = await session.scalar(
        select(func.count(Moment.id)).where(
            Moment.user_id == user.id,
            Moment.status == "active",
            Moment.rrule.is_(None),
            Moment.occurs_at.is_not(None),
            Moment.occurs_at < now_utc,
        )
    ) or 0

    # «Сделано сегодня» = одноразовые с completed_at сегодня + привычки с
    # habit_completions за сегодня.
    done_today_oneshots = await session.scalar(
        select(func.count(Moment.id)).where(
            Moment.user_id == user.id,
            Moment.status == "done",
            Moment.completed_at.is_not(None),
            Moment.completed_at >= today_start_utc,
        )
    ) or 0
    done_today_habits = await session.scalar(
        select(func.count(HabitCompletion.id)).where(
            HabitCompletion.user_id == user.id,
            HabitCompletion.completed_on == today,
        )
    ) or 0
    done_today = int(done_today_oneshots) + int(done_today_habits)

    # «Запланировано на неделю» = одноразовые активные с occurs_at в эту неделю
    # + done одноразовые с completed_at в этой неделе.
    week_completed_oneshots = await session.scalar(
        select(func.count(Moment.id)).where(
            Moment.user_id == user.id,
            Moment.status == "done",
            Moment.completed_at >= week_start_utc,
        )
    ) or 0
    week_completed_habits = await session.scalar(
        select(func.count(HabitCompletion.id)).where(
            HabitCompletion.user_id == user.id,
            HabitCompletion.completed_on
            >= today - timedelta(days=today.weekday()),
        )
    ) or 0
    week_completed = int(week_completed_oneshots) + int(week_completed_habits)

    week_planned_oneshots = await session.scalar(
        select(func.count(Moment.id)).where(
            Moment.user_id == user.id,
            Moment.status != "trashed",
            Moment.rrule.is_(None),
            Moment.occurs_at.is_not(None),
            Moment.occurs_at >= week_start_utc,
            Moment.occurs_at < week_start_utc + timedelta(days=7),
        )
    ) or 0
    week_planned = int(week_planned_oneshots) + int(week_completed)

    # Habit streaks (по 5 самым «горячим»)
    habit_rows = await session.scalars(
        select(Moment).where(
            Moment.user_id == user.id,
            Moment.status != "trashed",
            Moment.rrule.is_not(None),
        )
    )
    streaks: list[HabitStreakOut] = []
    for hm in habit_rows.all():
        # Считаем непрерывную последовательность дней назад от сегодня.
        days = await session.scalars(
            select(HabitCompletion.completed_on).where(
                HabitCompletion.moment_id == hm.id
            ).order_by(HabitCompletion.completed_on.desc()).limit(60)
        )
        day_set = set(days.all())
        streak = 0
        cursor = today
        while cursor in day_set:
            streak += 1
            cursor = cursor - timedelta(days=1)
        if streak > 0:
            streaks.append(
                HabitStreakOut(moment_id=hm.id, title=hm.title, streak_days=streak)
            )
    streaks.sort(key=lambda s: s.streak_days, reverse=True)

    return StatsOut(
        total_moments=int(total),
        active_count=int(active_count),
        done_today=done_today,
        overdue_count=int(overdue_count),
        week_completed=week_completed,
        week_planned=week_planned,
        habit_streaks=streaks[:5],
    )


# --- Wipe everything ---------------------------------------------------------


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Полное удаление аккаунта и всей памяти.

    Удаляются: моменты, факты, habit_completions, push-токены, refresh-токены,
    ai_usage, agent_messages, subscriptions — и сам User. Откат невозможен.
    """
    uid = user.id
    # Большинство FK имеют ON DELETE CASCADE, но дублируем явно для надёжности
    # и чтобы порядок был контролируемым.
    for model in (
        HabitCompletion,
        Fact,
        Moment,
        PushToken,
        RefreshToken,
        AiUsage,
        AgentMessage,
        Subscription,
    ):
        await session.execute(delete(model).where(model.user_id == uid))
    await session.delete(user)
    await session.commit()
    logger.info("user %s deleted everything", uid)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
