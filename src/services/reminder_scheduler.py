"""Reminder scheduler — фоновая asyncio-таска, шлющая push-уведомления
при наступлении ``moments.occurs_at``.

MVP-вариант (S5.5/M7): один пуш на момент. Идемпотентность через
``moments.notified_at`` — после успешной отправки ставим текущее время.

В планах (post-MVP):
- pre_reminder за N минут (отдельная колонка / scheduled_jobs)
- repeat для habits с явным временем
- inline-actions в пуше (выполнено/отложить)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.db.models import Moment, PushToken
from src.services import push_service

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 15


async def _send_push_for_moment(
    client: httpx.AsyncClient,
    fcm_url: str,
    headers: dict[str, str],
    token: str,
    moment: Moment,
) -> tuple[bool, str | None]:
    body = (moment.summary or moment.raw_text or "").strip()
    if len(body) > 200:
        body = body[:197] + "…"
    # data-only payload: клиент сам показывает уведомление через
    # flutter_local_notifications с inline-кнопками «Выполнено»/«+15 мин».
    msg = {
        "message": {
            "token": token,
            "data": {
                "moment_id": str(moment.id),
                "kind": "reminder",
                "title": moment.title or "Напоминание",
                "body": body or "Пора сделать.",
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


async def _tick(session_factory: async_sessionmaker) -> None:
    if not push_service.FIREBASE_INITIALIZED:
        return
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        due = await session.scalars(
            select(Moment)
            .where(Moment.status == "active")
            .where(Moment.notified_at.is_(None))
            .where(Moment.occurs_at.is_not(None))
            .where(Moment.occurs_at <= now)
            # Привычки (rrule) пока не уведомляем — нужен per-occurrence лог.
            .where(Moment.rrule.is_(None))
            .limit(50)
        )
        moments = list(due.all())
        if not moments:
            return

        access_token = push_service.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        fcm_url = push_service.FCM_V1_URL_TEMPLATE.format(
            project_id=push_service.PROJECT_ID
        )

        async with httpx.AsyncClient() as client:
            for m in moments:
                tokens = await session.scalars(
                    select(PushToken.token).where(PushToken.user_id == m.user_id)
                )
                token_list = list(tokens.all())
                if not token_list:
                    logger.info("no push tokens for user %s, moment %s", m.user_id, m.id)
                    # всё равно ставим notified_at, чтобы не зацикливаться
                    await session.execute(
                        update(Moment).where(Moment.id == m.id).values(notified_at=now)
                    )
                    continue
                ok_any = False
                for tok in token_list:
                    ok, err = await _send_push_for_moment(client, fcm_url, headers, tok, m)
                    if ok:
                        ok_any = True
                    else:
                        logger.warning("FCM send failed for moment %s: %s", m.id, err)
                if ok_any:
                    await session.execute(
                        update(Moment).where(Moment.id == m.id).values(notified_at=now)
                    )
                    logger.info("reminder push sent for moment %s", m.id)
        await session.commit()


async def reminder_loop(session_factory: async_sessionmaker, *, interval: int = POLL_INTERVAL_SEC) -> None:
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
