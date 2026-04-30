"""Outbound-уведомления админу через Telegram Bot API.

Нужно для:
- мгновенного оповещения о новом feedback (что юзер написал)
- регистрации новых юзеров
- критических ошибок (опционально)

Используется тот же бот, что в TG_BOT_TOKEN. Получатель — ADMIN_TELEGRAM_ID
(chat_id, который ты получил от @userinfobot после /start с ним).

Если переменные не заданы или Telegram недоступен — silently skip (это
вторичный канал, не должен ломать основные операции).
"""
from __future__ import annotations

import asyncio
import html
import logging
import os
from typing import Iterable

import httpx

logger = logging.getLogger(__name__)


def _split_admin_ids(raw: str) -> list[str]:
    """Поддерживаем несколько админов через запятую."""
    return [s.strip() for s in raw.split(",") if s.strip()]


async def _send_one(client: httpx.AsyncClient, token: str, chat_id: str, text: str) -> None:
    try:
        r = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if r.status_code >= 400:
            logger.warning(
                "admin_notify chat=%s failed: %s %s",
                chat_id, r.status_code, r.text[:200],
            )
    except Exception:
        logger.exception("admin_notify chat=%s send failed", chat_id)


async def notify_admin(text: str) -> None:
    """Отправить text в чат(ы) админа. Никогда не raises — fail-soft."""
    token = os.environ.get("TG_BOT_TOKEN") or ""
    raw_ids = os.environ.get("ADMIN_TELEGRAM_ID") or ""
    if not token or not raw_ids:
        logger.debug(
            "admin_notify skipped (token or ADMIN_TELEGRAM_ID empty)"
        )
        return
    ids = _split_admin_ids(raw_ids)
    if not ids:
        return
    async with httpx.AsyncClient() as client:
        await asyncio.gather(*(_send_one(client, token, cid, text) for cid in ids))


def fire_and_forget(text: str) -> None:
    """Удобный shortcut: запускает notify в текущем event-loop без await.

    Можно звать из любого async-кода после успешного коммита БД, не
    блокирующего HTTP-ответ.
    """
    try:
        asyncio.create_task(notify_admin(text))
    except RuntimeError:
        # нет running loop — это синхронный контекст; пропускаем.
        logger.debug("fire_and_forget called without running loop, skip")


# --- format helpers --------------------------------------------------------


def _esc(s: str | None) -> str:
    return html.escape(s or "")


SENTIMENT_EMOJI = {"positive": "😊", "neutral": "😐", "negative": "😞"}


def fmt_feedback(
    *,
    feedback_id: int,
    sentiment: str,
    body: str,
    user_id: int,
    user_email: str | None,
    user_name: str | None,
    app_version: str | None,
    device_info: str | None,
) -> str:
    emoji = SENTIMENT_EMOJI.get(sentiment, "💬")
    body_short = body if len(body) <= 1500 else body[:1497] + "…"

    name = (user_name or "").strip() or "—"
    email = (user_email or "").strip()
    device = (device_info or "—").strip()
    version = (app_version or "—").strip()

    # Если есть email — даём mailto-ссылку с готовой темой.
    if email:
        subject = f"Re%3A%20Feedback%20%23{feedback_id}"
        contact = (
            f'<a href="mailto:{_esc(email)}?subject={subject}">{_esc(email)}</a>'
        )
    else:
        contact = "—"

    lines = [
        f"{emoji} <b>Feedback #{feedback_id}</b>",
        "",
        f"<blockquote>{_esc(body_short)}</blockquote>",
        "",
        f"👤 {_esc(name)}  ·  <code>user#{user_id}</code>",
        f"✉️ {contact}",
        f"📱 <code>{_esc(device)}</code>",
        f"🏷 <code>{_esc(version)}</code>",
    ]
    return "\n".join(lines)


def fmt_signup(*, user_id: int, email: str | None, display_name: str | None) -> str:
    name = (display_name or "").strip() or "(без имени)"
    em = (email or "").strip()
    contact = f'<a href="mailto:{_esc(em)}">{_esc(em)}</a>' if em else "—"
    return (
        f"🎉 <b>Новый юзер</b>  ·  <code>#{user_id}</code>\n"
        f"👤 {_esc(name)}\n"
        f"✉️ {contact}"
    )
