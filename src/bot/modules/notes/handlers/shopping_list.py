# src/bot/modules/notes/handlers/shopping_list.py
import logging

from aiogram import Bot, F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hitalic

from .....database import note_repo
from ..common_utils.callbacks import ShoppingListAction
from ..keyboards import get_shopping_list_keyboard
from .list_view import display_notes_list_page

logger = logging.getLogger(__name__)
router = Router()


async def _update_all_shared_views(note_id: int, bot: Bot):
    """
    Обновляет все открытые сообщения со списком покупок у всех участников,
    чтобы обеспечить синхронизацию в реальном времени.
    """
    note = await note_repo.get_note_by_id(note_id, 0)  # 0 - админский доступ для получения заметки
    if not note: return

    items = note.get('llm_analysis_json', {}).get('items', [])
    is_archived = note.get('is_archived', False)
    keyboard = get_shopping_list_keyboard(note_id, items, is_archived)

    message_ids_to_update = await note_repo.get_shared_message_ids(note_id)

    for record in message_ids_to_update:
        user_id, message_id = record['user_id'], record['message_id']
        try:
            await bot.edit_message_reply_markup(
                chat_id=user_id,
                message_id=message_id,
                reply_markup=keyboard
            )
        except TelegramBadRequest as e:
            # Игнорируем ошибку "message is not modified"
            if "message is not modified" in str(e):
                continue
            logger.warning(f"Не удалось обновить view списка покупок для user {user_id} msg {message_id}: {e}")
            # Если сообщение не найдено, удаляем его из нашей БД
            await note_repo.delete_shared_message_id(note_id, user_id)
        except Exception as e:
            logger.error(f"Критическая ошибка при обновлении view списка покупок для {user_id}: {e}")
            await note_repo.delete_shared_message_id(note_id, user_id)


async def render_shopping_list(note_id: int, message: types.Message, user_id: int):
    """Отображает или обновляет сообщение со списком покупок."""
    note = await note_repo.get_note_by_id(note_id, user_id)
    if not note:
        await message.answer("Ошибка: не удалось найти данные списка.")
        return

    items = note.get('llm_analysis_json', {}).get('items', [])
    is_archived = note.get('is_archived', False)
    is_owner = note.get('owner_id') == user_id

    shared_text = "" if is_owner else f"\n{hitalic('(Список доступен вам по ссылке)')}"
    list_title = note.get('summary_text') or 'Ваш список покупок'
    text_to_send = f"🛒 {hbold(list_title)}:{shared_text}"

    keyboard = get_shopping_list_keyboard(note_id, items, is_archived)

    try:
        # Пытаемся отредактировать существующее сообщение
        await message.edit_text(text_to_send, reply_markup=keyboard)
    except (TelegramBadRequest, AttributeError):
        # Если не вышло, отправляем новое
        message = await message.answer(text_to_send, reply_markup=keyboard)

    # Сохраняем/обновляем ID сообщения для будущей синхронизации
    await note_repo.store_shared_message_id(note_id, user_id, message.message_id)


@router.callback_query(ShoppingListAction.filter(F.action == "show"))
async def show_shopping_list_handler(callback: types.CallbackQuery, callback_data: ShoppingListAction):
    """Показывает список покупок (вызывается из карточки заметки)."""
    await render_shopping_list(callback_data.note_id, callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "show_active_shopping_list")
async def show_active_shopping_list_from_profile(callback: types.CallbackQuery):
    """Показывает активный список покупок (вызывается из профиля)."""
    active_list = await note_repo.get_active_shopping_list(callback.from_user.id)
    if not active_list:
        await callback.answer("У вас нет активного списка покупок.", show_alert=True)
        return

    await render_shopping_list(active_list['note_id'], callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(ShoppingListAction.filter(F.action == "toggle"))
async def toggle_shopping_list_item_handler(callback: types.CallbackQuery, callback_data: ShoppingListAction, bot: Bot):
    """Отмечает/снимает отметку с пункта списка."""
    note_id = callback_data.note_id
    item_index = callback_data.item_index

    note = await note_repo.get_note_by_id(note_id, callback.from_user.id)
    if not note or note.get('is_archived'):
        await callback.answer("Этот список уже в архиве.", show_alert=True)
        return

    llm_json = note.get('llm_analysis_json', {})
    items = llm_json.get('items', [])

    if 0 <= item_index < len(items):
        items[item_index]['checked'] = not items[item_index].get('checked', False)
        item_name = items[item_index]['item_name']
        status = "Отмечено" if items[item_index]['checked'] else "Снята отметка"
        await callback.answer(f"{status}: {item_name}")
    else:
        await callback.answer("Ошибка: товар не найден.", show_alert=True)
        return

    llm_json['items'] = items
    await note_repo.update_note_llm_json(note_id, llm_json)

    # Запускаем обновление вида у всех участников
    await _update_all_shared_views(note_id, bot)


@router.callback_query(ShoppingListAction.filter(F.action == "archive"))
async def archive_shopping_list_handler(callback: types.CallbackQuery, callback_data: ShoppingListAction,
                                        state: FSMContext, bot: Bot):
    """Завершает список покупок и переносит его в архив."""
    note_id = callback_data.note_id

    # Завершаем список
    success = await note_repo.set_note_completed_status(note_id, True)
    if not success:
        await callback.answer("❌ Не удалось заархивировать список.", show_alert=True)
        return

    await callback.answer("✅ Список покупок завершен и перенесен в архив.", show_alert=False)

    # Отправляем уведомление владельцу, если список завершил не он
    note = await note_repo.get_note_by_id(note_id, 0)  # Админский доступ, чтобы получить владельца
    if note and note.get('owner_id') != callback.from_user.id:
        try:
            completer_name = hbold(callback.from_user.first_name)
            await bot.send_message(
                note.get('owner_id'),
                f"✅ Ваш список покупок '{hitalic(note.get('summary_text'))}' был завершен пользователем {completer_name}."
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить владельца {note.get('owner_id')} о завершении списка: {e}")

    # Возвращаем пользователя к списку активных заметок
    await display_notes_list_page(callback.message, callback.from_user.id, 1, state, is_archive_list=False)