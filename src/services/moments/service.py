"""MomentService — доменные операции над ``moments`` (§4.1, §5.2, §6.1).

Этот слой знает про:
    - Moment ORM и её инварианты
    - skip-LLM heuristics и LLMRouter
    - идемпотентность по client_id (§4.10)

И не знает про:
    - FastAPI/HTTP
    - Telegram/Alice
    - Конкретного провайдера LLM (ходит только в LLMRouter)
"""
from __future__ import annotations

import json
import logging
import re
import uuid as uuid_module
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Moment, User
from src.services.llm_router import LLMRouter, LLMTask
from src.services.llm_router.prompts.loader import render as render_prompt

from .heuristics import TrivialResult, classify_trivial_text

logger = logging.getLogger(__name__)

EXTRACT_FACETS_VERSION = "extract_facets_v1"
FREE_HISTORY_DAYS = 30  # §2.4: free видит только 30 дней


# --- DTO-входы/выходы ------------------------------------------------------


@dataclass(slots=True)
class MomentCreate:
    raw_text: str
    source: str = "text"                     # 'voice' | 'text' | 'forward' | 'alice' | 'manual'
    created_via: str = "mobile"              # 'mobile' | 'bot' | 'alice' | 'system'
    audio_url: Optional[str] = None
    language: str = "ru"
    client_id: Optional[uuid_module.UUID] = None
    # Клиент может переопределить occurs_at/rrule вручную — тогда LLM не
    # трогает эти поля (мы им доверяем).
    occurs_at_override: Optional[datetime] = None
    rrule_override: Optional[str] = None


@dataclass(slots=True)
class MomentPatch:
    raw_text: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    occurs_at: Optional[datetime] = None
    rrule: Optional[str] = None
    rrule_until: Optional[datetime] = None
    status: Optional[str] = None
    facets: Optional[dict[str, Any]] = None


class MomentNotFound(Exception):
    pass


class MomentForbidden(Exception):
    """Попытка доступа к чужому моменту."""


# --- Service ---------------------------------------------------------------


