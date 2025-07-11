# src/web/api/notes.py
from fastapi import APIRouter, Depends, Query

from src.database import note_repo, user_repo
from src.core.config import NOTES_PER_PAGE
from .dependencies import get_current_user
from .schemas import PaginatedNotesResponse

router = APIRouter()


@router.get("", response_model=PaginatedNotesResponse, tags=["Notes"])
async def get_notes(
        current_user: dict = Depends(get_current_user),
        page: int = Query(1, ge=1),
        per_page: int = Query(NOTES_PER_PAGE, ge=1, le=100),
        archived: bool = False
):
    """
    Возвращает пагинированный список заметок (активных или архивных)
    для текущего аутентифицированного пользователя.
    """
    user_id = current_user['telegram_id']
    notes, total_items = await note_repo.get_paginated_notes_for_user(
        telegram_id=user_id,
        page=page,
        per_page=per_page,
        archived=archived
    )

    total_pages = (total_items + per_page - 1) // per_page
    if total_pages == 0:
        total_pages = 1

    return {
        "items": notes,
        "total": total_items,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages
    }