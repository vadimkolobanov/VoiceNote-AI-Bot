# src/web/api/notes.py
from fastapi import APIRouter, Depends, Query, HTTPException, status, Request, Body
from datetime import datetime
import pytz
from aiogram import Bot

from src.database import note_repo
from src.core.config import NOTES_PER_PAGE
from .dependencies import get_current_user
from .schemas import (
    PaginatedNotesResponse, Note, NoteCreateRequest, NoteUpdateRequest
)
from src.bot.modules.notes.services import process_and_save_note
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
        archived: bool = False
):
    """Возвращает пагинированный список заметок пользователя."""
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