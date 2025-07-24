# src/web/api/shopping_list.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from aiogram import Bot
import asyncio

from src.database import note_repo
from .dependencies import get_current_user
from .schemas import ShoppingListNote, ShoppingListItemUpdate, ShoppingListItemAddRequest
# Убираем прямой импорт хендлера, будем импортировать новый сервис
from src.bot.modules.notes.handlers.shopping_list import _background_sync_for_others

router = APIRouter()


async def get_full_shopping_list(user_id: int) -> dict:
    """Вспомогательная функция для получения списка покупок с участниками."""
    active_list = await note_repo.get_active_shopping_list(user_id)
    if not active_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Активный список покупок не найден."
        )

    participants = await note_repo.get_shared_note_participants(active_list['note_id'])
    active_list['participants'] = participants
    return active_list


@router.get("", response_model=ShoppingListNote, tags=["Shopping List"])
async def get_active_shopping_list_endpoint(
        current_user: dict = Depends(get_current_user)
):
    """Возвращает активный список покупок для текущего пользователя, включая участников."""
    return await get_full_shopping_list(current_user['telegram_id'])


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
        # Запускаем синхронизацию в фоне, чтобы не ждать ее завершения
        asyncio.create_task(_background_sync_for_others(bot, note_id, user_id))

    return await get_full_shopping_list(user_id)


@router.post("/items/add", response_model=ShoppingListNote, tags=["Shopping List"])
async def add_shopping_list_item(
        item_add: ShoppingListItemAddRequest,
        current_user: dict = Depends(get_current_user),
        request: Request = None,
):
    """Добавляет новый пункт в список покупок."""
    user_id = current_user['telegram_id']

    active_list = await note_repo.get_or_create_active_shopping_list_note(user_id)
    if not active_list:
        raise HTTPException(status_code=500, detail="Не удалось получить или создать список покупок.")

    note_id = active_list['note_id']
    items = active_list.get("llm_analysis_json", {}).get("items", [])

    new_item = {
        "item_name": item_add.item_name.strip(),
        "checked": False,
        "added_by": user_id
    }
    items.append(new_item)

    new_llm_json = {"items": items}
    await note_repo.update_note_llm_json(note_id, new_llm_json)

    bot: Bot = request.app.state.bot
    if bot:
        # Запускаем синхронизацию в фоне
        asyncio.create_task(_background_sync_for_others(bot, note_id, user_id))

    return await get_full_shopping_list(user_id)


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