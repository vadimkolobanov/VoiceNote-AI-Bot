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
    get_notes_list_display_keyboard,
    NoteAction,
    PageNavigation,
    get_main_menu_keyboard,
    get_note_view_actions_keyboard,
    get_confirm_delete_keyboard
)
import database_setup as db
from services.tz_utils import format_datetime_for_user  # <--- НОВЫЙ ИМПОРТ
from states import NoteCreationStates, NoteNavigationStates, NoteEditingStates

logger = logging.getLogger(__name__)
router = Router()


# --- FSM HANDLERS FOR NOTE CREATION (Confirm/Cancel) ---
@router.callback_query(NoteCreationStates.awaiting_confirmation, F.data == "confirm_save_note")
async def confirm_save_note_fsm_handler(callback_query: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    telegram_id = callback_query.from_user.id

    active_notes_count = await db.count_active_notes_for_user(telegram_id)
    if active_notes_count >= MAX_NOTES_MVP:
        await callback_query.message.edit_text(
            f"⚠️ Достигнут лимит в {MAX_NOTES_MVP} заметок для MVP.\n"
            "Чтобы добавить новую, пожалуйста, удалите или архивируйте одну из существующих.",
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
    await callback_query.message.edit_text("🚫 Сохранение отменено.", reply_markup=None)
    await callback_query.answer()
    await state.clear()
    await callback_query.message.answer("Чем еще могу помочь?", reply_markup=get_main_menu_keyboard())


# --- NOTES LIST, PAGINATION, VIEW, ACTIONS ---

async def _display_notes_list_page(
        target_message: types.Message,
        telegram_id: int,
        page_num: int,
        state: FSMContext,
        is_archive_list: bool
):
    await state.set_state(NoteNavigationStates.browsing_notes)
    await state.update_data(current_notes_page=page_num, is_archive_view=is_archive_list)

    notes_on_page, total_notes_count = await db.get_paginated_notes_for_user(
        telegram_id=telegram_id,
        page=page_num,
        per_page=NOTES_PER_PAGE,
        archived=is_archive_list
    )

    total_pages = (total_notes_count + NOTES_PER_PAGE - 1) // NOTES_PER_PAGE
    if total_pages == 0: total_pages = 1

    if page_num > total_pages and total_pages > 0:
        page_num = total_pages
        await state.update_data(current_notes_page=page_num)
        notes_on_page, total_notes_count = await db.get_paginated_notes_for_user(
            telegram_id=telegram_id, page=page_num, per_page=NOTES_PER_PAGE, archived=is_archive_list
        )

    list_type_name = "архивных заметок" if is_archive_list else "заметок"
    if not notes_on_page and page_num == 1:
        text_content = f"У вас пока нет {list_type_name}."
    else:
        title = "🗄️ Ваш архив" if is_archive_list else "📝 Ваши заметки"
        text_content = f"{hbold(f'{title} (Стр. {page_num}/{total_pages}):')}"

    keyboard = get_notes_list_display_keyboard(notes_on_page, page_num, total_pages, is_archive_list)

    try:
        await target_message.edit_text(text_content, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.info(f"Не удалось отредактировать сообщение для списка заметок, отправляю новое: {e}")
        await target_message.answer(text_content, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(PageNavigation.filter(F.target == "notes"))
async def notes_list_paginated_handler(
        callback_query: types.CallbackQuery,
        callback_data: PageNavigation,
        state: FSMContext
):
    await callback_query.answer()
    await _display_notes_list_page(
        target_message=callback_query.message,
        telegram_id=callback_query.from_user.id,
        page_num=callback_data.page,
        state=state,
        is_archive_list=callback_data.archived
    )


@router.message(Command("my_notes"))
async def cmd_my_notes(message: types.Message, state: FSMContext):
    await _display_notes_list_page(
        target_message=message,
        telegram_id=message.from_user.id,
        page_num=1,
        state=state,
        is_archive_list=False
    )


@router.callback_query(F.data == "main_menu_from_notes")
async def back_to_main_menu_from_notes_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback_query.message.edit_text("🏠 Вы в главном меню.", reply_markup=get_main_menu_keyboard())
    except Exception:
        await callback_query.message.answer("🏠 Вы в главном меню.", reply_markup=get_main_menu_keyboard())
    await callback_query.answer()


# <--- ЗДЕСЬ ОСНОВНЫЕ ИЗМЕНЕНИЯ --->
@router.callback_query(NoteAction.filter(F.action == "view"))
async def view_note_detail_handler(
        callback_query: types.CallbackQuery,
        callback_data: NoteAction,
        state: FSMContext
):
    note_id = callback_data.note_id
    current_page = callback_data.page
    target_list = callback_data.target_list
    is_archived_view = target_list == 'archive'
    telegram_id = callback_query.from_user.id

    await state.set_state(NoteNavigationStates.browsing_notes)
    await state.update_data(current_notes_page=current_page, is_archive_view=is_archived_view)

    # Получаем профиль пользователя, чтобы узнать его таймзону
    user_profile = await db.get_user_profile(telegram_id)
    user_timezone = user_profile.get('timezone', 'UTC') if user_profile else 'UTC'

    note = await db.get_note_by_id(note_id, telegram_id)

    if not note:
        await callback_query.answer("Заметка не найдена или удалена.", show_alert=True)
        await _display_notes_list_page(callback_query.message, telegram_id, current_page, state, is_archived_view)
        return

    # --- Форматируем все даты с учетом таймзоны пользователя ---
    note_taken_at_local = format_datetime_for_user(note.get('note_taken_at') or note['created_at'], user_timezone)
    updated_at_local = format_datetime_for_user(note.get('updated_at'), user_timezone)
    due_date_local = format_datetime_for_user(note.get('due_date'), user_timezone)

    status_icon = "🗄️" if note['is_archived'] else "📌"
    text = f"{status_icon} {hbold(f'Заметка #{note['note_id']}')}\n\n"
    text += f"Созд./Записана: {hitalic(note_taken_at_local)}\n"

    # Показываем дату обновления, только если она действительно отличается от даты создания
    if note.get('updated_at') and note['updated_at'].strftime('%Y%m%d%H%M') != note['created_at'].strftime(
            '%Y%m%d%H%M'):
        text += f"Обновлена: {hitalic(updated_at_local)}\n"
    if due_date_local:
        text += f"Срок до: {hitalic(due_date_local)}\n"

    text += f"\n{hbold('Текст заметки:')}\n{hcode(note['corrected_text'])}\n"

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_note_view_actions_keyboard(note['note_id'], current_page, note['is_archived'])
    )
    await callback_query.answer()


# --- NOTE ACTIONS: ARCHIVE, UNARCHIVE, DELETE ---
# (остальные хендлеры без изменений)

@router.callback_query(NoteAction.filter(F.action == "archive"))
async def archive_note_handler(callback_query: CallbackQuery, callback_data: NoteAction, state: FSMContext):
    success = await db.set_note_archived_status(callback_data.note_id, callback_query.from_user.id, archived=True)
    if success:
        await callback_query.answer("🗄️ Заметка перемещена в архив")
    else:
        await callback_query.answer("❌ Ошибка при архивации", show_alert=True)
    await _display_notes_list_page(
        callback_query.message, callback_query.from_user.id, callback_data.page, state, is_archive_list=False
    )


@router.callback_query(NoteAction.filter(F.action == "unarchive"))
async def unarchive_note_handler(callback_query: CallbackQuery, callback_data: NoteAction, state: FSMContext):
    success = await db.set_note_archived_status(callback_data.note_id, callback_query.from_user.id, archived=False)
    if success:
        await callback_query.answer("↩️ Заметка восстановлена из архива")
    else:
        await callback_query.answer("❌ Ошибка при восстановлении", show_alert=True)
    await _display_notes_list_page(
        callback_query.message, callback_query.from_user.id, callback_data.page, state, is_archive_list=True
    )


@router.callback_query(NoteAction.filter(F.action == "confirm_delete"))
async def confirm_delete_note_handler(callback_query: CallbackQuery, callback_data: NoteAction):
    await callback_query.message.edit_text(
        f"‼️ {hbold('ВЫ УВЕРЕНЫ?')}\n\n"
        f"Вы собираетесь {hbold('НАВСЕГДА')} удалить заметку #{callback_data.note_id}.\n"
        "Это действие необратимо.",
        parse_mode="HTML",
        reply_markup=get_confirm_delete_keyboard(
            note_id=callback_data.note_id,
            page=callback_data.page,
            target_list=callback_data.target_list
        )
    )
    await callback_query.answer()


@router.callback_query(NoteAction.filter(F.action == "delete"))
async def delete_note_confirmed_handler(callback_query: CallbackQuery, callback_data: NoteAction, state: FSMContext):
    deleted = await db.delete_note(callback_data.note_id, callback_query.from_user.id)
    is_archive_list = callback_data.target_list == 'archive'
    if deleted:
        await callback_query.answer("🗑️ Заметка удалена навсегда!")
    else:
        await callback_query.answer("❌ Не удалось удалить заметку.", show_alert=True)
    await _display_notes_list_page(
        callback_query.message, callback_query.from_user.id, callback_data.page, state, is_archive_list
    )


# --- FSM HANDLERS FOR NOTE EDITING ---

@router.callback_query(NoteAction.filter(F.action == "edit"))
async def start_note_edit_handler(callback_query: CallbackQuery, callback_data: NoteAction, state: FSMContext):
    await state.set_state(NoteEditingStates.awaiting_new_text)
    await state.update_data(
        note_id_to_edit=callback_data.note_id,
        page_to_return_to=callback_data.page,
        original_message_id=callback_query.message.message_id
    )
    await callback_query.message.edit_text(
        f"✏️ {hbold('Редактирование заметки #{callback_data.note_id}')}\n\n"
        "Пришлите мне новый текст для этой заметки. "
        "Чтобы отменить, просто отправьте /cancel.",
        parse_mode="HTML",
        reply_markup=None
    )
    await callback_query.answer()


@router.message(NoteEditingStates.awaiting_new_text, Command("cancel"))
async def cancel_note_edit_handler(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    note_id = user_data.get("note_id_to_edit")
    original_message_id = user_data.get("original_message_id")
    await state.clear()
    await message.answer("🚫 Редактирование отменено.")
    try:
        # Для возврата к просмотру нам снова нужен user_timezone
        user_profile = await db.get_user_profile(message.from_user.id)
        user_timezone = user_profile.get('timezone', 'UTC') if user_profile else 'UTC'
        note = await db.get_note_by_id(note_id, message.from_user.id)
        if not note: raise ValueError("Note not found or access denied")

        note_taken_at_local = format_datetime_for_user(note.get('note_taken_at') or note['created_at'], user_timezone)
        status_icon = "🗄️" if note['is_archived'] else "📌"
        text = f"{status_icon} {hbold(f'Заметка #{note['note_id']}')}\n\n"
        text += f"Созд./Записана: {hitalic(note_taken_at_local)}\n"
        text += f"\n{hbold('Текст заметки:')}\n{hcode(note['corrected_text'])}\n"

        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=original_message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=get_note_view_actions_keyboard(
                note['note_id'], user_data.get("page_to_return_to", 1), note['is_archived']
            )
        )
    except Exception as e:
        logger.warning(f"Не удалось вернуть пользователя к просмотру заметки после отмены редактирования: {e}")
        await message.answer("Чем еще могу помочь?", reply_markup=get_main_menu_keyboard())


@router.message(NoteEditingStates.awaiting_new_text, F.text)
async def process_note_edit_handler(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    note_id = user_data.get("note_id_to_edit")
    page_to_return_to = user_data.get("page_to_return_to", 1)
    original_message_id = user_data.get("original_message_id")
    new_text = message.text
    if len(new_text) < 3:
        await message.reply("Текст заметки слишком короткий. Введите более содержательный текст или отмените /cancel.")
        return
    success = await db.update_note_text(note_id, new_text, message.from_user.id)
    await state.clear()
    if success:
        await message.reply(f"✅ Текст заметки #{note_id} успешно обновлен.")
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=original_message_id)
        except Exception:
            pass
        await _display_notes_list_page(message, message.from_user.id, page_to_return_to, state, is_archive_list=False)
    else:
        await message.reply("❌ Произошла ошибка при обновлении заметки. Попробуйте еще раз.")
        await message.answer("Чем еще могу помочь?", reply_markup=get_main_menu_keyboard())