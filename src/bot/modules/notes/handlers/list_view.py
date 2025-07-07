# src/bot/modules/notes/handlers/list_view.py
import logging

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hcode, hbold, hitalic

from .....core import config
from .....database import note_repo, user_repo
from .....services.tz_utils import format_datetime_for_user
from ....common_utils.callbacks import NoteAction, PageNavigation
from ....common_utils.states import NoteNavigationStates
from ..keyboards import get_notes_list_display_keyboard, get_note_view_actions_keyboard

logger = logging.getLogger(__name__)
router = Router()


def humanize_rrule(rule_str: str) -> str:
    """Преобразует строку RRULE в человекочитаемый формат."""
    try:
        if "FREQ=DAILY" in rule_str: return "Каждый день"
        if "FREQ=WEEKLY" in rule_str: return "Каждую неделю"
        if "FREQ=MONTHLY" in rule_str: return "Каждый месяц"
        if "FREQ=YEARLY" in rule_str: return "Каждый год"
        return "Повторяющаяся"
    except Exception:
        return "Повторяющаяся"


async def display_notes_list_page(
        target_message: types.Message,
        telegram_id: int,
        page_num: int,
        state: FSMContext,
        is_archive_list: bool
):
    """
    Основная функция для отображения страницы со списком заметок (активных или архивных).
    """
    await state.set_state(NoteNavigationStates.browsing_notes)
    await state.update_data(current_notes_page=page_num, is_archive_view=is_archive_list)

    notes_on_page, total_notes_count = await note_repo.get_paginated_notes_for_user(
        telegram_id=telegram_id, page=page_num, archived=is_archive_list
    )
    total_pages = (total_notes_count + config.NOTES_PER_PAGE - 1) // config.NOTES_PER_PAGE
    if total_pages == 0: total_pages = 1

    # Если мы оказались на несуществующей странице, переходим на последнюю
    if page_num > total_pages > 0:
        page_num = total_pages
        await state.update_data(current_notes_page=page_num)
        notes_on_page, total_notes_count = await note_repo.get_paginated_notes_for_user(
            telegram_id=telegram_id, page=page_num, archived=is_archive_list
        )

    # Формируем текст сообщения
    if not notes_on_page and page_num == 1:
        text_content = "🗄️ В архиве пусто." if is_archive_list else "📝 У вас пока нет активных задач. Создайте новую, отправив мне сообщение!"
    else:
        title = "🗄️ Ваш архив" if is_archive_list else "📝 Ваши активные задачи"
        text_content = f"{hbold(f'{title} (Стр. {page_num}/{total_pages}):')}"

    keyboard = get_notes_list_display_keyboard(notes_on_page, page_num, total_pages, is_archive_list, telegram_id)

    try:
        await target_message.edit_text(text_content, reply_markup=keyboard)
    except (TelegramBadRequest, AttributeError):
        # Если не получилось отредактировать (например, это было /my_notes), отправляем новое
        await target_message.answer(text_content, reply_markup=keyboard)


@router.message(Command("my_notes"))
async def cmd_my_notes(message: types.Message, state: FSMContext):
    """Хендлер для команды /my_notes."""
    await display_notes_list_page(message, message.from_user.id, 1, state, is_archive_list=False)


@router.callback_query(PageNavigation.filter(F.target == "notes"))
async def notes_list_paginated_handler(callback: types.CallbackQuery, callback_data: PageNavigation, state: FSMContext):
    """Хендлер для пагинации по спискам заметок."""
    await display_notes_list_page(
        target_message=callback.message,
        telegram_id=callback.from_user.id,
        page_num=callback_data.page,
        state=state,
        is_archive_list=callback_data.archived
    )
    await callback.answer()


