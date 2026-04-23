"""/api/v1/agent/* — Pro-only Q&A (PRODUCT_PLAN.md §5.2, §6.3).

Важные оговорки:
- pgvector-поиск top-10 moments + top-5 facts по embedding — появится, когда
  встанет BGE-M3 (скорее всего начало M3). Пока контекст собирается по
  последним по дате моментам — достаточный baseline, чтобы тестить контракт.
- Claude Haiku через Hetzner-прокси заработает в M3. До этого роутер
  переключается на DeepSeek fallback — see PRODUCT_PLAN §18.2 layer 4.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentMessage, Moment, User
from src.db.session import get_session
from src.services.llm_router import LLMRouter, LLMTask, build_default_router
from src.services.llm_router.base import LLMRouterError

from .dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


# --- schemas ---------------------------------------------------------------


class AgentAskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class CitedMoment(BaseModel):
    id: int
    title: str
    snippet: str


class AgentAskOut(BaseModel):
    answer: str
    cited_moments: list[CitedMoment]


class AgentMessageOut(BaseModel):
    id: int
    role: str  # 'user' | 'assistant'
    content: str
    cited_moment_ids: list[int] = []
    created_at: datetime


class AgentHistoryOut(BaseModel):
    items: list[AgentMessageOut]
    next_cursor: Optional[int] = None


# --- DI --------------------------------------------------------------------


def get_llm_router() -> LLMRouter:
    return build_default_router(usage_logger_kind="db")


# --- helpers ---------------------------------------------------------------


def _require_pro(user: User) -> None:
    if not user.is_pro():
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": {
                    "code": "PRO_REQUIRED",
                    "message": "Agent Q&A доступен только в Pro (PRODUCT_PLAN §8.2)",
                }
            },
        )


async def _fetch_recent_moments(
    session: AsyncSession, user: User, limit: int = 10
) -> list[Moment]:
    stmt = (
        select(Moment)
        .where(Moment.user_id == user.id)
        .where(Moment.status != "trashed")
        .order_by(Moment.created_at.desc())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


def _build_context_block(moments: list[Moment]) -> str:
    if not moments:
        return "Релевантных записей пользователя не найдено."
    lines = ["Записи пользователя (от новых к старым):"]
    for m in moments:
        when = m.occurs_at.isoformat() if m.occurs_at else m.created_at.isoformat()
        lines.append(f"- #{m.id} [{when}] {m.title}: {m.raw_text[:200]}")
    return "\n".join(lines)


# --- endpoints -------------------------------------------------------------


@router.post("/ask", response_model=AgentAskOut)
async def ask_agent(
    payload: AgentAskIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm_router: LLMRouter = Depends(get_llm_router),
) -> AgentAskOut:
    _require_pro(user)

    # Контекст: последние 10 моментов. BGE-M3 + top-10 по косинусу — в M3.
    moments = await _fetch_recent_moments(session, user, limit=10)
    context_block = _build_context_block(moments)

    system = (
        "Ты — умный внимательный друг пользователя. Отвечаешь только на "
        "основе его записей (ниже в контексте). Если ответа в них нет — "
        "честно говоришь: «Не помню, расскажи мне». Короткие фразы, без "
        "канцелярита, на «ты». После ответа укажи номера записей, которые "
        "использовал (если были), в формате: «Опора: #12, #34»."
    )
    user_prompt = f"{context_block}\n\nВопрос пользователя: {payload.question}"

    try:
        response = await llm_router.chat(
            task=LLMTask.AGENT_ASK,
            system=system,
            user=user_prompt,
            user_id=user.id,
            temperature=0.3,
            max_tokens=512,
        )
    except LLMRouterError:
        # §18.2 layer 4 — graceful degradation
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "AGENT_UNAVAILABLE",
                    "message": "Извини, я сегодня перегружен. Попробуй через час.",
                }
            },
        )

    answer = response.content.strip()

    # Собираем cited по упоминанию `#<id>` в ответе.
    cited_ids = _extract_cited_ids(answer)
    by_id = {m.id: m for m in moments}
    cited = [
        CitedMoment(id=m.id, title=m.title, snippet=m.raw_text[:160])
        for mid in cited_ids
        if (m := by_id.get(mid)) is not None
    ]

    # Сохраняем пару messages (question + answer).
    session.add(
        AgentMessage(user_id=user.id, role="user", content=payload.question)
    )
    session.add(
        AgentMessage(
            user_id=user.id,
            role="assistant",
            content=answer,
            cited_moment_ids=[c.id for c in cited],
        )
    )

    return AgentAskOut(answer=answer, cited_moments=cited)


@router.get("/history", response_model=AgentHistoryOut)
async def history(
    cursor: Optional[int] = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AgentHistoryOut:
    _require_pro(user)
    stmt = select(AgentMessage).where(AgentMessage.user_id == user.id)
    if cursor is not None:
        stmt = stmt.where(AgentMessage.id < cursor)
    stmt = stmt.order_by(AgentMessage.id.desc()).limit(limit)
    rows = list((await session.scalars(stmt)).all())
    next_cursor = rows[-1].id if len(rows) == limit else None
    return AgentHistoryOut(
        items=[
            AgentMessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                cited_moment_ids=list(m.cited_moment_ids or []),
                created_at=m.created_at,
            )
            for m in rows
        ],
        next_cursor=next_cursor,
    )


# --- helpers (pure) --------------------------------------------------------


import re

_CITE_RE = re.compile(r"#(\d+)")


def _extract_cited_ids(text: str) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for match in _CITE_RE.finditer(text):
        i = int(match.group(1))
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out
