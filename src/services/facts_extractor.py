"""Auto-extract facts из моментов (PRODUCT_PLAN.md §6.4 / §4.4).

Запускается fire-and-forget после успешного создания момента. Дёргает LLMRouter
с `LLMTask.FACTS_EXTRACT`, парсит результат, делает UPSERT в `facts` по уникальному
ключу (user_id, kind, key). Дубликаты не плодим: если факт уже есть, обновляем
`value`, добавляем `moment_id` в `source_moment_ids`, апаем `confidence` если
новая выше.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.db.models import Fact, Moment, User
from src.services.embeddings import embed_text
from src.services.llm_router import LLMRouter
from src.services.llm_router.base import LLMTask
from src.services.llm_router.prompts.loader import render as render_prompt

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.6
ALLOWED_KINDS = {"person", "place", "preference", "schedule", "other"}


def _value_brief(value: dict[str, Any]) -> str:
    """Короткое представление value для подсказки в промпте (известные факты)."""
    if not isinstance(value, dict):
        return str(value)[:40]
    for k in ("name", "summary", "label", "what"):
        if k in value and value[k]:
            return str(value[k])[:60]
    return json.dumps(value, ensure_ascii=False)[:60]


async def _known_facts_for_prompt(
    session, user_id: int, *, limit: int = 30
) -> list[dict[str, str]]:
    rows = await session.scalars(
        select(Fact)
        .where(Fact.user_id == user_id)
        .order_by(Fact.updated_at.desc())
        .limit(limit)
    )
    out: list[dict[str, str]] = []
    for f in rows.all():
        out.append(
            {
                "kind": f.kind,
                "key": f.key,
                "value_brief": _value_brief(f.value),
            }
        )
    return out


def _parse_facts(raw: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # бывает что LLM обернёт в ```json …```
        cleaned = raw.strip().strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return []
    facts = data.get("facts") if isinstance(data, dict) else None
    if not isinstance(facts, list):
        return []
    return facts


def _fact_to_text(kind: str, key: str, value: dict[str, Any]) -> str:
    """Свернуть факт в строку для эмбеддинга."""
    parts: list[str] = [kind, key]
    if isinstance(value, dict):
        for k in ("name", "role", "summary", "label", "what", "when", "details", "address"):
            v = value.get(k)
            if v:
                parts.append(str(v))
    return " · ".join(parts)


async def _upsert_fact(
    session,
    user_id: int,
    moment_id: int | None,
    kind: str,
    key: str,
    value: dict[str, Any],
    confidence: float,
) -> None:
    existing = await session.scalar(
        select(Fact).where(
            Fact.user_id == user_id,
            Fact.kind == kind,
            Fact.key == key,
        )
    )
    embedding = await embed_text(_fact_to_text(kind, key, value), kind="doc")
    src_moments = [moment_id] if moment_id is not None else []
    if existing is None:
        f = Fact(
            user_id=user_id,
            kind=kind,
            key=key,
            value=value,
            confidence=confidence,
            source_moment_ids=src_moments,
            embedding=embedding,
        )
        session.add(f)
        return
    merged = dict(existing.value or {})
    merged.update(value or {})
    existing.value = merged
    if confidence > (existing.confidence or 0.0):
        existing.confidence = confidence
    src = list(existing.source_moment_ids or [])
    if moment_id is not None and moment_id not in src:
        src.append(moment_id)
        existing.source_moment_ids = src
    if embedding is not None:
        existing.embedding = embedding
    existing.updated_at = datetime.now(timezone.utc)


async def extract_and_persist_facts(
    session_factory: async_sessionmaker,
    *,
    router: LLMRouter,
    user_id: int,
    user_timezone: str,
    raw_text: str,
    moment_id: int | None = None,
) -> int:
    """Главная точка входа. Возвращает число записанных/обновлённых фактов."""
    if not raw_text or len(raw_text.strip()) < 8:
        return 0
    try:
        async with session_factory() as session:
            known = await _known_facts_for_prompt(session, user_id)
            now_utc = datetime.now(timezone.utc)
            prompt = render_prompt(
                "extract_facts",
                raw_text=raw_text,
                timezone=user_timezone or "Europe/Moscow",
                current_datetime_iso=now_utc.isoformat(),
                known_facts=known,
            )
            response = await router.chat(
                task=LLMTask.FACTS_EXTRACT,
                system="Ты возвращаешь только JSON по схеме. Никакого текста.",
                user=prompt,
                user_id=user_id,
                json_mode=True,
                temperature=0.1,
                max_tokens=800,
            )
            facts = _parse_facts(response.content)
            written = 0
            for f in facts:
                kind = (f.get("kind") or "").strip().lower()
                key = (f.get("key") or "").strip()
                value = f.get("value") if isinstance(f.get("value"), dict) else None
                conf = f.get("confidence")
                try:
                    conf = float(conf) if conf is not None else 0.0
                except (TypeError, ValueError):
                    conf = 0.0
                if (
                    kind not in ALLOWED_KINDS
                    or not key
                    or value is None
                    or conf < MIN_CONFIDENCE
                ):
                    continue
                await _upsert_fact(
                    session,
                    user_id=user_id,
                    moment_id=moment_id,
                    kind=kind,
                    key=key[:128],
                    value=value,
                    confidence=conf,
                )
                written += 1
            await session.commit()
            if written:
                logger.info(
                    "facts_extract: user=%s moment=%s wrote=%s",
                    user_id, moment_id, written,
                )
            return written
    except Exception:
        logger.exception("facts_extract failed for moment=%s", moment_id)
        return 0