@router.callback_query(NoteAction.filter(F.action == "view"))
async def view_note_detail_handler(
        event: types.Message | types.CallbackQuery,
        state: FSMContext,
        note_id: int | None = None
):
    """
    Отображает детальную информацию о заметке.
    Может быть вызвана как по колбэку, так и напрямую из другого хендлера (например, после шаринга).
    """
    is_callback = isinstance(event, types.CallbackQuery)
    message = event.message if is_callback else event
    user = event.from_user

    if is_callback:
        callback_data = NoteAction.unpack(event.data)
        note_id = callback_data.note_id
        page = callback_data.page
        is_archived_view = callback_data.target_list == 'archive'
    else:
        # При вызове из другого хендлера, возвращаемся на 1-ю страницу активных заметок
        page = 1
        is_archived_view = False

    await state.set_state(NoteNavigationStates.browsing_notes)
    await state.update_data(current_notes_page=page, is_archive_view=is_archived_view)

    user_profile = await user_repo.get_user_profile(user.id)
    user_timezone = user_profile.get('timezone', 'UTC')
    note = await note_repo.get_note_by_id(note_id, user.id)

    if not note:
        if is_callback:
            await event.answer("Заметка не найдена или удалена.", show_alert=True)
        else:
            await message.answer("Заметка не найдена или удалена.")
        # Возвращаем пользователя к списку, из которого он пришел
        await display_notes_list_page(message, user.id, page, state, is_archived_view)
        return

    # --- Сборка текста для карточки заметки ---
    is_completed = note.get('is_completed', False)
    category = note.get('category', 'Общее')
    status_icon = "✅" if is_completed else ("🗄️" if note['is_archived'] else ("🛒" if category == 'Покупки' else "📌"))
    status_text = "Выполнена" if is_completed else ("В архиве" if note['is_archived'] else "Активна")

    summary = note.get('summary_text') or note['corrected_text']

    shared_info_text = ""
    if note.get('owner_id') != user.id:
        owner_profile = await user_repo.get_user_profile(note.get('owner_id'))
        owner_name = owner_profile.get('first_name', f"ID:{note.get('owner_id')}") if owner_profile else 'Неизвестно'
        shared_info_text = f"🤝 {hitalic(f'Заметка доступна вам от {hbold(owner_name)}')}\n"

    text_parts = [
        f"{status_icon} {hbold(f'Заметка #{note_id}')}",
        shared_info_text,
        f"Статус: {hitalic(status_text)}",
        f"🗂️ Категория: {hitalic(category)}"
    ]

    if note.get('recurrence_rule') and user_profile.get('is_vip'):
        text_parts.append(f"⭐ 🔁 Повторение: {hitalic(humanize_rrule(note.get('recurrence_rule')))}")

    if note.get('due_date'):
        due_date_local = format_datetime_for_user(note.get('due_date'), user_timezone)
        text_parts.append(f"Срок до: {hitalic(due_date_local)}")

    text_parts.append(f"\n{hbold('Текст заметки:')}\n{hcode(summary)}")

    # Показываем полный текст, если он отличается от краткого
    if summary.strip() != note['corrected_text'].strip():
        text_parts.append(f"\n{hitalic('Полный текст:')}\n{hcode(note['corrected_text'])}")

    text = "\n".join(filter(None, text_parts))  # Собираем, убирая пустые строки

    # --- Формирование клавиатуры и отправка ---
    note['is_vip'] = user_profile.get('is_vip', False)
    final_keyboard = get_note_view_actions_keyboard(note, page, user.id)

    try:
        if is_callback:
            await message.edit_text(text, reply_markup=final_keyboard)
        else:
            sent_msg = await message.answer(text, reply_markup=final_keyboard)
            # Сохраняем ID сообщения для будущей синхронизации, если это прямой вызов
            await note_repo.store_shared_message_id(note_id, user.id, sent_msg.message_id)
    except TelegramBadRequest:
        logger.warning(f"Не удалось отредактировать сообщение #{message.message_id}, отправляю новое.")
        sent_msg = await message.answer(text, reply_markup=final_keyboard)
        await note_repo.store_shared_message_id(note_id, user.id, sent_msg.message_id)

    if is_callback:
        await event.answer()