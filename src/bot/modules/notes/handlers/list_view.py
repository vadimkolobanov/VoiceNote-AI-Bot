# src/bot/modules/notes/handlers/list_view.py
import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hitalic, hcode
from aiogram.filters import Command, StateFilter

from .....database import note_repo, user_repo
from .....services.llm import search_notes_with_llm
from .....services.tz_utils import format_datetime_for_user
from ....common_utils.callbacks import PageNavigation, NoteAction
from ..keyboards import get_notes_list_display_keyboard, get_note_view_actions_keyboard, get_confirm_delete_keyboard, get_notes_search_results_keyboard
from ....common_utils.states import NotesSearchStates

logger = logging.getLogger(__name__)
router = Router()


async def display_notes_list_page(message: types.Message, user_id: int, page: int = 1, archived: bool = False,
                                  is_callback: bool = False):
    """Отображает пагинированный список заметок (активных или архивных)."""
    notes, total_items = await note_repo.get_paginated_notes_for_user(user_id, page=page, archived=archived)

    from .....core.config import NOTES_PER_PAGE
    per_page = NOTES_PER_PAGE
    total_pages = (total_items + per_page - 1) // per_page
    if total_pages == 0: total_pages = 1

    if archived:
        header = f"🗄️ {hbold('Архив заметок')}"
        no_notes_text = "В вашем архиве пока пусто."
    else:
        header = f"📝 {hbold('Активные заметки')}"
        no_notes_text = "У вас пока нет активных заметок. Просто отправьте мне что-нибудь!"

    text = f"{header} (Стр. {page}/{total_pages}, Всего: {total_items})"
    if not notes:
        text = f"{header}\n\n{no_notes_text}"

    keyboard = get_notes_list_display_keyboard(notes, page, total_pages, archived, user_id)

    if is_callback:
        try:
            await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            await message.delete()
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(PageNavigation.filter(F.target == "notes"))
async def notes_list_page_handler(callback: types.CallbackQuery, callback_data: PageNavigation):
    """Обрабатывает навигацию по страницам списка заметок."""
    await display_notes_list_page(
        message=callback.message,
        user_id=callback.from_user.id,
        page=callback_data.page,
        archived=callback_data.archived,
        is_callback=True
    )
    await callback.answer()


@router.callback_query(NoteAction.filter(F.action == "view"))
async def view_note_detail_handler(
        event: types.Message | types.CallbackQuery,
        state: FSMContext,
        note_id: int | None = None,
        callback_data: NoteAction | None = None
):
    """Показывает детальную информацию о заметке."""
    await state.clear()

    user_id = event.from_user.id
    message = event if isinstance(event, types.Message) else event.message

    if callback_data:
        note_id = callback_data.note_id
        page = callback_data.page
    else:
        page = 1

    note = await note_repo.get_note_by_id(note_id, user_id)

    if not note:
        await message.answer("❌ Заметка не найдена или у вас нет к ней доступа.")
        if isinstance(event, types.CallbackQuery):
            await event.answer("Заметка не найдена.", show_alert=True)
        return

    owner_profile = await user_repo.get_user_profile(note['owner_id'])
    owner_name = owner_profile.get('first_name', 'Неизвестно') if owner_profile else 'Неизвестно'
    is_owner = user_id == note['owner_id']

    owner_info = ""
    if not is_owner:
        owner_info = f"Владелец: {hitalic(owner_name)}\n"

    status = "Выполнена" if note.get('is_completed') else "В архиве" if note.get('is_archived') else "Активна"
    category = note.get('category', 'Общее')

    note_date = format_datetime_for_user(note['note_taken_at'],
                                         owner_profile.get('timezone') if owner_profile else 'UTC')
    due_date = format_datetime_for_user(note['due_date'], owner_profile.get('timezone') if owner_profile else 'UTC')

    text_parts = [
        f"🗒️ {hbold('Заметка')} #{note['note_id']}",
        f"{hcode(note.get('summary_text') or note['corrected_text'])}\n",
        f"{owner_info}"
        f"▪️ Статус: {hbold(status)}",
        f"▪️ Категория: {hitalic(category)}",
        f"▪️ Создана: {note_date}"
    ]

    if due_date:
        text_parts.append(f"▪️ Срок: {hbold(due_date)}")
    if note.get('recurrence_rule'):
        text_parts.append(f"▪️ Повторение: ⭐ {hitalic(note['recurrence_rule'])}")

    text = "\n".join(text_parts)
    keyboard = get_note_view_actions_keyboard(note, page, user_id)

    try:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    if isinstance(event, types.CallbackQuery):
        await event.answer()


@router.callback_query(NoteAction.filter(F.action == "confirm_delete"))
async def confirm_delete_handler(callback: types.CallbackQuery, callback_data: NoteAction):
    """Запрашивает подтверждение на удаление."""
    text = (
        f"{callback.message.text}\n\n"
        f"‼️ {hbold('ВЫ УВЕРЕНЫ?')}\n"
        "Это действие необратимо. Заметка будет удалена навсегда."
    )
    keyboard = get_confirm_delete_keyboard(
        note_id=callback_data.note_id,
        page=callback_data.page,
        target_list=callback_data.target_list
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(Command("search_note"))
async def start_search_note(message: types.Message, state: FSMContext):
    await state.set_state(NotesSearchStates.waiting_for_query)
    await message.answer("Введите текст для поиска по вашим заметкам:")

@router.message(StateFilter(NotesSearchStates.waiting_for_query), F.text)
async def process_search_note_query(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    query = message.text.strip()
    await message.answer("🔎 Ищу подходящие заметки... Это может занять несколько секунд.")
    notes = await note_repo.get_all_notes_for_user(user_id)
    results = await search_notes_with_llm(notes, query, max_results=10)
    if not results:
        await message.answer("Ничего не найдено по вашему запросу.")
        return
    await message.answer(
        "Вот что удалось найти:",
        reply_markup=get_notes_search_results_keyboard(results)
    )

@router.callback_query(F.data == "search_notes")
async def search_notes_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(NotesSearchStates.waiting_for_query)
    await callback.message.answer("Введите текст для поиска по вашим заметкам:")
    await callback.answer()