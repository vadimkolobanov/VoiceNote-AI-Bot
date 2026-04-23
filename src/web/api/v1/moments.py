"""/api/v1/moments/* — CRUD моментов (PRODUCT_PLAN.md §5.2).

LLM-роутер инжектится через FastAPI dependency и создаётся один раз
на процесс (в ``src.web.app`` в M2-slice-2, сейчас — через build_default_router
с usage_logger='db' на каждый запрос создаётся заново; OK, Provider создаёт
собственные aiohttp-сессии ad hoc).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Moment, User
from src.db.session import get_session
from src.services.llm_router import LLMRouter, build_default_router
from src.services.moments import MomentService
from src.services.moments.service import (
    MomentCreate,
    MomentForbidden,
    MomentNotFound,
    MomentPatch,
)

from .dependencies import get_current_user
from .moments_schemas import (
    MomentBulkIn,
    MomentCreateIn,
    MomentOut,
    MomentPatchIn,
    MomentSnoozeIn,
    MomentsBulkOut,
    MomentsListOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/moments", tags=["moments"])


# --- DI ---------------------------------------------------------------------


def get_llm_router() -> LLMRouter:
    """Lazy instance. В M2-slice-2 вынесем в app.state singleton."""
    return build_default_router(usage_logger_kind="db")


def get_moment_service(
    session: AsyncSession = Depends(get_session),
    llm_router: LLMRouter = Depends(get_llm_router),
) -> MomentService:
    return MomentService(session, llm_router=llm_router)


# --- helpers ----------------------------------------------------------------


def _to_out(m: Moment) -> MomentOut:
    return MomentOut(
        id=m.id,
        client_id=m.client_id,
        raw_text=m.raw_text,
        title=m.title,
        summary=m.summary,
        facets=m.facets or {},
        occurs_at=m.occurs_at,
        rrule=m.rrule,
        rrule_until=m.rrule_until,
        status=m.status,  # type: ignore[arg-type]
        source=m.source,  # type: ignore[arg-type]
        audio_url=m.audio_url,
        created_at=m.created_at,
        updated_at=m.updated_at,
        created_via=m.created_via,  # type: ignore[arg-type]
    )


def _raise_not_found() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "MOMENT_NOT_FOUND", "message": "Moment not found"}},
    )


def _raise_forbidden() -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error": {"code": "FORBIDDEN", "message": "Not your moment"}},
    )


# --- endpoints --------------------------------------------------------------


@router.post("", response_model=MomentOut, status_code=status.HTTP_201_CREATED)
async def create_moment(
    payload: MomentCreateIn,
    user: User = Depends(get_current_user),
    service: MomentService = Depends(get_moment_service),
) -> MomentOut:
    moment = await service.create_from_text(
        user,
        MomentCreate(
            raw_text=payload.raw_text,
            source=payload.source,
            client_id=payload.client_id,
            occurs_at_override=payload.occurs_at,
            rrule_override=payload.rrule,
            audio_url=payload.audio_url,
        ),
    )
    return _to_out(moment)


@router.post("/bulk", response_model=MomentsBulkOut)
async def bulk_create(
    payload: MomentBulkIn,
    user: User = Depends(get_current_user),
    service: MomentService = Depends(get_moment_service),
) -> MomentsBulkOut:
    creates = [
        MomentCreate(
            raw_text=it.raw_text,
            source=it.source,
            client_id=it.client_id,
            occurs_at_override=it.occurs_at,
            rrule_override=it.rrule,
            audio_url=it.audio_url,
        )
        for it in payload.items
    ]
    saved = await service.bulk_create(user, creates)
    return MomentsBulkOut(items=[_to_out(m) for m in saved])


@router.get("", response_model=MomentsListOut)
async def list_moments(
    view: str = Query("timeline", pattern="^(today|timeline|rhythm)$"),
    cursor: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    service: MomentService = Depends(get_moment_service),
) -> MomentsListOut:
    if view == "today":
        items = await service.list_today(user, limit=limit)
    elif view == "rhythm":
        rhythm = await service.list_rhythm(user)
        items = rhythm["habits"] + rhythm["cycles"]
    else:
        items = await service.list_timeline(user, cursor=cursor, limit=limit)

    next_cursor = items[-1].id if len(items) == limit and view == "timeline" else None
    return MomentsListOut(items=[_to_out(m) for m in items], next_cursor=next_cursor)


@router.get("/{moment_id}", response_model=MomentOut)
async def get_moment(
    moment_id: int,
    user: User = Depends(get_current_user),
    service: MomentService = Depends(get_moment_service),
) -> MomentOut:
    try:
        m = await service.get(user, moment_id)
    except MomentNotFound:
        _raise_not_found()
    except MomentForbidden:
        _raise_forbidden()
    return _to_out(m)


@router.patch("/{moment_id}", response_model=MomentOut)
async def patch_moment(
    moment_id: int,
    payload: MomentPatchIn,
    user: User = Depends(get_current_user),
    service: MomentService = Depends(get_moment_service),
) -> MomentOut:
    try:
        m = await service.patch(
            user,
            moment_id,
            MomentPatch(
                raw_text=payload.raw_text,
                title=payload.title,
                summary=payload.summary,
                occurs_at=payload.occurs_at,
                rrule=payload.rrule,
                rrule_until=payload.rrule_until,
                status=payload.status,
                facets=payload.facets,
            ),
        )
    except MomentNotFound:
        _raise_not_found()
    except MomentForbidden:
        _raise_forbidden()
    return _to_out(m)


@router.delete("/{moment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_moment(
    moment_id: int,
    user: User = Depends(get_current_user),
    service: MomentService = Depends(get_moment_service),
) -> Response:
    try:
        await service.soft_delete(user, moment_id)
    except MomentNotFound:
        _raise_not_found()
    except MomentForbidden:
        _raise_forbidden()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{moment_id}/complete", response_model=MomentOut)
async def complete_moment(
    moment_id: int,
    user: User = Depends(get_current_user),
    service: MomentService = Depends(get_moment_service),
) -> MomentOut:
    try:
        m = await service.complete(user, moment_id)
    except MomentNotFound:
        _raise_not_found()
    except MomentForbidden:
        _raise_forbidden()
    return _to_out(m)


@router.post("/{moment_id}/snooze", response_model=MomentOut)
async def snooze_moment(
    moment_id: int,
    payload: MomentSnoozeIn,
    user: User = Depends(get_current_user),
    service: MomentService = Depends(get_moment_service),
) -> MomentOut:
    try:
        m = await service.snooze(user, moment_id, payload.until)
    except MomentNotFound:
        _raise_not_found()
    except MomentForbidden:
        _raise_forbidden()
    return _to_out(m)
