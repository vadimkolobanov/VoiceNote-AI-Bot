# src/bot/modules/notes/handlers/actions.py
import logging
from datetime import datetime, timedelta
import pytz

from aiogram import Bot, F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hcode, hitalic

from src.database import note_repo, user_repo
from src.core.config import MAX_NOTES_MVP
from src.services.scheduler import add_reminder_to_scheduler, remove_reminder_from_scheduler, reschedule_recurring_note
from src.bot.common_utils.callbacks import NoteAction
from ..keyboards import get_confirm_delete_keyboard
from .list_view import display_notes_list_page, view_note_detail_handler

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(NoteAction.filter(F.action == "undo_create"))
async def undo_note_creation_handler(callback: types.CallbackQuery, callback_data: NoteAction):
    """Отменяет только что созданную заметку."""
    note_id = callback_data.note_id
    deleted = await note_repo.delete_note(note_id, callback.from_user.id)
    if deleted:
        remove_reminder_from_scheduler(note_id)
        await user_repo.log_user_action(callback.from_user.id, 'undo_create_note', metadata={'note_id': note_id})
        await callback.message.edit_text(f"🚫 Создание заметки #{hbold(str(note_id))} отменено.")
        await callback.answer("Создание отменено")
    else:
        await callback.message.edit_text(f"☑️ Заметка #{hbold(str(note_id))} уже неактуальна.")
        await callback.answer("Действие уже неактуально", show_alert=True)


