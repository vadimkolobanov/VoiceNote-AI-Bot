# src/bot/modules/notes/handlers/actions.py
import logging
from datetime import timedelta
from dateutil.rrule import rrulestr, DAILY, WEEKLY, MONTHLY

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hitalic, hcode

from .....database import note_repo, user_repo
from .....services.scheduler import add_reminder_to_scheduler, remove_reminder_from_scheduler, reschedule_recurring_note
from .....services.gamification_service import XP_REWARDS, AchievCode, check_and_grant_achievements
from ....common_utils.callbacks import NoteAction
from ..keyboards import get_category_selection_keyboard
from .list_view import display_notes_list_page, view_note_detail_handler

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(NoteAction.filter(F.action == "undo_create"))
async def undo_note_creation_handler(callback: types.CallbackQuery, callback_data: NoteAction):
    """Отменяет создание заметки, удаляя ее из БД."""
    note_id = callback_data.note_id
    note = await note_repo.get_note_by_id(note_id, callback.from_user.id)
    if note:
        remove_reminder_from_scheduler(note_id)
        await note_repo.delete_note(note_id, callback.from_user.id)
        await callback.message.edit_text("✅ Создание заметки отменено.")
    else:
        await callback.message.edit_text("✅ Заметка уже была отменена или удалена.")

    await callback.answer()


