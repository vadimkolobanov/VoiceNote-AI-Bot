"""/api/v1/facts/* — CRUD фактов (PRODUCT_PLAN.md §5.2, экран S15).

Факты извлекаются async-job'ом для Pro-юзеров (§6.4) — извлечение будет в
M3. Здесь — чтение, ручное создание/редактирование/удаление.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Fact, User
from src.db.session import get_session

from .dependencies import get_current_user

router = APIRouter(prefix="/facts", tags=["facts"])


# --- schemas ---------------------------------------------------------------


class FactOut(BaseModel):
    id: int
    kind: str
    key: str
    value: dict[str, Any]
    confidence: float
    source_moment_ids: list[int]
    created_at: datetime
    updated_at: datetime


class FactCreateIn(BaseModel):
    kind: str = Field(pattern="^(person|place|preference|schedule|other)$")
    key: str = Field(min_length=1, max_length=128)
    value: dict[str, Any]
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class FactPatchIn(BaseModel):
    kind: Optional[str] = Field(default=None, pattern="^(person|place|preference|schedule|other)$")
    key: Optional[str] = Field(default=None, max_length=128)
    value: Optional[dict[str, Any]] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


def _to_out(f: Fact) -> FactOut:
    return FactOut(
        id=f.id,
        kind=f.kind,
        key=f.key,
        value=f.value,
        confidence=f.confidence,
        source_moment_ids=list(f.source_moment_ids or []),
        created_at=f.created_at,
        updated_at=f.updated_at,
    )


# --- endpoints -------------------------------------------------------------


@router.get("", response_model=list[FactOut])
async def list_facts(
    kind: Optional[str] = Query(
        default=None, pattern="^(person|place|preference|schedule|other)$"
    ),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[FactOut]:
    stmt = select(Fact).where(Fact.user_id == user.id)
    if kind is not None:
        stmt = stmt.where(Fact.kind == kind)
    stmt = stmt.order_by(Fact.kind, Fact.key)
    rows = (await session.scalars(stmt)).all()
    return [_to_out(f) for f in rows]


@router.post("", response_model=FactOut, status_code=status.HTTP_201_CREATED)
async def create_fact(
    payload: FactCreateIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FactOut:
    existing = await session.scalar(
        select(Fact).where(
            Fact.user_id == user.id,
            Fact.kind == payload.kind,
            Fact.key == payload.key,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "FACT_ALREADY_EXISTS",
                    "message": "A fact with this kind+key already exists",
                }
            },
        )
    fact = Fact(
        user_id=user.id,
        kind=payload.kind,
        key=payload.key,
        value=payload.value,
        confidence=payload.confidence,
        source_moment_ids=[],
    )
    session.add(fact)
    await session.flush()
    return _to_out(fact)


@router.patch("/{fact_id}", response_model=FactOut)
async def patch_fact(
    fact_id: int,
    payload: FactPatchIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FactOut:
    fact = await session.get(Fact, fact_id)
    if fact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "FACT_NOT_FOUND"}})
    if fact.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": {"code": "FORBIDDEN"}})

    if payload.kind is not None:
        fact.kind = payload.kind
    if payload.key is not None:
        fact.key = payload.key
    if payload.value is not None:
        fact.value = payload.value
    if payload.confidence is not None:
        fact.confidence = payload.confidence
    return _to_out(fact)


@router.delete("/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fact(
    fact_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    fact = await session.get(Fact, fact_id)
    if fact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "FACT_NOT_FOUND"}})
    if fact.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": {"code": "FORBIDDEN"}})
    await session.delete(fact)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