@router.callback_query(NoteAction.filter(F.action == "complete"))
async def complete_note_handler(callback: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    """Отмечает заметку как выполненную."""
    note_id = callback_data.note_id
    note = await note_repo.get_note_by_id(note_id, callback.from_user.id)
    if not note:
        await callback.answer("❌ Заметка не найдена.", show_alert=True)
        return

    user_profile = await user_repo.get_user_profile(callback.from_user.id)
    is_recurring = note.get('recurrence_rule') and user_profile.get('is_vip')

    # Логика для повторяющихся задач
    if is_recurring:
        await callback.answer("✅ Отлично! Это событие отмечено, ждем следующего.", show_alert=False)
        await reschedule_recurring_note(callback.bot, note)
        try:  # Пытаемся обновить сообщение, но не падаем, если не вышло
            await callback.message.edit_text(
                f"{callback.message.text}\n\n{hbold('Статус: ✅ Пропущено, ждем следующего повторения')}",
                reply_markup=None
            )
        except Exception:
            pass
        return

    # Логика для обычных задач
    success = await note_repo.set_note_completed_status(note_id, True)
    if success:
        remove_reminder_from_scheduler(note_id)
        await callback.answer("✅ Отлично! Задача выполнена и перенесена в архив.", show_alert=False)
        await display_notes_list_page(callback.message, callback.from_user.id, 1, state, is_archive_list=False)
    else:
        await callback.answer("❌ Не удалось отметить задачу как выполненную.", show_alert=True)


@router.callback_query(NoteAction.filter(F.action == "archive"))
async def archive_note_handler(callback: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    """Перемещает заметку в архив."""
    success = await note_repo.set_note_archived_status(callback_data.note_id, True)
    if success:
        remove_reminder_from_scheduler(callback_data.note_id)
        await callback.answer("🗄️ Заметка перемещена в архив")
    else:
        await callback.answer("❌ Ошибка при архивации", show_alert=True)
    await display_notes_list_page(callback.message, callback.from_user.id, callback_data.page, state,
                                  is_archive_list=False)


@router.callback_query(NoteAction.filter(F.action == "unarchive"))
async def unarchive_note_handler(callback: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    """Восстанавливает заметку из архива."""
    user_profile = await user_repo.get_user_profile(callback.from_user.id)
    if not user_profile.get('is_vip'):
        active_notes_count = await note_repo.count_active_notes_for_user(callback.from_user.id)
        if active_notes_count >= MAX_NOTES_MVP:
            await callback.answer(f"Нельзя восстановить. Лимит в {MAX_NOTES_MVP} активных заметок.", show_alert=True)
            return

    success = await note_repo.set_note_archived_status(callback_data.note_id, False)
    if success:
        note = await note_repo.get_note_by_id(callback_data.note_id, callback.from_user.id)
        if note and note.get('due_date'):
            note_with_profile = {**note, **user_profile}
            add_reminder_to_scheduler(callback.bot, note_with_profile)
        await callback.answer("↩️ Заметка восстановлена из архива")
    else:
        await callback.answer("❌ Ошибка при восстановлении", show_alert=True)
    await display_notes_list_page(callback.message, callback.from_user.id, callback_data.page, state,
                                  is_archive_list=True)


@router.callback_query(NoteAction.filter(F.action == "confirm_delete"))
async def confirm_delete_note_handler(callback: types.CallbackQuery, callback_data: NoteAction):
    """Показывает экран подтверждения удаления."""
    note = await note_repo.get_note_by_id(callback_data.note_id, callback.from_user.id)
    warning_text = f"Вы собираетесь {hbold('НАВСЕГДА')} удалить заметку #{callback_data.note_id}."
    if note and note.get('recurrence_rule'):
        warning_text += f" и {hbold('ВСЕ')} её будущие повторения."

    await callback.message.edit_text(
        f"‼️ {hbold('ВЫ УВЕРЕНЫ?')}\n\n{warning_text}\nЭто действие необратимо.",
        reply_markup=get_confirm_delete_keyboard(
            note_id=callback_data.note_id, page=callback_data.page, target_list=callback_data.target_list
        )
    )
    await callback.answer()


@router.callback_query(NoteAction.filter(F.action == "delete"))
async def delete_note_confirmed_handler(callback: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    """Окончательно удаляет заметку."""
    deleted = await note_repo.delete_note(callback_data.note_id, callback.from_user.id)
    if deleted:
        remove_reminder_from_scheduler(callback_data.note_id)
        await callback.answer("🗑️ Заметка удалена навсегда!")
    else:
        await callback.answer("❌ Не удалось удалить заметку.", show_alert=True)
    await display_notes_list_page(callback.message, callback.from_user.id, callback_data.page, state,
                                  callback_data.target_list == 'archive')


@router.callback_query(NoteAction.filter(F.action == "snooze"))
async def snooze_reminder_handler(callback: types.CallbackQuery, callback_data: NoteAction):
    """Откладывает напоминание."""
    user_profile = await user_repo.get_user_profile(callback.from_user.id)
    if not user_profile.get('is_vip', False):
        await callback.answer("⭐ Отложенные напоминания доступны только для VIP-пользователей.", show_alert=True)
        return

    note = await note_repo.get_note_by_id(callback_data.note_id, callback.from_user.id)
    if not note or not note.get('due_date'):
        await callback.answer("❌ Не удалось отложить: заметка или дата не найдены.", show_alert=True)
        return

    new_due_date = datetime.now(pytz.utc) + timedelta(minutes=callback_data.snooze_minutes)
    await note_repo.update_note_due_date(callback_data.note_id, new_due_date)

    note_with_profile = {**note, **user_profile, 'due_date': new_due_date}
    add_reminder_to_scheduler(callback.bot, note_with_profile)

    await callback.answer(f"👌 Понял! Напомню через {callback_data.snooze_minutes // 60} ч.", show_alert=False)
    try:
        await callback.message.edit_text(f"{callback.message.text}\n\n{hbold('Статус: ⏰ Отложено')}", reply_markup=None)
    except Exception:
        pass


@router.callback_query(NoteAction.filter(F.action == "share"))
async def generate_share_link_handler(callback: types.CallbackQuery, callback_data: NoteAction, bot: Bot):
    """Генерирует диплинк для шаринга заметки."""
    token = await note_repo.create_share_token(callback_data.note_id, callback.from_user.id)
    if not token:
        await callback.answer("❌ Не удалось создать ссылку. Попробуйте позже.", show_alert=True)
        return

    bot_info = await bot.get_me()
    share_link = f"https://t.me/{bot_info.username}?start=share_{token}"

    text = (
        f"🤝 {hbold('Ссылка для приглашения создана!')}\n\n"
        "Отправьте эту ссылку человеку, с которым хотите поделиться заметкой.\n\n"
        f"🔗 {hbold('Ваша ссылка:')}\n{hcode(share_link)}\n\n"
        f"{hitalic('Ссылка действительна 48 часов и используется один раз.')}"
    )
    back_button = types.InlineKeyboardButton(
        text="⬅️ Назад к заметке",
        callback_data=NoteAction(action="view", note_id=callback_data.note_id, page=callback_data.page).pack()
    )
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[back_button]]),
                                     disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(NoteAction.filter(F.action == "listen_audio"))
async def listen_audio_handler(callback: types.CallbackQuery, callback_data: NoteAction):
    """Отправляет оригинальный аудиофайл заметки."""
    note = await note_repo.get_note_by_id(callback_data.note_id, callback.from_user.id)
    if note and note.get('original_audio_telegram_file_id'):
        await callback.answer("▶️ Отправляю аудио...")
        await callback.message.answer_voice(voice=note['original_audio_telegram_file_id'])
    else:
        await callback.answer("Аудиофайл для этой заметки не найден.", show_alert=True)