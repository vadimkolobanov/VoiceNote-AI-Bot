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
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Fact, HabitCompletion, Moment, User
from src.services.llm_router import LLMRouter, LLMTask
from src.services.llm_router.prompts.loader import render as render_prompt

from .heuristics import TrivialResult, classify_trivial_text

logger = logging.getLogger(__name__)

EXTRACT_FACETS_VERSION = "extract_facets_v2"
FREE_HISTORY_DAYS = 30  # §2.4: free видит только 30 дней
DEFAULT_HOUR_LOCAL = 9  # §6.2 v2: если пользователь не назвал час — 09:00 local


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
            4. Сохранить главный момент + любые `extras` (доп. моменты,
               которые LLM извлёк из того же сообщения, см. §6.2 v2).
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

        title, facets, llm_version, extras = await self._derive_structure(
            raw_text, user
        )

        # Эмбеддинг для main + всех extras считается из исходного raw_text.
        embedding = None
        try:
            from src.services.embeddings import embed_text as _embed
            embedding = await _embed(raw_text, kind="doc")
        except Exception:
            logger.exception("embedding skipped for moment")

        # Главный момент.
        main = self._build_moment(
            user=user,
            raw_text=raw_text,
            payload=payload,
            title=title,
            facets=facets,
            llm_version=llm_version,
            client_id=payload.client_id,
        )
        if embedding is not None:
            main.embedding = embedding
        self._session.add(main)
        await self._session.flush()

        # Дочерние из extras (например, ДР Дианы из «завтра Диане купить
        # подарок на день рождения»). Сохраняем в той же транзакции —
        # клиент о них узнаёт через GET /moments следующим запросом.
        for extra in extras:
            try:
                child_title = (
                    (extra.get("title") or "").strip()
                    or _fallback_title_from_text(raw_text)
                )
                if len(child_title) > 120:
                    child_title = child_title[:117] + "…"
                child = self._build_moment(
                    user=user,
                    raw_text=raw_text,  # тот же исходный текст
                    payload=payload,
                    title=child_title,
                    facets=extra,
                    llm_version=llm_version,
                    client_id=None,  # extras всегда новые, без идемпотентности
                )
                if embedding is not None:
                    child.embedding = embedding
                self._session.add(child)
            except Exception as exc:  # noqa: BLE001 — extras best-effort
                logger.warning("Skipping extra due to error: %s", exc)
        await self._session.flush()

        return main

    def _build_moment(
        self,
        *,
        user: User,
        raw_text: str,
        payload: MomentCreate,
        title: str,
        facets: dict[str, Any],
        llm_version: Optional[str],
        client_id: Optional[uuid_module.UUID],
    ) -> Moment:
        """Собирает Moment из (title, facets, ...) с применением общих правил:
        override-полей клиента, normalize 00:00 default-часом, summary."""
        user_tz = user.timezone or "Europe/Moscow"

        # Override от клиента имеют наивысший приоритет (только для главного).
        # Для extras их нет — там client_id=None.
        override_occurs_at = (
            payload.occurs_at_override if client_id == payload.client_id else None
        )
        override_rrule = (
            payload.rrule_override if client_id == payload.client_id else None
        )

        occurs_at = override_occurs_at
        if occurs_at is None:
            occurs_at = _parse_iso_utc(facets.get("occurs_at"))
            occurs_at = _normalize_midnight_default(occurs_at, user_tz, raw_text)

        rrule = override_rrule
        if rrule is None:
            rrule = _nonblank_or_none(facets.get("rrule"))

        rrule_until = _parse_iso_utc(facets.get("rrule_until"))

        summary = None
        if len(raw_text) > 200:
            summary = _nonblank_or_none(facets.get("summary"))

        clean_facets = _clean_facets_for_storage(facets)

        return Moment(
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
            client_id=client_id,
        )

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
        """Сегодняшний экран:
        - одноразовые активные моменты с ``occurs_at`` в ближайшие 24 часа
        - одноразовые активные без времени, созданные за последние сутки
        - все привычки (rrule != null) — отметка «выполнено сегодня»
          вычисляется отдельно через ``completed_today_map``.
        """
        now = datetime.now(timezone.utc)
        horizon = now + timedelta(hours=24)

        stmt = (
            select(Moment)
            .where(Moment.user_id == user.id)
            .where(Moment.status != "trashed")
            .where(Moment.status != "archived")
            .where(
                or_(
                    Moment.rrule.is_not(None),
                    and_(
                        Moment.status == "active",
                        or_(
                            and_(Moment.occurs_at.is_not(None), Moment.occurs_at < horizon),
                            and_(
                                Moment.occurs_at.is_(None),
                                Moment.created_at >= now - timedelta(hours=24),
                            ),
                        ),
                    ),
                )
            )
            .order_by(Moment.occurs_at.asc().nulls_last(), Moment.created_at.desc())
        )
        rows = list((await self._session.scalars(stmt)).all())
        # Точная фильтрация на Python: yearly DR не показывать если не сегодня,
        # one-shot из прошлого не тащить, habit без часа — оставлять.
        filtered = [m for m in rows if is_relevant_today(m, user)]
        return filtered[:limit]

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
        """«Выполнить».

        Для одноразового момента — статус становится ``done``.
        Для привычки (``rrule != null``) — пишется отметка за сегодняшний
        день в ``habit_completions``; статус не трогаем, завтра привычка
        снова появится в Сегодня как невыполненная.
        """
        m = await self.get(user, moment_id)
        if m.rrule:
            today = _user_today(user)
            stmt = (
                pg_insert(HabitCompletion)
                .values(moment_id=m.id, user_id=user.id, completed_on=today)
                .on_conflict_do_nothing(constraint="uq_habit_completion_day")
            )
            await self._session.execute(stmt)
        else:
            m.status = "done"
            m.completed_at = datetime.now(timezone.utc)
        return m

    async def uncomplete(self, user: User, moment_id: int) -> Moment:
        """Откат «Выполнить» (для привычек удаляем сегодняшнюю отметку)."""
        m = await self.get(user, moment_id)
        if m.rrule:
            today = _user_today(user)
            await self._session.execute(
                delete(HabitCompletion).where(
                    HabitCompletion.moment_id == m.id,
                    HabitCompletion.completed_on == today,
                )
            )
        else:
            m.status = "active"
            m.completed_at = None
        return m

    async def _load_recent_facts(
        self, user_id: int, *, limit: int = 10
    ) -> list[dict[str, str]]:
        rows = await self._session.scalars(
            select(Fact)
            .where(Fact.user_id == user_id)
            .order_by(Fact.updated_at.desc())
            .limit(limit)
        )
        out: list[dict[str, str]] = []
        for f in rows.all():
            value = f.value or {}
            brief = ""
            if isinstance(value, dict):
                for k in ("name", "summary", "label", "what"):
                    if value.get(k):
                        brief = str(value[k])[:60]
                        break
            out.append({"kind": f.kind, "key": f.key, "value_brief": brief or f.key})
        return out

    async def is_completed_today(self, user: User, moment: Moment) -> bool:
        """True, если момент считается выполненным сегодня (для UI)."""
        if not moment.rrule:
            return moment.status == "done"
        today = _user_today(user)
        row = await self._session.scalar(
            select(HabitCompletion.id).where(
                HabitCompletion.moment_id == moment.id,
                HabitCompletion.completed_on == today,
            )
        )
        return row is not None

    async def completed_today_map(
        self, user: User, moments: Iterable[Moment]
    ) -> dict[int, bool]:
        """Пакетно: вернуть {moment_id: completed_today} для списка."""
        moments = list(moments)
        result: dict[int, bool] = {}
        habit_ids: list[int] = []
        for m in moments:
            if m.rrule:
                habit_ids.append(m.id)
            else:
                result[m.id] = m.status == "done"
        if habit_ids:
            today = _user_today(user)
            rows = await self._session.scalars(
                select(HabitCompletion.moment_id).where(
                    HabitCompletion.moment_id.in_(habit_ids),
                    HabitCompletion.completed_on == today,
                )
            )
            done_set = set(rows.all())
            for mid in habit_ids:
                result[mid] = mid in done_set
        return result

    async def snooze(self, user: User, moment_id: int, until: datetime) -> Moment:
        m = await self.get(user, moment_id)
        m.occurs_at = until
        m.status = "active"
        m.notified_at = None  # сбрасываем, чтобы scheduler уведомил снова
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
    ) -> tuple[str, dict[str, Any], Optional[str], list[dict[str, Any]]]:
        """Возвращает (title, facets, llm_version, extras).

        ``llm_version=None`` означает, что pipeline прошёл через skip-LLM
        (т. е. никакого LLM-вызова не было). ``extras`` — список
        дополнительных моментов из того же сообщения (например, ДР персоны
        упомянутый вместе с задачей «купить подарок»). См. §6.2 v2.
        """
        # 1. Skip-LLM.
        trivial = classify_trivial_text(raw_text)
        if trivial is not None:
            return trivial.title, trivial.facets, None, []

        # 2. LLM-путь (если роутер сконфигурирован).
        if self._router is None:
            title = _fallback_title_from_text(raw_text)
            return title, {"kind": "note", "topics": []}, None, []

        user_tz = user.timezone or "Europe/Moscow"
        now_utc = datetime.now(timezone.utc)
        tomorrow_local = _local_tomorrow_at(user_tz, hour=DEFAULT_HOUR_LOCAL)
        # Подсасываем top-10 последних фактов: LLM нормализует имена/места
        # к существующим ключам, а не плодит «Диана» / «Дианочка» / «Ди».
        recent_facts = await self._load_recent_facts(user.id, limit=10)
        try:
            prompt = render_prompt(
                "extract_facets",
                raw_text=raw_text,
                timezone=user_tz,
                current_datetime_iso=now_utc.isoformat(),
                current_day_of_week=_day_of_week_ru(now_utc),
                recent_titles=[],
                recent_facts=recent_facts,
                tomorrow_9h_utc=tomorrow_local.astimezone(timezone.utc).isoformat(),
                tomorrow_15h_utc=tomorrow_local.replace(hour=15)
                .astimezone(timezone.utc)
                .isoformat(),
                tomorrow_month=tomorrow_local.month,
                tomorrow_day=tomorrow_local.day,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to render extract_facets prompt: %s", exc)
            title = _fallback_title_from_text(raw_text)
            return title, {"kind": "note", "topics": []}, None, []

        try:
            response = await self._router.chat(
                task=LLMTask.FACET_EXTRACT,
                system="Ты — ассистент, возвращающий только JSON по схеме.",
                user=prompt,
                user_id=user.id,
                json_mode=True,
                temperature=0.1,
                max_tokens=1500,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "LLMRouter failed for moment extract, falling back to raw: %s", exc
            )
            title = _fallback_title_from_text(raw_text)
            return title, {"kind": "note", "topics": []}, None, []

        facets = _parse_facets_json(response.content)
        if facets is None:
            title = _fallback_title_from_text(raw_text)
            return title, {"kind": "note", "topics": []}, EXTRACT_FACETS_VERSION, []

        # extras достаём ДО clean — иначе они уплывут вместе с зеркалами.
        raw_extras = facets.get("extras") or []
        extras: list[dict[str, Any]] = [
            e for e in raw_extras if isinstance(e, dict)
        ]

        title = (facets.get("title") or "").strip() or _fallback_title_from_text(raw_text)
        if len(title) > 120:
            title = title[:117] + "…"

        return title, facets, EXTRACT_FACETS_VERSION, extras


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
    """Убираем из facets зеркала временных колонок (title, occurs_at, rrule)
    и поле extras (оно — flow-instruction для сервиса, в БД не нужно)."""
    mirrored = {
        "title",
        "summary",
        "occurs_at",
        "rrule",
        "rrule_until",
        "extras",
    }
    return {k: v for k, v in facets.items() if k not in mirrored}


def _user_tz(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone)
    except (ZoneInfoNotFoundError, AttributeError, TypeError):
        return ZoneInfo("Europe/Moscow")


def _user_today(user: User):
    """Сегодняшняя дата в TZ пользователя."""
    return datetime.now(_user_tz(user)).date()


def compute_next_reminder(moment: Moment, user: User) -> Optional[datetime]:
    """Следующее срабатывание момента в UTC.

    Для одноразового — ``occurs_at`` если ещё в будущем, иначе None.
    Для rrule:
      - если ``occurs_at`` задан (в нём время-внутри-дня) → считаем через rrulestr
      - если ``occurs_at`` отсутствует — у привычки нет конкретного часа,
        возвращаем None (UI покажет текстом «каждый день» / «каждую неделю»).
    """
    now = datetime.now(timezone.utc)
    if moment.rrule:
        if moment.occurs_at is None:
            return None
        try:
            from dateutil.rrule import rrulestr
        except Exception:
            return moment.occurs_at if moment.occurs_at > now else None
        try:
            dtstart = moment.occurs_at
            if dtstart.tzinfo is None:
                dtstart = dtstart.replace(tzinfo=timezone.utc)
            rule = rrulestr(moment.rrule, dtstart=dtstart)
            nxt = rule.after(now, inc=True) if dtstart > now else rule.after(now, inc=False)
            if nxt is None:
                return None
            if nxt.tzinfo is None:
                nxt = nxt.replace(tzinfo=timezone.utc)
            if moment.rrule_until and nxt > moment.rrule_until:
                return None
            return nxt
        except Exception:
            return None
    if moment.occurs_at and moment.occurs_at > now:
        return moment.occurs_at
    return None


def _rrule_fires_today(rrule: str, today_weekday_idx: int) -> bool:
    """Грубая проверка: правило срабатывает сегодня?

    Поддерживает FREQ=DAILY (всегда True) и FREQ=WEEKLY;BYDAY=… (проверяет
    день недели). MONTHLY/YEARLY → False (для них нужен compute_next_reminder
    и явный occurs_at, иначе мы не знаем дату).
    """
    parts = {}
    for kv in rrule.split(";"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            parts[k.strip().upper()] = v.strip().upper()
    freq = parts.get("FREQ", "")
    if freq == "DAILY":
        return True
    if freq == "WEEKLY":
        days = parts.get("BYDAY", "")
        if not days:
            return True  # каждую неделю — без уточнения дня считаем как «всегда»
        weekday_codes = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
        today_code = weekday_codes[today_weekday_idx]
        return today_code in {d.strip() for d in days.split(",")}
    return False


def is_relevant_today(moment: Moment, user: User) -> bool:
    """Должен ли момент попадать в Сегодня для UI."""
    if moment.status in ("trashed", "archived"):
        return False
    tz = _user_tz(user)
    now_tz = datetime.now(tz)
    today = now_tz.date()
    horizon_end = datetime.combine(today, datetime.min.time(), tz) + timedelta(days=1)

    if moment.rrule:
        # 1. Привычка с явным временем (occurs_at) — смотрим, попадает ли
        #    следующее срабатывание в сегодняшнее окно.
        if moment.occurs_at is not None:
            nxt = compute_next_reminder(moment, user)
            if nxt is None:
                return False
            return nxt < horizon_end
        # 2. Привычка без времени — ориентируемся на FREQ
        return _rrule_fires_today(moment.rrule, today.weekday())

    if moment.status == "done":
        return False  # одноразовый и уже выполнен — не показываем

    if moment.occurs_at is not None:
        occurs_local = moment.occurs_at.astimezone(tz)
        today_start_tz = datetime.combine(today, datetime.min.time(), tz)
        return today_start_tz <= occurs_local < horizon_end

    # без времени — показываем только если создан за последние 24ч
    return moment.created_at >= datetime.now(timezone.utc) - timedelta(hours=24)


def _local_tomorrow_at(tz_name: str, *, hour: int) -> datetime:
    """Возвращает «завтра, {hour}:00» в указанной таймзоне как aware-datetime."""
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("Europe/Moscow")
    now_local = datetime.now(tz)
    tomorrow = (now_local + timedelta(days=1)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    return tomorrow


# Слова, которые означают «время явно полночь / ночь» — для них 00:00 ок.
_MIDNIGHT_KEYWORDS = (
    "в полночь",
    "полночью",
    "в 00",
    "в 24",
    "ночью",
    "около полуночи",
    "после полуночи",
)


def _normalize_midnight_default(
    occurs_at: Optional[datetime],
    tz_name: str,
    raw_text: str,
) -> Optional[datetime]:
    """Если LLM вернул 00:00 локального времени, а в тексте полночь не
    упомянута — поднимаем до DEFAULT_HOUR_LOCAL (09:00). Иначе оставляем
    как есть. См. §6.2 v2 «Правила времени».
    """
    if occurs_at is None:
        return None
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("Europe/Moscow")
    local = occurs_at.astimezone(tz)
    if local.hour != 0 or local.minute != 0:
        return occurs_at  # время указано — не трогаем

    lower = raw_text.lower()
    if any(kw in lower for kw in _MIDNIGHT_KEYWORDS):
        return occurs_at  # пользователь явно сказал про полночь

    fixed_local = local.replace(hour=DEFAULT_HOUR_LOCAL)
    return fixed_local.astimezone(timezone.utc)


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
