# src/web/api/notes.py
from fastapi import APIRouter, Depends, Query, HTTPException, status, Request, Body
from datetime import datetime
import pytz
from aiogram import Bot
from pydantic import BaseModel, Field

from src.database import note_repo, reminder_repo
from src.core.config import NOTES_PER_PAGE
from .dependencies import get_current_user
from .schemas import (
    PaginatedNotesResponse, Note, NoteCreateRequest, NoteUpdateRequest
)
# M0: src/bot/modules/notes/ удалён (docs/PRODUCT_PLAN.md §16.2).
# Endpoint останется в /api/v1/notes до M2, после чего заменяется /moments (§5.2).
async def process_and_save_note(*args, **kwargs):
    raise NotImplementedError(
        "process_and_save_note удалён в M0. "
        "В M2 будет заменён на /moments pipeline (docs/PRODUCT_PLAN.md §5.2, §6.1)."
    )
from src.services.llm import search_notes_with_llm

router = APIRouter()


@router.post("", response_model=Note, status_code=status.HTTP_201_CREATED, tags=["Notes"])
async def create_note_from_api(
    request_data: NoteCreateRequest,
    current_user: dict = Depends(get_current_user),
    request: Request = None
):
    """
    Создает новую заметку через API. Авторизация происходит по JWT токену.
    """
    bot: Bot = request.app.state.bot
    telegram_id = current_user['telegram_id']

    success, user_message, new_note_dict, _ = await process_and_save_note(
        bot=bot,
        telegram_id=telegram_id,
        text_to_process=request_data.text,
        message_date=datetime.now(pytz.utc)
    )

    if not success or not new_note_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=user_message
        )
    return new_note_dict


@router.get("", response_model=PaginatedNotesResponse, tags=["Notes"])
async def get_notes(
        current_user: dict = Depends(get_current_user),
        page: int = Query(1, ge=1),
        per_page: int = Query(NOTES_PER_PAGE, ge=1, le=100),
        archived: bool = False,
        type: str | None = Query(
            default='note',
            description="Filter: note | task | idea | shopping | all",
            pattern="^(note|task|idea|shopping|all)$",
        ),
):
    """Возвращает пагинированный список записей пользователя.

    По умолчанию — только простые заметки (`type='note'`). Для ленты задач
    мобилка передаёт `type=task` (они отсортированы по due_date). `type=all`
    возвращает всё (для обратной совместимости).
    """
    user_id = current_user['telegram_id']
    effective_type = None if type == 'all' else type
    notes, total_items = await note_repo.get_paginated_notes_for_user(
        telegram_id=user_id,
        page=page,
        per_page=per_page,
        archived=archived,
        note_type=effective_type,
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


@router.get("/{note_id}", response_model=Note, tags=["Notes"])
async def get_note_by_id(note_id: int, current_user: dict = Depends(get_current_user)):
    """Возвращает одну заметку по ID."""
    note = await note_repo.get_note_by_id(note_id, current_user['telegram_id'])
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found or access denied")
    return note


@router.put("/{note_id}", response_model=Note, tags=["Notes"])
async def update_note(note_id: int, request_data: NoteUpdateRequest, current_user: dict = Depends(get_current_user)):
    """Обновляет текст заметки."""
    note = await note_repo.get_note_by_id(note_id, current_user['telegram_id'])
    if not note or note.get('owner_id') != current_user['telegram_id']:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found or you are not the owner")

    success = await note_repo.update_note_text(note_id, request_data.text, current_user['telegram_id'])
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update note")

    updated_note = await note_repo.get_note_by_id(note_id, current_user['telegram_id'])
    return updated_note


class NotePatchRequest(BaseModel):
    """Partial update. Все поля опциональные. Явные sentinels для сброса полей.

    - `clear_due_date=True` → выставить due_date в NULL
    - `clear_recurrence=True` → выставить recurrence_rule в NULL
    """
    text: str | None = Field(default=None, min_length=1)
    category: str | None = None
    type: str | None = Field(default=None, pattern="^(note|task|idea|shopping)$")
    due_date: datetime | None = None
    clear_due_date: bool = False
    recurrence_rule: str | None = None
    clear_recurrence: bool = False


@router.patch("/{note_id}", response_model=Note, tags=["Notes"])
async def patch_note(
    note_id: int,
    payload: NotePatchRequest,
    current_user: dict = Depends(get_current_user),
    request: Request = None,
):
    """Частичное обновление заметки/задачи. Меняет только переданные поля."""
    note = await note_repo.get_note_by_id(note_id, current_user['telegram_id'])
    if not note or note.get('owner_id') != current_user['telegram_id']:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found or you are not the owner")

    ok = await note_repo.update_note_fields(
        note_id,
        current_user['telegram_id'],
        text=payload.text,
        category=payload.category,
        note_type=payload.type,
        due_date=payload.due_date,
        clear_due_date=payload.clear_due_date,
        recurrence_rule=payload.recurrence_rule,
        clear_recurrence=payload.clear_recurrence,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to patch note")

    updated_note = await note_repo.get_note_by_id(note_id, current_user['telegram_id'])

    # Sync scheduler + reminders, если менялась due_date / recurrence
    if payload.due_date is not None or payload.clear_due_date or \
       payload.recurrence_rule is not None or payload.clear_recurrence:
        bot: Bot = request.app.state.bot if request else None
        if bot is not None:
            from src.services.scheduler import add_reminder_to_scheduler, remove_reminder_from_scheduler
            if updated_note and updated_note.get('due_date'):
                from src.database import user_repo
                user = await user_repo.get_user_profile(current_user['telegram_id'])
                add_reminder_to_scheduler(bot, {**updated_note, **(user or {})})
            else:
                remove_reminder_from_scheduler(note_id)
                await reminder_repo.delete_note_reminder(note_id)

    return updated_note


@router.post("/{note_id}/complete", response_model=Note, tags=["Notes"])
async def complete_note(note_id: int, current_user: dict = Depends(get_current_user)):
    """Помечает заметку как выполненную."""
    await note_repo.set_note_completed_status(note_id, True)
    updated_note = await note_repo.get_note_by_id(note_id, current_user['telegram_id'])
    if not updated_note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return updated_note


@router.post("/{note_id}/unarchive", response_model=Note, tags=["Notes"])
async def unarchive_note(note_id: int, current_user: dict = Depends(get_current_user)):
    """Восстанавливает заметку из архива."""
    await note_repo.set_note_archived_status(note_id, False)
    updated_note = await note_repo.get_note_by_id(note_id, current_user['telegram_id'])
    if not updated_note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return updated_note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Notes"])
async def delete_note(note_id: int, current_user: dict = Depends(get_current_user)):
    """Окончательно удаляет заметку."""
    note = await note_repo.get_note_by_id(note_id, current_user['telegram_id'])
    if not note or note.get('owner_id') != current_user['telegram_id']:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found or you are not the owner")

    success = await note_repo.delete_note(note_id, current_user['telegram_id'])
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete note")
    return None


@router.post("/search", tags=["Notes"])
async def search_notes(
    query: str = Body(..., embed=True, min_length=1, description="Поисковый запрос пользователя"),
    current_user: dict = Depends(get_current_user),
    archived: bool = False,
    max_results: int = 10
):
    """
    Ищет заметки пользователя по запросу с помощью ИИ (DeepSeek).
    Возвращает список релевантных заметок с кратким описанием.
    """
    notes = await note_repo.get_all_notes_for_user(current_user["telegram_id"], archived=archived)
    found = await search_notes_with_llm(notes, query, max_results=max_results)
    return {"results": found}