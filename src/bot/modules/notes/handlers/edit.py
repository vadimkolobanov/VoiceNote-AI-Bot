# src/bot/modules/notes/handlers/edit.py
import logging

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold

from .....database import note_repo
from ....common_utils.callbacks import NoteAction
from ....common_utils.states import NoteEditingStates
from .list_view import view_note_detail_handler, display_notes_list_page

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(NoteAction.filter(F.action == "edit"))
async def start_note_edit_handler(callback: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    """Начинает сценарий редактирования текста заметки."""
    await state.clear()
    await state.set_state(NoteEditingStates.awaiting_new_text)
    await state.update_data(
        note_id=callback_data.note_id,
        page=callback_data.page,
        target_list=callback_data.target_list
    )

    note = await note_repo.get_note_by_id(callback_data.note_id, callback.from_user.id)
    if not note:
        await callback.answer("Заметка не найдена.", show_alert=True)
        await state.clear()
        return

    text = (
        f"✏️ {hbold('Редактирование заметки')} #{note['note_id']}\n\n"
        f"Пришлите новый текст для этой заметки. "
        f"Текущий текст:\n"
        f"<code>{note['corrected_text']}</code>\n\n"
        "Для отмены введите /cancel."
    )

    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.message(NoteEditingStates.awaiting_new_text, F.text, ~F.text.startswith('/'))
async def process_new_note_text_handler(message: types.Message, state: FSMContext):
    """Обрабатывает новый текст и обновляет заметку."""
    fsm_data = await state.get_data()
    note_id = fsm_data.get('note_id')
    page = fsm_data.get('page', 1)
    target_list = fsm_data.get('target_list', 'active')

    if not note_id:
        await message.reply("Произошла ошибка, ID заметки не найден. Попробуйте снова.")
        await state.clear()
        return

    new_text = message.text.strip()
    success = await note_repo.update_note_text(note_id, new_text, message.from_user.id)

    await state.clear()

    if success:
        await message.answer("✅ Текст заметки успешно обновлен!")
        # Возвращаемся к просмотру обновленной заметки
        await view_note_detail_handler(message, state, note_id=note_id)
    else:
        await message.answer("❌ Не удалось обновить текст заметки. Возможно, вы не являетесь ее владельцем.")
        # Возвращаемся к списку
        await display_notes_list_page(
            message=message,
            user_id=message.from_user.id,
            page=page,
            archived=(target_list == 'archive'),
            is_callback=False
        )


@router.message(StateFilter(NoteEditingStates), Command("cancel"))
async def cancel_edit_handler(message: types.Message, state: FSMContext):
    """Отменяет процесс редактирования."""
    fsm_data = await state.get_data()
    note_id = fsm_data.get('note_id')
    await state.clear()

    await message.answer("🚫 Редактирование отменено.")

    if note_id:
        # Возвращаемся к просмотру заметки без изменений
        await view_note_detail_handler(message, state, note_id=note_id)
    else:
        # Если что-то пошло не так, просто показываем список
        await display_notes_list_page(message, message.from_user.id)