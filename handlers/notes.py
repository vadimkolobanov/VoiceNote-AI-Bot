import logging
from datetime import datetime, timedelta, time
from dateutil.rrule import rrulestr
import pytz

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
    get_confirm_delete_keyboard,
    get_category_selection_keyboard,
)
import database_setup as db
from services.scheduler import add_reminder_to_scheduler, remove_reminder_from_scheduler
from services.tz_utils import format_datetime_for_user
from states import NoteNavigationStates, NoteEditingStates

logger = logging.getLogger(__name__)
router = Router()


def humanize_rrule(rule_str: str) -> str:
    """Превращает RRULE в человекочитаемую строку."""
    try:
        if "FREQ=DAILY" in rule_str: return "Каждый день"
        if "FREQ=WEEKLY" in rule_str: return "Каждую неделю"
        if "FREQ=MONTHLY" in rule_str: return "Каждый месяц"
        if "FREQ=YEARLY" in rule_str: return "Каждый год"
        return "Повторяющаяся"
    except Exception:
        return "Повторяющаяся"


async def return_to_main_menu(message: types.Message):
    """Отправляет сообщение с главным меню."""
    user_profile = await db.get_user_profile(message.from_user.id)
    is_vip = user_profile.get('is_vip', False) if user_profile else False
    await message.answer("Чем еще могу помочь?", reply_markup=get_main_menu_keyboard(is_vip=is_vip))