@router.callback_query(NoteAction.filter(F.action == "snooze"))
async def snooze_note_handler(callback: types.CallbackQuery, callback_data: NoteAction):
    """Откладывает напоминание."""
    note_id = callback_data.note_id
    minutes = callback_data.snooze_minutes
    user_id = callback.from_user.id

    note = await note_repo.get_note_by_id(note_id, user_id)
    if not note or not note.get('due_date'):
        await callback.answer("❌ Не удалось отложить: заметка не найдена.", show_alert=True)
        return

    new_due_date = note['due_date'] + timedelta(minutes=minutes)
    await note_repo.update_note_due_date(note_id, new_due_date)

    user_profile = await user_repo.get_user_profile(user_id)
    note['due_date'] = new_due_date  # Обновляем локальный объект для планировщика
    add_reminder_to_scheduler(callback.bot, {**note, **user_profile})

    # Логика ачивки
    new_snooze_count = await note_repo.increment_snooze_count(note_id)
    await user_repo.add_xp_and_check_level_up(callback.bot, user_id, XP_REWARDS['snooze_note'])

    if new_snooze_count >= 3:
        # Проверяем, есть ли уже ачивка, чтобы не спамить
        user_achievements = await user_repo.get_user_achievements_codes(user_id)
        if AchievCode.PROCRASTINATOR.value not in user_achievements:
            await user_repo.grant_achievement(callback.bot, user_id, AchievCode.PROCRASTINATOR.value)

    await callback.answer(f"✅ Напоминание отложено на {minutes} минут.", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.callback_query(NoteAction.filter(F.action == "complete"))
async def complete_note_handler(callback: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    """
    Обрабатывает выполнение заметки.
    Для повторяющихся задач - просто подтверждает. Для обычных - архивирует.
    """
    note_id = callback_data.note_id
    user_id = callback.from_user.id

    note = await note_repo.get_note_by_id(note_id, user_id)
    if not note:
        await callback.answer("❌ Заметка не найдена.", show_alert=True)
        return

    # Начисляем опыт и проверяем ачивки в любом случае
    await user_repo.add_xp_and_check_level_up(callback.bot, user_id, XP_REWARDS['note_completed'])
    await check_and_grant_achievements(callback.bot, user_id)

    if note.get('recurrence_rule'):
        # Это повторяющаяся задача. Не архивируем!
        # Перепланируем на следующее повторение.
        await reschedule_recurring_note(callback.bot, note)

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            # Если сообщение старое, может возникнуть ошибка, это нормально
            pass

        await callback.answer("👍 Выполнено! Следующее напоминание уже запланировано.", show_alert=True)

    else:
        # Это обычная задача. Архивируем ее.
        success = await note_repo.set_note_completed_status(note_id, True)
        remove_reminder_from_scheduler(note_id)

        if success:
            await callback.answer("✅ Отлично! Заметка выполнена и перенесена в архив.", show_alert=True)
            # Обновляем список заметок, чтобы выполненная исчезла
            await display_notes_list_page(
                message=callback.message,
                user_id=user_id,
                page=callback_data.page,
                archived=False,
                is_callback=True
            )
        else:
            await callback.answer("❌ Ошибка при архивации.", show_alert=True)


@router.callback_query(NoteAction.filter(F.action == "archive"))
async def archive_note_handler(callback: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    """Архивирует заметку."""
    note_id = callback_data.note_id
    await note_repo.set_note_archived_status(note_id, True)
    remove_reminder_from_scheduler(note_id)
    await callback.answer("🗄️ Заметка перенесена в архив.", show_alert=False)
    await display_notes_list_page(
        message=callback.message,
        user_id=callback.from_user.id,
        page=callback_data.page,
        archived=False,
        is_callback=True
    )


@router.callback_query(NoteAction.filter(F.action == "unarchive"))
async def restore_note_handler(callback: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    """Восстанавливает заметку из архива."""
    note_id = callback_data.note_id

    success = await note_repo.restore_note_from_archive(note_id)
    if not success:
        await callback.answer("❌ Ошибка при восстановлении.", show_alert=True)
        return

    # После восстановления нужно заново добавить напоминание в планировщик, если оно есть
    note = await note_repo.get_note_by_id(note_id, callback.from_user.id)
    if note and note.get('due_date'):
        user_profile = await user_repo.get_user_profile(callback.from_user.id)
        if user_profile:
            add_reminder_to_scheduler(callback.bot, {**note, **user_profile})

    await callback.answer("↩️ Заметка восстановлена.", show_alert=False)
    await display_notes_list_page(
        message=callback.message,
        user_id=callback.from_user.id,
        page=callback_data.page,
        archived=True,
        is_callback=True
    )


@router.callback_query(NoteAction.filter(F.action == "delete"))
async def delete_note_handler(callback: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    """Окончательно удаляет заметку."""
    note_id = callback_data.note_id
    success = await note_repo.delete_note(note_id, callback.from_user.id)
    if success:
        remove_reminder_from_scheduler(note_id)
        await callback.answer("🗑️ Заметка удалена навсегда.", show_alert=True)
        await display_notes_list_page(
            message=callback.message,
            user_id=callback.from_user.id,
            page=callback_data.page,
            archived=True,
            is_callback=True
        )
    else:
        await callback.answer("❌ Ошибка при удалении.", show_alert=True)


@router.callback_query(NoteAction.filter(F.action == "change_category"))
async def change_category_handler(callback: types.CallbackQuery, callback_data: NoteAction):
    """Показывает клавиатуру для смены категории."""
    keyboard = get_category_selection_keyboard(
        note_id=callback_data.note_id,
        page=callback_data.page,
        target_list=callback_data.target_list
    )
    await callback.message.edit_text(f"{callback.message.text}\n\nВыберите новую категорию:", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(NoteAction.filter(F.action == "set_category"))
async def set_category_handler(callback: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    """Устанавливает новую категорию и возвращает к просмотру заметки."""
    note_id = callback_data.note_id
    new_category = callback_data.category
    await note_repo.update_note_category(note_id, new_category)
    await callback.answer(f"✅ Категория изменена на «{new_category}».", show_alert=False)
    await view_note_detail_handler(callback, state, callback_data=callback_data)


@router.callback_query(NoteAction.filter(F.action == "listen_audio"))
async def listen_audio_handler(callback: types.CallbackQuery, callback_data: NoteAction):
    """Отправляет оригинальный аудиофайл заметки."""
    note = await note_repo.get_note_by_id(callback_data.note_id, callback.from_user.id)
    if note and note.get('original_audio_telegram_file_id'):
        await callback.message.answer_voice(
            voice=note['original_audio_telegram_file_id'],
            caption=f"🎧 Оригинал аудио для заметки #{callback_data.note_id}"
        )
        await callback.answer()
    else:
        await callback.answer("Аудиофайл не найден.", show_alert=True)


@router.callback_query(NoteAction.filter(F.action == "share"))
async def share_note_handler(callback: types.CallbackQuery, callback_data: NoteAction):
    """Генерирует ссылку для шаринга заметки."""
    note_id = callback_data.note_id
    user_id = callback.from_user.id
    token = await note_repo.create_share_token(note_id, user_id)

    if not token:
        await callback.answer("❌ Не удалось создать ссылку. Попробуйте позже.", show_alert=True)
        return

    # Награждаем за первое действие шаринга
    await check_and_grant_achievements(callback.bot, user_id)
    await user_repo.add_xp_and_check_level_up(callback.bot, user_id, XP_REWARDS['note_shared'])

    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username
    share_link = f"https://t.me/{bot_username}?start=share_{token}"

    text = (
        f"{callback.message.text}\n\n"
        f"🤝 {hbold('Ссылка для шаринга заметки')}\n\n"
        f"Отправьте эту ссылку человеку, с которым хотите поделиться доступом.\n\n"
        f"🔗 {hbold('Ваша ссылка:')}\n"
        f"{hcode(share_link)}\n\n"
        f"{hitalic('Ссылка действительна 48 часов и может быть использована только один раз.')}"
    )

    back_button = types.InlineKeyboardButton(
        text="⬅️ Назад к заметке",
        callback_data=NoteAction(action="view", note_id=note_id, page=callback_data.page,
                                 target_list=callback_data.target_list).pack()
    )
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[back_button]])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(NoteAction.filter(F.action == "stop_recurrence"))
async def stop_note_recurrence_handler(callback: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    """Делает повторяющуюся задачу разовой."""
    note_id = callback_data.note_id
    user_id = callback.from_user.id

    success = await note_repo.set_note_recurrence_rule(note_id, user_id, rule=None)
    if success:
        await callback.answer("✅ Повторение отключено. Заметка стала разовой.", show_alert=True)
        await view_note_detail_handler(callback, state, callback_data=callback_data)
    else:
        await callback.answer("❌ Не удалось отключить повторение.", show_alert=True)


@router.callback_query(NoteAction.filter(F.action == "set_recur"))
async def set_suggested_recurrence_handler(callback: types.CallbackQuery, callback_data: NoteAction, state: FSMContext):
    """Устанавливает повторение по кнопке из предложения."""
    note_id = callback_data.note_id
    user_id = callback.from_user.id
    freq = callback_data.recur_freq

    note = await note_repo.get_note_by_id(note_id, user_id)
    if not note or not note.get('due_date'):
        await callback.message.edit_text("❌ Не удалось установить повторение: заметка или ее дата не найдены.")
        await callback.answer("Ошибка", show_alert=True)
        return

    freq_map = {"DAILY": "DAILY", "WEEKLY": "WEEKLY", "MONTHLY": "MONTHLY"}
    freq_str = freq_map.get(freq.upper())
    weekday = note['due_date'].strftime('%A')[:2].upper()
    rule_str = f"RRULE:FREQ={freq_str};BYDAY={weekday}" if freq_str == "WEEKLY" else f"RRULE:FREQ={freq_str}"
    success = await note_repo.set_note_recurrence_rule(note_id, user_id, rule=rule_str)

    if success:
        user_profile = await user_repo.get_user_profile(user_id)
        if user_profile:
            note_for_scheduler = {**note, **user_profile, 'recurrence_rule': rule_str}
            add_reminder_to_scheduler(callback.bot, note_for_scheduler)

        await callback.message.edit_text(
            f"✅ Отлично! Заметка «{hitalic(note['summary_text'])}» теперь будет повторяться.",
            reply_markup=None
        )
        await callback.answer("Повторение установлено!")
        await check_and_grant_achievements(callback.bot, user_id)
    else:
        await callback.message.edit_text("❌ Не удалось установить повторение.")
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(NoteAction.filter(F.action == "decline_recur"))
async def decline_suggested_recurrence_handler(callback: types.CallbackQuery):
    """Убирает сообщение с предложением о повторении."""
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Хорошо, я понял.")