class MomentService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        llm_router: Optional[LLMRouter] = None,
    ) -> None:
        self._session = session
        self._router = llm_router

    # --- create --------------------------------------------------------

    async def create_from_text(
        self,
        user: User,
        payload: MomentCreate,
    ) -> Moment:
        """Создаёт момент из текста. Идемпотентно по ``client_id``.

        Pipeline:
            1. Если ``client_id`` уже есть в БД — вернуть существующий.
            2. Попробовать skip-LLM эвристику.
            3. Если не зашло — сходить в LLMRouter (facet_extract).
            4. Сохранить.
        """
        # Идемпотентность (§4.10).
        if payload.client_id is not None:
            existing = await self._session.scalar(
                select(Moment).where(Moment.client_id == payload.client_id)
            )
            if existing is not None:
                return existing

        raw_text = payload.raw_text.strip()
        if not raw_text:
            raise ValueError("raw_text is empty")

        title, facets, llm_version = await self._derive_structure(
            raw_text, user
        )

        # Пользовательские override'ы имеют приоритет над LLM-ответом.
        occurs_at = payload.occurs_at_override
        rrule = payload.rrule_override

        # Если override не указан, вытаскиваем из facets (LLM-ветка).
        if occurs_at is None:
            occurs_at = _parse_iso_utc(facets.get("occurs_at"))
        if rrule is None:
            rrule = _nonblank_or_none(facets.get("rrule"))

        rrule_until = _parse_iso_utc(facets.get("rrule_until"))

        summary = None
        if len(raw_text) > 200:
            summary = _nonblank_or_none(facets.get("summary"))

        # ``facets`` в БД — компактный объект без зеркал временных полей;
        # дедуп колонок решается БД-индексами (§4.1 — «дублируют facets»).
        clean_facets = _clean_facets_for_storage(facets)

        moment = Moment(
            user_id=user.id,
            raw_text=raw_text,
            source=payload.source,
            audio_url=payload.audio_url,
            language=payload.language,
            title=title,
            summary=summary,
            facets=clean_facets,
            occurs_at=occurs_at,
            rrule=rrule,
            rrule_until=rrule_until,
            status="active",
            created_via=payload.created_via,
            llm_version=llm_version,
            client_id=payload.client_id,
        )
        self._session.add(moment)
        await self._session.flush()
        return moment

    async def bulk_create(
        self,
        user: User,
        items: Iterable[MomentCreate],
    ) -> list[Moment]:
        """Офлайн-sync (§4.10). Дубли по ``client_id`` возвращаются как были."""
        out: list[Moment] = []
        for payload in items:
            out.append(await self.create_from_text(user, payload))
        return out

    # --- read ----------------------------------------------------------

    async def get(self, user: User, moment_id: int) -> Moment:
        m = await self._session.get(Moment, moment_id)
        if m is None or m.status == "trashed":
            raise MomentNotFound()
        if m.user_id != user.id:
            raise MomentForbidden()
        return m

    async def list_today(self, user: User, *, limit: int = 50) -> list[Moment]:
        """Моменты с occurs_at в ближайшие 24 часа + без времени, созданные
        за последние сутки. Порядок: сначала по времени, потом по created_at.
        """
        now = datetime.now(timezone.utc)
        horizon = now + timedelta(hours=24)

        stmt = (
            select(Moment)
            .where(Moment.user_id == user.id)
            .where(Moment.status == "active")
            .where(
                or_(
                    and_(Moment.occurs_at.is_not(None), Moment.occurs_at < horizon),
                    and_(
                        Moment.occurs_at.is_(None),
                        Moment.created_at >= now - timedelta(hours=24),
                    ),
                )
            )
            .order_by(Moment.occurs_at.asc().nulls_last(), Moment.created_at.desc())
            .limit(limit)
        )
        return list((await self._session.scalars(stmt)).all())

    async def list_timeline(
        self,
        user: User,
        *,
        cursor: Optional[int] = None,
        limit: int = 50,
    ) -> list[Moment]:
        """Хроника: все moments юзера, новые сверху. Курсор — id предыдущей
        последней записи. Free-юзер ограничен 30 днями (§2.4)."""
        stmt = (
            select(Moment)
            .where(Moment.user_id == user.id)
            .where(Moment.status != "trashed")
        )
        if not user.is_pro():
            cutoff = datetime.now(timezone.utc) - timedelta(days=FREE_HISTORY_DAYS)
            stmt = stmt.where(Moment.created_at >= cutoff)
        if cursor is not None:
            stmt = stmt.where(Moment.id < cursor)
        stmt = stmt.order_by(Moment.id.desc()).limit(limit)
        return list((await self._session.scalars(stmt)).all())

    async def list_rhythm(self, user: User) -> dict[str, list[Moment]]:
        """Ритм: attenzione — это представление (§5.2 ``GET /views/rhythm``).

        Возвращаем `habits` и `cycles` отдельно, как ждёт фронт.
        """
        stmt = (
            select(Moment)
            .where(Moment.user_id == user.id)
            .where(Moment.status != "trashed")
            .where(Moment.rrule.is_not(None))
        )
        rows = list((await self._session.scalars(stmt)).all())
        habits = [m for m in rows if _facet_kind(m) == "habit"]
        cycles = [m for m in rows if _facet_kind(m) != "habit"]
        return {"habits": habits, "cycles": cycles}

    # --- update --------------------------------------------------------

    async def patch(self, user: User, moment_id: int, changes: MomentPatch) -> Moment:
        m = await self.get(user, moment_id)
        if changes.raw_text is not None:
            m.raw_text = changes.raw_text
        if changes.title is not None:
            m.title = changes.title
        if changes.summary is not None:
            m.summary = changes.summary
        if changes.occurs_at is not None:
            m.occurs_at = changes.occurs_at
        if changes.rrule is not None:
            m.rrule = changes.rrule or None
        if changes.rrule_until is not None:
            m.rrule_until = changes.rrule_until
        if changes.status is not None:
            m.status = changes.status
        if changes.facets is not None:
            m.facets = _clean_facets_for_storage(changes.facets)
        # updated_at обновляется триггером onupdate, но для ранних SQLite
        # тестов явно дублируем:
        m.updated_at = datetime.now(timezone.utc)
        return m

    async def complete(self, user: User, moment_id: int) -> Moment:
        m = await self.get(user, moment_id)
        m.status = "done"
        m.completed_at = datetime.now(timezone.utc)
        return m

    async def snooze(self, user: User, moment_id: int, until: datetime) -> Moment:
        m = await self.get(user, moment_id)
        m.occurs_at = until
        m.status = "active"
        return m

    async def soft_delete(self, user: User, moment_id: int) -> Moment:
        m = await self.get(user, moment_id)
        m.status = "trashed"
        return m

    # --- internal: structure derivation -------------------------------

    async def _derive_structure(
        self,
        raw_text: str,
        user: User,
    ) -> tuple[str, dict[str, Any], Optional[str]]:
        """Возвращает (title, facets, llm_version).

        ``llm_version=None`` означает, что pipeline прошёл через skip-LLM
        (т. е. никакого LLM-вызова не было).
        """
        # 1. Skip-LLM.
        trivial = classify_trivial_text(raw_text)
        if trivial is not None:
            return trivial.title, trivial.facets, None

        # 2. LLM-путь (если роутер сконфигурирован).
        if self._router is None:
            # Деградация: берём raw_text как title, facets — пустой note.
            title = _fallback_title_from_text(raw_text)
            return title, {"kind": "note", "topics": []}, None

        user_tz = user.timezone or "Europe/Moscow"
        now_utc = datetime.now(timezone.utc)
        try:
            prompt = render_prompt(
                "extract_facets",
                raw_text=raw_text,
                timezone=user_tz,
                current_datetime_iso=now_utc.isoformat(),
                current_day_of_week=_day_of_week_ru(now_utc),
                recent_titles=[],
                recent_facts=[],
                tomorrow_15h_utc=(now_utc + timedelta(days=1)).replace(
                    hour=12, minute=0, second=0, microsecond=0
                ).isoformat(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to render extract_facets prompt: %s", exc)
            title = _fallback_title_from_text(raw_text)
            return title, {"kind": "note", "topics": []}, None

        try:
            response = await self._router.chat(
                task=LLMTask.FACET_EXTRACT,
                system="Ты — ассистент, возвращающий только JSON по схеме.",
                user=prompt,
                user_id=user.id,
                json_mode=True,
                temperature=0.1,
                max_tokens=1024,
            )
        except Exception as exc:  # noqa: BLE001 — включая LLMRouterError
            logger.warning(
                "LLMRouter failed for moment extract, falling back to raw: %s", exc
            )
            title = _fallback_title_from_text(raw_text)
            return title, {"kind": "note", "topics": []}, None

        facets = _parse_facets_json(response.content)
        if facets is None:
            title = _fallback_title_from_text(raw_text)
            return title, {"kind": "note", "topics": []}, EXTRACT_FACETS_VERSION

        title = (facets.get("title") or "").strip() or _fallback_title_from_text(raw_text)
        if len(title) > 120:
            title = title[:117] + "…"

        return title, facets, EXTRACT_FACETS_VERSION


# --- helpers ---------------------------------------------------------------


def _facet_kind(m: Moment) -> str:
    return (m.facets or {}).get("kind") or "note"


def _parse_iso_utc(raw: Any) -> Optional[datetime]:
    if not raw or not isinstance(raw, str):
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _nonblank_or_none(v: Any) -> Optional[str]:
    if not isinstance(v, str):
        return None
    v = v.strip()
    return v or None


def _clean_facets_for_storage(facets: dict[str, Any]) -> dict[str, Any]:
    """Убираем из facets зеркала временных колонок (title, occurs_at, rrule),
    которые уже лежат в реальных колонках moments. Остальное — сохраняем."""
    mirrored = {"title", "summary", "occurs_at", "rrule", "rrule_until"}
    return {k: v for k, v in facets.items() if k not in mirrored}


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)


def _parse_facets_json(raw: str) -> Optional[dict[str, Any]]:
    """Вытаскивает JSON из ответа LLM. Fences + mixed text — обрабатываем."""
    text = raw.strip()
    match = _JSON_FENCE_RE.search(text)
    if match:
        text = match.group(1).strip()
    elif text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON, falling back: %s", raw[:200])
        return None

    if not isinstance(data, dict):
        return None
    return data


def _fallback_title_from_text(raw: str) -> str:
    """Первые ≤ 60 симв первой строки, без точки в конце."""
    first_line = raw.strip().splitlines()[0] if raw.strip() else ""
    title = first_line[:60].rstrip(".!? ")
    return title or "Без названия"


_WEEKDAYS_RU = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье")


def _day_of_week_ru(dt: datetime) -> str:
    return _WEEKDAYS_RU[dt.weekday()]