@router.callback_query(NoteAction.filter(F.action == "undo_create"))
async def undo_note_creation_handler(callback: CallbackQuery, callback_data: NoteAction):
    """Обрабатывает отмену только что созданной заметки."""
    note_id = callback_data.note_id
    user_id = callback.from_user.id

    deleted = await db.delete_note(note_id, user_id)

    if deleted:
        remove_reminder_from_scheduler(note_id)
        await db.log_user_action(user_id, 'undo_create_note', metadata={'note_id': note_id})
        await callback.message.edit_text(f"🚫 Создание заметки #{hbold(str(note_id))} было отменено.")
        await callback.answer("Создание отменено")
    else:
        await callback.message.edit_text(f"☑️ Заметка #{hbold(str(note_id))} уже была удалена или не найдена.")
        await callback.answer("Действие уже неактуально", show_alert=True)


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
        telegram_id=telegram_id, page=page_num, per_page=NOTES_PER_PAGE, archived=is_archive_list
    )
    total_pages = (total_notes_count + NOTES_PER_PAGE - 1) // NOTES_PER_PAGE
    if total_pages == 0: total_pages = 1
    if page_num > total_pages and total_pages > 0:
        page_num = total_pages
        await state.update_data(current_notes_page=page_num)
        notes_on_page, total_notes_count = await db.get_paginated_notes_for_user(
            telegram_id=telegram_id, page=page_num, per_page=NOTES_PER_PAGE, archived=is_archive_list
        )

    if not notes_on_page and page_num == 1:
        empty_text = "В архиве пусто." if is_archive_list else "У вас пока нет активных задач. Создайте новую!"
        text_content = empty_text
    else:
        title = "🗄️ Ваш архив" if is_archive_list else "📝 Ваши активные задачи"
        text_content = f"{hbold(f'{title} (Стр. {page_num}/{total_pages}):')}"

    keyboard = get_notes_list_display_keyboard(notes_on_page, page_num, total_pages, is_archive_list)

    try:
        await target_message.edit_text(text_content, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.info(f"Не удалось отредактировать сообщение для списка заметок, отправляю новое: {e}")
        await target_message.answer(text_content, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(PageNavigation.filter(F.target == "notes"))
async def notes_list_paginated_handler(callback_query: types.CallbackQuery, callback_data: PageNavigation,
                                       state: FSMContext):
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
    await _display_notes_list_page(message, message.from_user.id, 1, state, is_archive_list=False)


@router.callback_query(F.data == "main_menu_from_notes")
async def back_to_main_menu_from_notes_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_profile = await db.get_user_profile(callback_query.from_user.id)
    is_vip = user_profile.get('is_vip', False) if user_profile else False
    try:
        await callback_query.message.edit_text("🏠 Вы в главном меню.", reply_markup=get_main_menu_keyboard(is_vip=is_vip))
    except Exception:
        await callback_query.message.answer("🏠 Вы в главном меню.", reply_markup=get_main_menu_keyboard(is_vip=is_vip))
    await callback_query.answer()


@router.callback_query(NoteAction.filter(F.action == "view"))
async def view_note_detail_handler(callback_query: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    note_id = callback_data.note_id
    current_page = callback_data.page
    target_list = callback_data.target_list
    is_archived_view = target_list == 'archive'
    telegram_id = callback_query.from_user.id

    await state.set_state(NoteNavigationStates.browsing_notes)
    await state.update_data(current_notes_page=current_page, is_archive_view=is_archived_view)

    user_profile = await db.get_user_profile(telegram_id)
    user_timezone = user_profile.get('timezone', 'UTC') if user_profile else 'UTC'
    note = await db.get_note_by_id(note_id, telegram_id)
    if not note:
        await callback_query.answer("Заметка не найдена или удалена.", show_alert=True)
        await _display_notes_list_page(callback_query.message, telegram_id, current_page, state, is_archived_view)
        return

    updated_at_local = format_datetime_for_user(note.get('updated_at'), user_timezone)
    due_date_local = format_datetime_for_user(note.get('due_date'), user_timezone)
    recurrence_rule = note.get('recurrence_rule')
    is_vip = user_profile.get('is_vip', False)

    category = note.get('category', 'Общее')
    is_completed = note.get('is_completed', False)

    status_icon = "✅" if is_completed else ("🗄️" if note['is_archived'] else "📌")
    status_text = "Выполнена" if is_completed else ("В архиве" if note['is_archived'] else "Активна")

    text = f"{status_icon} {hbold(f'Заметка #{note['note_id']}')}\n\n"
    if recurrence_rule and is_vip:
        text += f"⭐ 🔁 Повторение: {hitalic(humanize_rrule(recurrence_rule))}\n"
    text += f"Статус: {hitalic(status_text)}\n"
    text += f"🗂️ Категория: {hitalic(category)}\n"
    if note.get('updated_at') and note['updated_at'].strftime('%Y%m%d%H%M') != note['created_at'].strftime(
            '%Y%m%d%H%M'):
        text += f"Обновлена: {hitalic(updated_at_local)}\n"
    if due_date_local:
        text += f"Срок до: {hitalic(due_date_local)}\n"
    text += f"\n{hbold('Текст заметки:')}\n{hcode(note['corrected_text'])}\n"

    note['is_vip'] = is_vip

    try:
        await callback_query.message.edit_text(
            text, parse_mode="HTML",
            reply_markup=get_note_view_actions_keyboard(note, current_page)
        )
    except Exception as e:
        logger.warning(f"Could not edit note view, sending new message: {e}")
        await callback_query.message.answer(
            text, parse_mode="HTML",
            reply_markup=get_note_view_actions_keyboard(note, current_page)
        )

@router.callback_query(NoteAction.filter(F.action == "listen_audio"))
async def listen_audio_handler(callback_query: CallbackQuery, callback_data: NoteAction):
    note = await db.get_note_by_id(callback_data.note_id, callback_query.from_user.id)
    if note and note.get('original_audio_telegram_file_id'):
        audio_file_id = note['original_audio_telegram_file_id']
        await callback_query.answer("▶️ Отправляю аудио...")
        try:
            await callback_query.message.answer_voice(voice=audio_file_id)
        except Exception as e:
            logger.error(f"Не удалось отправить аудио {audio_file_id}: {e}")
            await callback_query.answer("❌ Не удалось отправить аудиофайл.", show_alert=True)
    else:
        await callback_query.answer("Аудиофайл для этой заметки не найден.", show_alert=True)


@router.callback_query(NoteAction.filter(F.action == "change_category"))
async def change_category_handler(callback_query: CallbackQuery, callback_data: NoteAction):
    await callback_query.message.edit_text(
        "🗂️ Выберите новую категорию для заметки:",
        reply_markup=get_category_selection_keyboard(
            note_id=callback_data.note_id,
            page=callback_data.page,
            target_list=callback_data.target_list
        )
    )
    await callback_query.answer()


@router.callback_query(NoteAction.filter(F.action == "set_category"))
async def set_category_handler(callback_query: CallbackQuery, callback_data: NoteAction, state: FSMContext):
    new_category = callback_data.category
    success = await db.update_note_category(callback_data.note_id, new_category, callback_query.from_user.id)

    if success:
        await callback_query.answer(f"Категория изменена на '{new_category}'")
    else:
        await callback_query.answer("❌ Ошибка при смене категории.", show_alert=True)

    await view_note_detail_handler(callback_query, callback_data, state)


@router.callback_query(NoteAction.filter(F.action == "stop_recurrence"))
async def stop_recurrence_handler(callback_query: CallbackQuery, callback_data: NoteAction, state: FSMContext):
    success = await db.set_note_recurrence_rule(callback_data.note_id, callback_query.from_user.id, rule=None)
    if success:
        await callback_query.answer("✅ Повторение для этой заметки отключено.")
    else:
        await callback_query.answer("❌ Ошибка при отключении повторения.", show_alert=True)
    await view_note_detail_handler(callback_query, callback_data, state)


@router.callback_query(NoteAction.filter(F.action == "archive"))
async def archive_note_handler(callback_query: CallbackQuery, callback_data: NoteAction, state: FSMContext):
    success = await db.set_note_archived_status(callback_data.note_id, callback_query.from_user.id, archived=True)
    if success:
        remove_reminder_from_scheduler(callback_data.note_id)
        await callback_query.answer("🗄️ Заметка перемещена в архив")
    else:
        await callback_query.answer("❌ Ошибка при архивации", show_alert=True)
    await _display_notes_list_page(
        callback_query.message, callback_query.from_user.id, callback_data.page, state, is_archive_list=False
    )


@router.callback_query(NoteAction.filter(F.action == "unarchive"))
async def unarchive_note_handler(callback_query: CallbackQuery, callback_data: NoteAction, state: FSMContext):
    bot = callback_query.bot
    telegram_id = callback_query.from_user.id
    user_profile = await db.get_user_profile(telegram_id)
    is_vip = user_profile.get('is_vip', False) if user_profile else False
    if not is_vip:
        active_notes_count = await db.count_active_notes_for_user(telegram_id)
        if active_notes_count >= MAX_NOTES_MVP:
            await callback_query.answer(f"Нельзя восстановить. Лимит в {MAX_NOTES_MVP} активных заметок.",
                                        show_alert=True)
            return

    success = await db.set_note_archived_status(callback_data.note_id, telegram_id, archived=False)
    if success:
        note = await db.get_note_by_id(callback_data.note_id, telegram_id)
        if note and note.get('due_date'):
            note.update({
                'default_reminder_time': user_profile.get('default_reminder_time'),
                'timezone': user_profile.get('timezone'),
                'pre_reminder_minutes': user_profile.get('pre_reminder_minutes'),
                'is_vip': is_vip
            })
            add_reminder_to_scheduler(bot, note)
        await callback_query.answer("↩️ Заметка восстановлена из архива")
    else:
        await callback_query.answer("❌ Ошибка при восстановлении", show_alert=True)
    await _display_notes_list_page(callback_query.message, telegram_id, callback_data.page, state, is_archive_list=True)


@router.callback_query(NoteAction.filter(F.action == "confirm_delete"))
async def confirm_delete_note_handler(callback_query: CallbackQuery, callback_data: NoteAction):
    note = await db.get_note_by_id(callback_data.note_id, callback_query.from_user.id)
    is_recurring = note and note.get('recurrence_rule')

    warning_text = (f"Вы собираетесь {hbold('НАВСЕГДА')} удалить заметку #{callback_data.note_id}.\n"
                    "Это действие необратимо.")
    if is_recurring:
        warning_text = (f"Вы собираетесь {hbold('НАВСЕГДА')} удалить повторяющуюся заметку #{callback_data.note_id} "
                        f"и {hbold('ВСЕ')} её будущие повторения.\nЭто действие необратимо.")

    await callback_query.message.edit_text(
        f"‼️ {hbold('ВЫ УВЕРЕНЫ?')}\n\n{warning_text}",
        parse_mode="HTML",
        reply_markup=get_confirm_delete_keyboard(note_id=callback_data.note_id, page=callback_data.page,
                                                 target_list=callback_data.target_list)
    )
    await callback_query.answer()


@router.callback_query(NoteAction.filter(F.action == "delete"))
async def delete_note_confirmed_handler(callback_query: CallbackQuery, callback_data: NoteAction, state: FSMContext):
    deleted = await db.delete_note(callback_data.note_id, callback_query.from_user.id)
    is_archive_list = callback_data.target_list == 'archive'
    if deleted:
        remove_reminder_from_scheduler(callback_data.note_id)
        await callback_query.answer("🗑️ Заметка удалена навсегда!")
    else:
        await callback_query.answer("❌ Не удалось удалить заметку.", show_alert=True)
    await _display_notes_list_page(callback_query.message, callback_query.from_user.id, callback_data.page, state,
                                   is_archive_list)


@router.callback_query(NoteAction.filter(F.action == "edit"))
async def start_note_edit_handler(callback_query: CallbackQuery, callback_data: NoteAction, state: FSMContext):
    await state.set_state(NoteEditingStates.awaiting_new_text)
    await state.update_data(note_id_to_edit=callback_data.note_id, page_to_return_to=callback_data.page,
                            original_message_id=callback_query.message.message_id)
    await callback_query.message.edit_text(
        f"✏️ {hbold('Редактирование заметки')}\n\n"
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
    await state.clear()
    await message.answer("🚫 Редактирование отменено.")

    fake_callback_query = types.CallbackQuery(
        id=str(message.message_id),
        from_user=message.from_user,
        chat_instance="fake",
        message=message,
        data=NoteAction(
            action="view",
            note_id=note_id,
            page=user_data.get("page_to_return_to", 1)
        ).pack()
    )
    fake_callback_data = NoteAction(action="view", note_id=note_id, page=user_data.get("page_to_return_to", 1))
    await view_note_detail_handler(fake_callback_query, fake_callback_data, state)


@router.message(NoteEditingStates.awaiting_new_text, F.text)
async def process_note_edit_handler(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    note_id = user_data.get("note_id_to_edit")
    page_to_return_to = user_data.get("page_to_return_to", 1)
    new_text = message.text
    if len(new_text) < 3:
        await message.reply("Текст заметки слишком короткий. Введите более содержательный текст или отмените /cancel.")
        return
    success = await db.update_note_text(note_id, new_text, message.from_user.id)
    await state.clear()
    if success:
        await message.reply(f"✅ Текст заметки #{note_id} успешно обновлен.")
        await _display_notes_list_page(message, message.from_user.id, page_to_return_to, state, is_archive_list=False)
    else:
        await message.reply("❌ Произошла ошибка при обновлении заметки. Попробуйте еще раз.")
        await return_to_main_menu(message)


@router.callback_query(NoteAction.filter(F.action == "complete"))
async def complete_note_handler(callback: CallbackQuery, callback_data: NoteAction, state: FSMContext):
    note_id = callback_data.note_id
    telegram_id = callback.from_user.id

    note = await db.get_note_by_id(note_id, telegram_id)
    user_profile = await db.get_user_profile(telegram_id)
    is_recurring = note and note.get('recurrence_rule') and user_profile.get('is_vip')

    if is_recurring:
        await callback.answer("✅ Отлично! Это событие отмечено, ждем следующего.", show_alert=False)
        from services.scheduler import reschedule_recurring_note
        await reschedule_recurring_note(callback.bot, note)
        try:
            await callback.message.edit_text(
                f"{callback.message.text}\n\n{hbold('Статус: ✅ Пропущено, ждем следующего повторения')}",
                parse_mode="HTML", reply_markup=None
            )
        except Exception:
            pass
        return

    success = await db.set_note_completed_status(note_id, telegram_id, completed=True)
    if success:
        remove_reminder_from_scheduler(note_id)
        await callback.answer("✅ Отлично! Задача выполнена и перенесена в архив.", show_alert=False)

        try:
            await callback.message.edit_text(
                f"{callback.message.text}\n\n{hbold('Статус: ✅ Выполнено')}",
                parse_mode="HTML", reply_markup=None
            )
        except Exception:
            pass
        await _display_notes_list_page(callback.message, telegram_id, page_num=1, state=state, is_archive_list=False)
    else:
        await callback.answer("❌ Не удалось отметить задачу как выполненную.", show_alert=True)


@router.callback_query(NoteAction.filter(F.action == "snooze"))
async def snooze_reminder_handler(callback: CallbackQuery, callback_data: NoteAction):
    telegram_id = callback.from_user.id

    user_profile = await db.get_user_profile(telegram_id)
    if not user_profile.get('is_vip', False):
        await callback.answer("⭐ Отложенные напоминания доступны только для VIP-пользователей.", show_alert=True)
        return

    note_id = callback_data.note_id
    snooze_minutes = callback_data.snooze_minutes

    note = await db.get_note_by_id(note_id, telegram_id)
    if not note or not note.get('due_date'):
        await callback.answer("❌ Не удалось отложить: заметка или дата не найдены.", show_alert=True)
        return

    new_due_date = datetime.now(datetime.now().astimezone().tzinfo) + timedelta(minutes=snooze_minutes)

    await db.update_note_due_date(note_id, new_due_date)

    note_data_for_scheduler = note.copy()
    note_data_for_scheduler.update({
        'due_date': new_due_date,
        'default_reminder_time': user_profile.get('default_reminder_time'),
        'timezone': user_profile.get('timezone'),
        'pre_reminder_minutes': user_profile.get('pre_reminder_minutes'),
        'is_vip': user_profile.get('is_vip', False)
    })

    add_reminder_to_scheduler(callback.bot, note_data_for_scheduler)

    if snooze_minutes < 60:
        snooze_text = f"{snooze_minutes} мин."
    else:
        snooze_text = f"{snooze_minutes // 60} ч."

    await callback.answer(f"👌 Понял! Напомню через {snooze_text}", show_alert=False)

    try:
        await callback.message.edit_text(
            f"{callback.message.text}\n\n{hbold(f'Статус: ⏰ Отложено до {new_due_date.astimezone().strftime('%H:%M')}')}",
            parse_mode="HTML", reply_markup=None
        )
    except Exception:
        pass

    await return_to_main_menu(callback.message)