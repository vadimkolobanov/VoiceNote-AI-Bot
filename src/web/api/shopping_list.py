# src/web/api/shopping_list.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from aiogram import Bot
import asyncio

from src.database import note_repo
from .dependencies import get_current_user
from .schemas import ShoppingListNote, ShoppingListItemUpdate
from src.bot.modules.notes.handlers import shopping_list as bot_shopping_list_handler

router = APIRouter()


@router.get("", response_model=ShoppingListNote, tags=["Shopping List"])
async def get_active_shopping_list(
        current_user: dict = Depends(get_current_user)
):
    """Возвращает активный список покупок для текущего пользователя, включая участников."""
    user_id = current_user['telegram_id']
    active_list = await note_repo.get_active_shopping_list(user_id)
    if not active_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Активный список покупок не найден."
        )

    participants = await note_repo.get_shared_note_participants(active_list['note_id'])
    active_list['participants'] = participants

    return active_list


@router.post("/items", response_model=ShoppingListNote, tags=["Shopping List"])
async def toggle_shopping_list_item(
        item_update: ShoppingListItemUpdate,
        current_user: dict = Depends(get_current_user),
        request: Request = None,
):
    """Отмечает/снимает отметку с пункта в списке покупок."""
    user_id = current_user['telegram_id']
    active_list = await note_repo.get_active_shopping_list(user_id)
    if not active_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Активный список покупок не найден.")

    note_id = active_list['note_id']
    items = active_list.get("llm_analysis_json", {}).get("items", [])

    if not (0 <= item_update.item_index < len(items)):
        raise HTTPException(status_code=400, detail="Неверный индекс элемента.")

    items[item_update.item_index]['checked'] = item_update.checked

    new_llm_json = {"items": items}
    await note_repo.update_note_llm_json(note_id, new_llm_json)

    bot: Bot = request.app.state.bot
    if bot:
        asyncio.create_task(bot_shopping_list_handler.sync_shopping_list_for_all(bot, note_id))

    updated_list = await note_repo.get_note_by_id(note_id, 0)
    if updated_list:
        participants = await note_repo.get_shared_note_participants(updated_list['note_id'])
        updated_list['participants'] = participants
    return updated_list


@router.post("/archive", status_code=status.HTTP_204_NO_CONTENT, tags=["Shopping List"])
async def archive_shopping_list(
        current_user: dict = Depends(get_current_user)
):
    """Архивирует (завершает) текущий список покупок."""
    user_id = current_user['telegram_id']
    active_list = await note_repo.get_active_shopping_list(user_id)
    if not active_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Активный список покупок не найден.")

    await note_repo.set_note_archived_status(active_list['note_id'], True)
    return None