"""Reminder scheduler — фоновая asyncio-таска, отправляет:

1. **Reminder push** — при наступлении ``moments.occurs_at`` (с учётом
   ``users.pre_reminder_minutes`` — за N минут до). Идемпотентность через
   ``moments.notified_at``.
2. **Утренний дайджест** — раз в день в ``users.digest_hour`` в TZ юзера,
   если у него есть моменты на сегодня. Анти-дубли через
   ``users.last_digest_sent_on``.

Пул каждые 60 секунд (баланс точности vs нагрузки).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.db.models import Moment, PushToken, User
from src.services import push_service

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 60


# --- helpers ---------------------------------------------------------------


def _user_tz(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone)
    except (ZoneInfoNotFoundError, AttributeError, TypeError):
        return ZoneInfo("Europe/Moscow")


async def _fcm_send(
    client: httpx.AsyncClient,
    fcm_url: str,
    headers: dict[str, str],
    token: str,
    *,
    title: str,
    body: str,
    data: dict[str, str],
) -> tuple[bool, str | None]:
    body_clean = body.strip()
    if len(body_clean) > 200:
        body_clean = body_clean[:197] + "…"
    msg = {
        "message": {
            "token": token,
            "data": {
                **data,
                "title": title,
                "body": body_clean or " ",
            },
            "android": {"priority": "high"},
        }
    }
    try:
        resp = await client.post(fcm_url, headers=headers, json=msg, timeout=10)
        if 200 <= resp.status_code < 300:
            return True, None
        return False, f"{resp.status_code} {resp.text[:200]}"
    except Exception as e:  # pragma: no cover
        return False, str(e)[:200]


async def _user_tokens(session, user_id: int) -> list[str]:
    rows = await session.scalars(
        select(PushToken.token).where(PushToken.user_id == user_id)
    )
    return list(rows.all())


async def _get_user(session, user_id: int) -> User | None:
    return await session.scalar(select(User).where(User.id == user_id))


# --- 1. Reminder pushes ----------------------------------------------------


async def _tick_reminders(
    session_factory: async_sessionmaker,
    client: httpx.AsyncClient,
    fcm_url: str,
    headers: dict[str, str],
) -> None:
    now = datetime.now(timezone.utc)
    # Берём все ещё не уведомлённые active одноразовые моменты у которых
    # occurs_at <= now + max(pre_reminder_minutes юзеров)
    # Самый простой путь: тянем все NOT-yet-notified с occurs_at в будущем
    # на горизонте 4 часа + всё, что уже подошло — и фильтруем в Python.
    # Это даёт корректный pre-reminder и не плодит сложных JOIN'ов.
    async with session_factory() as session:
        horizon = now + timedelta(hours=4)
        rows = await session.scalars(
            select(Moment)
            .where(Moment.status == "active")
            .where(Moment.notified_at.is_(None))
            .where(Moment.occurs_at.is_not(None))
            .where(Moment.occurs_at <= horizon)
            .where(Moment.rrule.is_(None))
            .limit(200)
        )
        moments = list(rows.all())
        if not moments:
            return

        # Кешируем юзеров (часто несколько моментов у одного юзера).
        user_cache: dict[int, User] = {}

        for m in moments:
            user = user_cache.get(m.user_id)
            if user is None:
                user = await _get_user(session, m.user_id)
                if user is None:
                    continue
                user_cache[m.user_id] = user
            pre_min = max(0, int(user.pre_reminder_minutes or 0))
            fire_at = m.occurs_at - timedelta(minutes=pre_min)
            if fire_at > now:
                continue  # ещё рано

            tokens = await _user_tokens(session, user.id)
            if not tokens:
                # без устройств — отметим, чтобы не зацикливаться
                await session.execute(
                    update(Moment).where(Moment.id == m.id).values(notified_at=now)
                )
                continue

            title = m.title or "Напоминание"
            body = (m.summary or m.raw_text or "").strip() or "Пора сделать."
            if pre_min > 0:
                title = f"Через {pre_min} мин · {title}"
            ok_any = False
            for tok in tokens:
                ok, err = await _fcm_send(
                    client, fcm_url, headers, tok,
                    title=title,
                    body=body,
                    data={"moment_id": str(m.id), "kind": "reminder"},
                )
                if ok:
                    ok_any = True
                else:
                    logger.warning("FCM send failed for moment %s: %s", m.id, err)
            if ok_any:
                await session.execute(
                    update(Moment).where(Moment.id == m.id).values(notified_at=now)
                )
                logger.info("reminder push sent for moment %s (pre=%s)", m.id, pre_min)
        await session.commit()


# --- 2. Morning digest -----------------------------------------------------


def _build_digest_text(today_moments: list[Moment]) -> tuple[str, str]:
    """Заголовок и тело пуша из моментов на сегодня."""
    if not today_moments:
        return "Доброе утро", "Сегодня тихо. Расскажи, что не хочешь забыть."
    one_shots = [m for m in today_moments if not m.rrule]
    habits = [m for m in today_moments if m.rrule]

    parts: list[str] = []
    if one_shots:
        parts.append(f"{len(one_shots)} {_word_plan(len(one_shots))}")
    if habits:
        parts.append(f"{len(habits)} {_word_habit(len(habits))}")

    head = f"Доброе утро · {' · '.join(parts) if parts else 'тихо'}"
    # Тело: первые 3 заголовка
    bullets: list[str] = []
    for m in (one_shots + habits)[:3]:
        bullets.append(f"• {m.title}")
    body = "\n".join(bullets) if bullets else "Открой Сегодня — гляди что на повестке."
    return head, body


def _word_plan(n: int) -> str:
    m100 = n % 100
    if 11 <= m100 <= 14:
        return "дел"
    last = n % 10
    if last == 1:
        return "дело"
    if 2 <= last <= 4:
        return "дела"
    return "дел"


def _word_habit(n: int) -> str:
    m100 = n % 100
    if 11 <= m100 <= 14:
        return "привычек"
    last = n % 10
    if last == 1:
        return "привычка"
    if 2 <= last <= 4:
        return "привычки"
    return "привычек"


async def _tick_digest(
    session_factory: async_sessionmaker,
    client: httpx.AsyncClient,
    fcm_url: str,
    headers: dict[str, str],
) -> None:
    """Раз в минуту смотрим: для кого из юзеров сейчас digest_hour и
    дайджест ещё не уходил сегодня — шлём.
    """
    now_utc = datetime.now(timezone.utc)
    async with session_factory() as session:
        users = await session.scalars(
            select(User)
            .where(User.deleted_at.is_(None))
            .where(User.digest_hour.is_not(None))
        )
        for user in users.all():
            tz = _user_tz(user)
            now_local = now_utc.astimezone(tz)
            today_local = now_local.date()
            if user.digest_hour is None:
                continue
            if now_local.hour != int(user.digest_hour):
                continue
            if user.last_digest_sent_on == today_local:
                continue

            tokens = await _user_tokens(session, user.id)
            if not tokens:
                # Пометим всё равно — иначе будем долбиться весь час пока пройдёт hour mismatch
                await session.execute(
                    update(User).where(User.id == user.id).values(last_digest_sent_on=today_local)
                )
                continue

            # Сегодняшние моменты юзера
            today_start = datetime.combine(today_local, datetime.min.time(), tz).astimezone(timezone.utc)
            today_end = today_start + timedelta(days=1)
            mrows = await session.scalars(
                select(Moment)
                .where(Moment.user_id == user.id)
                .where(Moment.status != "trashed")
                .where(Moment.status != "archived")
                .where(
                    or_(
                        Moment.rrule.is_not(None),
                        and_(
                            Moment.occurs_at >= today_start,
                            Moment.occurs_at < today_end,
                        ),
                    )
                )
                .order_by(Moment.occurs_at.asc().nulls_last())
            )
            moments = list(mrows.all())

            title, body = _build_digest_text(moments)
            ok_any = False
            for tok in tokens:
                ok, err = await _fcm_send(
                    client, fcm_url, headers, tok,
                    title=title,
                    body=body,
                    data={"kind": "digest"},
                )
                if ok:
                    ok_any = True
                else:
                    logger.warning("digest FCM send failed for user %s: %s", user.id, err)
            await session.execute(
                update(User).where(User.id == user.id).values(last_digest_sent_on=today_local)
            )
            if ok_any:
                logger.info("digest sent to user %s (%s today moments)", user.id, len(moments))
        await session.commit()


# --- main loop -------------------------------------------------------------


async def _tick(session_factory: async_sessionmaker) -> None:
    if not push_service.FIREBASE_INITIALIZED:
        return
    access_token = push_service.get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    fcm_url = push_service.FCM_V1_URL_TEMPLATE.format(project_id=push_service.PROJECT_ID)
    async with httpx.AsyncClient() as client:
        await _tick_reminders(session_factory, client, fcm_url, headers)
        await _tick_digest(session_factory, client, fcm_url, headers)


async def reminder_loop(
    session_factory: async_sessionmaker, *, interval: int = POLL_INTERVAL_SEC
) -> None:
    """Бесконечный цикл. Запускать как create_task() в startup-хуке."""
    logger.info("reminder_scheduler started, interval=%ss", interval)
    while True:
        try:
            await _tick(session_factory)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover
            logger.exception("reminder_scheduler tick failed")
        await asyncio.sleep(interval)
