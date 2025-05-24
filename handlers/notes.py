# handlers/notes.py
import logging
from datetime import datetime

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hcode, hbold, hitalic

from config import MAX_NOTES_MVP, NOTES_PER_PAGE
from inline_keyboards import (
    get_notes_list_display_keyboard,  # Новая клавиатура для списка
    NoteAction,  # Обновленный CallbackFactory
    PageNavigation,  # Новый CallbackFactory для пагинации
    get_main_menu_keyboard,
    get_note_confirmation_keyboard,  # Используем эту
    get_note_view_actions_keyboard
)
import database_setup as db
from states import NoteCreationStates, NoteNavigationStates

logger = logging.getLogger(__name__)
router = Router()


# --- FSM HANDLERS FOR NOTE CREATION (Confirm/Cancel) ---
@router.callback_query(NoteCreationStates.awaiting_confirmation, F.data == "confirm_save_note")
async def confirm_save_note_fsm_handler(callback_query: CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение сохранения заметки из состояния FSM."""
    user_data = await state.get_data()
    telegram_id = callback_query.from_user.id

    active_notes_count = await db.count_active_notes_for_user(telegram_id)
    if active_notes_count >= MAX_NOTES_MVP:
        await callback_query.message.edit_text(
            f"⚠️ Достигнут лимит в {MAX_NOTES_MVP} заметок для MVP.\n"
            "Чтобы добавить новую, пожалуйста, удалите одну из существующих.",
            reply_markup=None
        )
        await callback_query.answer("Лимит заметок достигнут", show_alert=True)
        await state.clear()
        await callback_query.message.answer("Чем еще могу помочь?", reply_markup=get_main_menu_keyboard())
        return

    original_stt_text = user_data.get("original_stt_text")
    corrected_text_to_save = user_data.get("corrected_text_for_save")
    llm_analysis_data = user_data.get("llm_analysis_json")
    audio_file_id = user_data.get("original_audio_telegram_file_id")
    note_creation_time = user_data.get("voice_message_date")

    due_date_obj = None
    if llm_analysis_data and "dates_times" in llm_analysis_data and llm_analysis_data["dates_times"]:
        first_date_entry = llm_analysis_data["dates_times"][0]
        if "absolute_datetime_start" in first_date_entry:
            try:
                due_date_str = first_date_entry["absolute_datetime_start"]
                if due_date_str.endswith('Z'):
                    due_date_str = due_date_str[:-1] + "+00:00"
                due_date_obj = datetime.fromisoformat(due_date_str)
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse due_date '{first_date_entry['absolute_datetime_start']}': {e}")

    note_id = await db.create_note(
        telegram_id=telegram_id,
        original_stt_text=original_stt_text,
        corrected_text=corrected_text_to_save,
        llm_analysis_json=llm_analysis_data,
        original_audio_telegram_file_id=audio_file_id,
        note_taken_at=note_creation_time,
        due_date=due_date_obj
    )

    if note_id:
        await callback_query.message.edit_text(
            f"✅ Заметка #{note_id} успешно сохранена!\n\n{hcode(corrected_text_to_save)}",
            parse_mode="HTML", reply_markup=None
        )
    else:
        await callback_query.message.edit_text(
            "❌ Произошла ошибка при сохранении заметки.", reply_markup=None
        )

    await callback_query.answer()
    await state.clear()
    await callback_query.message.answer("Чем еще могу помочь?", reply_markup=get_main_menu_keyboard())


@router.callback_query(NoteCreationStates.awaiting_confirmation, F.data == "cancel_save_note")
async def cancel_save_note_fsm_handler(callback_query: CallbackQuery, state: FSMContext):
    """Обрабатывает отмену сохранения заметки из состояния FSM."""
    await callback_query.message.edit_text("🚫 Сохранение отменено.", reply_markup=None)
    await callback_query.answer()
    await state.clear()
    await callback_query.message.answer("Чем еще могу помочь?", reply_markup=get_main_menu_keyboard())


# --- NOTES LIST, PAGINATION, VIEW, DELETE ---

async def _display_notes_list_page(
        target_message: types.Message,  # Сообщение, которое будем редактировать или в которое ответим
        telegram_id: int,
        page_num: int,
        state: FSMContext
):
    """Отображает страницу со списком заметок и кнопками пагинации."""
    await state.set_state(NoteNavigationStates.browsing_notes)
    await state.update_data(current_notes_page=page_num)

    notes_on_page, total_notes_count = await db.get_paginated_notes_for_user(
        telegram_id=telegram_id,
        page=page_num,
        per_page=NOTES_PER_PAGE,
        archived=False
    )

    total_pages = (total_notes_count + NOTES_PER_PAGE - 1) // NOTES_PER_PAGE
    if total_pages == 0 and total_notes_count == 0: total_pages = 1  # Если заметок нет, то 1 страница "пусто"
    if page_num > total_pages and total_pages > 0:  # Если текущая страница больше максимальной (например, после удаления)
        page_num = total_pages
        await state.update_data(current_notes_page=page_num)
        notes_on_page, total_notes_count = await db.get_paginated_notes_for_user(
            telegram_id=telegram_id, page=page_num, per_page=NOTES_PER_PAGE, archived=False
        )

    text_content: str
    if not notes_on_page and page_num == 1:
        text_content = "У вас пока нет сохраненных заметок."
    elif not notes_on_page and page_num > 1:  # Могло случиться, если удалили все на последней странице
        text_content = f"На странице {page_num} заметок нет. Возможно, стоит вернуться назад."
    else:
        text_content = f"📝 {hbold(f'Ваши заметки (Стр. {page_num}/{total_pages}):')}"
        # Текст заметок будет в кнопках

    keyboard = get_notes_list_display_keyboard(notes_on_page, page_num, total_pages)

    try:
        await target_message.edit_text(text_content, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:  # Если не удалось отредактировать (старое сообщение, нет прав и т.д.)
        logger.info(f"Не удалось отредактировать сообщение для списка заметок, отправляю новое: {e}")
        await target_message.answer(text_content, reply_markup=keyboard, parse_mode="HTML")


# Обработчик для кнопки "Мои заметки" и кнопок пагинации
@router.callback_query(PageNavigation.filter(F.target == "notes"))
async def notes_list_paginated_handler(
        callback_query: types.CallbackQuery,
        callback_data: PageNavigation,
        state: FSMContext
):
    """Отображает список заметок с пагинацией."""
    await callback_query.answer()  # Сразу отвечаем на callback
    await _display_notes_list_page(
        target_message=callback_query.message,
        telegram_id=callback_query.from_user.id,
        page_num=callback_data.page,
        state=state
    )


# Команда /my_notes для вызова списка заметок
@router.message(Command("my_notes"))
async def cmd_my_notes(message: types.Message, state: FSMContext):
    """Команда для отображения списка заметок (начинаем с 1-й страницы)."""
    await _display_notes_list_page(
        target_message=message,
        telegram_id=message.from_user.id,
        page_num=1,
        state=state
    )


@router.callback_query(F.data == "main_menu_from_notes")  # Кнопка "Главное меню" из списка заметок
async def back_to_main_menu_from_notes_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню из просмотра списка заметок."""
    await state.clear()
    # Для кнопки "Главное меню" лучше всего отправить новое сообщение, а старое со списком удалить или отредактировать
    try:
        await callback_query.message.edit_text(
            "Вы в главном меню. Чем могу помочь?",  # или удалить и отправить новое
            reply_markup=get_main_menu_keyboard()
        )
    except Exception:
        await callback_query.message.answer(
            "Вы в главном меню. Чем могу помочь?",
            reply_markup=get_main_menu_keyboard()
        )
    await callback_query.answer()


@router.callback_query(NoteAction.filter(F.action == "view"))
async def view_note_detail_handler(
        callback_query: types.CallbackQuery,
        callback_data: NoteAction,
        state: FSMContext
):
    """Отображает детальную информацию о выбранной заметке."""
    note_id = callback_data.note_id
    current_page = callback_data.page  # Страница, с которой пользователь пришел
    telegram_id = callback_query.from_user.id

    await state.set_state(NoteNavigationStates.browsing_notes)  # Остаемся в состоянии навигации
    await state.update_data(current_notes_page=current_page)

    note = await db.get_note_by_id(note_id, telegram_id)

    if not note:
        await callback_query.answer("Заметка не найдена или удалена.", show_alert=True)
        # Возвращаем пользователя к списку заметок на предыдущую страницу
        await _display_notes_list_page(callback_query.message, telegram_id, current_page, state)
        return

    note_taken_at_utc = note.get('note_taken_at') or note['created_at']
    note_date_str = note_taken_at_utc.strftime("%d.%m.%Y %H:%M UTC")

    text = f"📌 {hbold(f'Заметка #{note['note_id']}')}\n\n"
    text += f"Созд./Записана: {hitalic(note_date_str)}\n"
    if note.get('updated_at') and note['updated_at'] != note['created_at']:  # Если обновлялась
        text += f"Обновлена: {hitalic(note['updated_at'].strftime('%d.%m.%Y %H:%M UTC'))}\n"

    if note.get('due_date'):
        due_date_str = note['due_date'].strftime("%d.%m.%Y %H:%M UTC")
        text += f"Срок до: {hitalic(due_date_str)}\n"

    text += f"\n{hbold('Текст заметки:')}\n{hcode(note['corrected_text'])}\n"

    # Показываем исходный текст, если он отличается от исправленного
    if note.get('original_stt_text') and note['original_stt_text'] != note['corrected_text']:
        text += f"\n{hbold('Исходный текст (STT):')}\n{hcode(note['original_stt_text'])}\n"

    # Вывод JSON анализа LLM (если нужно для отладки или информации)
    # llm_data = note.get('llm_analysis_json')
    # if llm_data:
    #     try:
    #         formatted_llm_data = json.dumps(llm_data, indent=2, ensure_ascii=False)
    #         text += f"\n{hbold('AI Анализ:')}\n<pre><code class=\"language-json\">{formatted_llm_data}</code></pre>\n" # Для HTML
    #     except Exception:
    #         text += f"\n{hbold('AI Анализ (сырой):')}\n{hcode(str(llm_data))}\n"

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_note_view_actions_keyboard(note['note_id'], current_page)
    )
    await callback_query.answer()


@router.callback_query(NoteAction.filter(F.action == "delete"))
async def delete_note_action_handler(
        callback_query: types.CallbackQuery,
        callback_data: NoteAction,
        state: FSMContext
):
    """Обрабатывает удаление заметки (из детального просмотра или списка)."""
    note_id_to_delete = callback_data.note_id
    page_to_return_to = callback_data.page
    telegram_id = callback_query.from_user.id

    if note_id_to_delete is None:
        await callback_query.answer("Ошибка: ID заметки не найден.", show_alert=True)
        return

    deleted = await db.delete_note(note_id_to_delete, telegram_id)

    if deleted:
        await callback_query.answer("🗑️ Заметка удалена!")
        # После удаления обновляем список заметок, оставаясь на той же (или скорректированной) странице
        await _display_notes_list_page(callback_query.message, telegram_id, page_to_return_to, state)
    else:
        await callback_query.answer("❌ Не удалось удалить заметку (возможно, уже удалена).", show_alert=True)
        # Попытаемся обновить список в любом случае
        await _display_notes_list_page(callback_query.message, telegram_id, page_to_return_to, state)