# src/bot/modules/notes/handlers/edit.py
import logging

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter  # <-- Добавляем StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold

# Используем относительные импорты
from .....database import note_repo
from ....common_utils.callbacks import NoteAction
from ....common_utils.states import NoteEditingStates
from ..keyboards import get_category_selection_keyboard
from .list_view import view_note_detail_handler, display_notes_list_page

logger = logging.getLogger(__name__)
router = Router()


# --- Редактирование текста заметки ---

@router.callback_query(NoteAction.filter(F.action == "edit"))
async def start_note_edit_handler(callback: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    """Начинает FSM-сценарий редактирования текста заметки."""
    await state.set_state(NoteEditingStates.awaiting_new_text)
    await state.update_data(
        note_id_to_edit=callback_data.note_id,
        page_to_return_to=callback_data.page,
        is_archive_view=callback_data.target_list == 'archive'
    )
    await callback.message.edit_text(
        f"✏️ {hbold('Редактирование заметки')}\n\n"
        "Пришлите мне новый текст для этой заметки. Я полностью заменю старый текст и попробую заново его проанализировать.\n\n"
        "Для отмены отправьте /cancel.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(StateFilter(NoteEditingStates), Command("cancel"))  # <-- ИСПРАВЛЕНИЕ
async def cancel_note_edit_handler(message: types.Message, state: FSMContext):
    """Отменяет редактирование и возвращает к просмотру заметки."""
    user_data = await state.get_data()
    note_id = user_data.get("note_id_to_edit")

    current_state = await state.get_state()
    logger.info(f"Отмена состояния {current_state} для пользователя {message.from_user.id}")
    await state.clear()

    await message.answer("🚫 Редактирование отменено.")

    # Возвращаемся к просмотру заметки
    if note_id:
        await view_note_detail_handler(message, state, note_id=note_id)


@router.message(NoteEditingStates.awaiting_new_text, F.text)
async def process_note_edit_handler(message: types.Message, state: FSMContext):
    """Принимает новый текст, обновляет заметку и возвращает к списку."""
    user_data = await state.get_data()
    note_id = user_data.get("note_id_to_edit")
    page = user_data.get("page_to_return_to", 1)
    is_archive = user_data.get("is_archive_view", False)
    new_text = message.text

    if len(new_text.strip()) < 3:
        await message.reply("Текст заметки слишком короткий. Попробуйте снова или отмените /cancel.")
        return


    success = await note_repo.update_note_text(note_id, new_text, message.from_user.id)
    await state.clear()

    if success:
        await message.reply(f"✅ Текст заметки #{note_id} успешно обновлен.")
        # Возвращаемся к списку заметок
        await display_notes_list_page(message, message.from_user.id, page, state, is_archive)
    else:
        await message.reply("❌ Произошла ошибка при обновлении заметки.")
        if note_id:
            await view_note_detail_handler(message, state, note_id=note_id)


# --- Смена категории ---

@router.callback_query(NoteAction.filter(F.action == "change_category"))
async def change_category_handler(callback: types.CallbackQuery, callback_data: NoteAction):
    """Показывает клавиатуру для выбора новой категории."""
    await callback.message.edit_text(
        "🗂️ Выберите новую категорию для заметки:",
        reply_markup=get_category_selection_keyboard(
            note_id=callback_data.note_id,
            page=callback_data.page,
            target_list=callback_data.target_list
        )
    )
    await callback.answer()


@router.callback_query(NoteAction.filter(F.action == "set_category"))
async def set_category_handler(callback: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    """Устанавливает новую категорию и возвращает к просмотру заметки."""
    new_category = callback_data.category
    success = await note_repo.update_note_category(callback_data.note_id, new_category)

    if success:
        await callback.answer(f"Категория изменена на '{new_category}'")
    else:
        await callback.answer("❌ Ошибка при смене категории.", show_alert=True)

    # Возвращаемся к просмотру заметки, чтобы увидеть изменения
    await view_note_detail_handler(callback, state)