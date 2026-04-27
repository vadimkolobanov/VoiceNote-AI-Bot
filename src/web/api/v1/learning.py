"""/api/v1/learning/* — режим «обучения», когда юзер диктует историю
о себе целиком, чтобы вырастить память (PRODUCT_PLAN.md S16, M10).

Отличие от обычного ``/moments``:
- Текст НЕ становится моментом, не попадает в Хронику и Сегодня
- Из текста извлекаются ТОЛЬКО факты (через тот же facts_extractor)
- Каждый факт получает эмбеддинг (для семантического поиска)

Юзер может рассказать длинный рассказ — приложение разберёт и запомнит.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.db.models import User
from src.db.session import AsyncSessionLocal
from src.services.facts_extractor import extract_and_persist_facts
from src.services.llm_router import LLMRouter

from .dependencies import get_current_user
from .moments import get_llm_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning", tags=["learning"])


class TellIn(BaseModel):
    text: str = Field(min_length=8, max_length=16000)


class TellOut(BaseModel):
    facts_written: int
    chunks_processed: int


def _split_into_chunks(text: str, *, max_len: int = 1500) -> list[str]:
    """Дробим длинный рассказ на куски по предложениям, чтобы LLM не задыхался."""
    text = text.strip()
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    buf: list[str] = []
    cur = 0
    # очень простое разбиение по точке/!/?
    parts = []
    start = 0
    for i, ch in enumerate(text):
        if ch in ".!?\n" and (i - start) > 30:
            parts.append(text[start : i + 1].strip())
            start = i + 1
    if start < len(text):
        parts.append(text[start:].strip())
    if not parts:
        return [text]
    for p in parts:
        if cur + len(p) > max_len and buf:
            chunks.append(" ".join(buf))
            buf, cur = [], 0
        buf.append(p)
        cur += len(p) + 1
    if buf:
        chunks.append(" ".join(buf))
    return chunks


@router.post("/tell", response_model=TellOut, status_code=status.HTTP_200_OK)
async def tell_about_yourself(
    payload: TellIn,
    user: User = Depends(get_current_user),
    llm_router: LLMRouter = Depends(get_llm_router),
) -> TellOut:
    chunks = _split_into_chunks(payload.text)
    if not chunks:
        raise HTTPException(400, "Текст пустой")

    total_written = 0
    # Проходим по чанкам последовательно: facts_extractor сам делает upsert,
    # параллелить не имеет смысла (LLM rate-limit + конфликт ON CONFLICT в БД).
    for chunk in chunks:
        written = await extract_and_persist_facts(
            AsyncSessionLocal,
            router=llm_router,
            user_id=user.id,
            user_timezone=user.timezone,
            raw_text=chunk,
            moment_id=None,
        )
        total_written += written

    return TellOut(facts_written=total_written, chunks_processed=len(chunks))
