# src/bot/modules/notes/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ....core.config import NOTE_CATEGORIES
from ..common_utils.callbacks import NoteAction, ShoppingListAction, PageNavigation


def get_undo_creation_keyboard(note_id: int, is_shopping_list: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой отмены создания заметки и просмотра."""
    builder = InlineKeyboardBuilder()

    if is_shopping_list:
        builder.button(
            text="🛒 Посмотреть список",
            callback_data=ShoppingListAction(action="show", note_id=note_id).pack()
        )
    else:
        builder.button(
            text="👀 Посмотреть детали",
            callback_data=NoteAction(action="view", note_id=note_id).pack()
        )

    builder.button(
        text="❌ Отменить",
        callback_data=NoteAction(action="undo_create", note_id=note_id).pack()
    )
    builder.adjust(2)
    return builder.as_markup()


def get_notes_list_display_keyboard(
        notes: list[dict],
        current_page: int,
        total_pages: int,
        is_archive_list: bool,
        current_user_id: int
) -> InlineKeyboardMarkup:
    """Формирует клавиатуру со списком заметок и пагинацией."""
    builder = InlineKeyboardBuilder()
    target_list_str = 'archive' if is_archive_list else 'active'

    for note in notes:
        is_owner = note.get('owner_id') == current_user_id
        shared_icon = "" if is_owner else "🤝"
        category = note.get('category')

        if category == 'Покупки':
            status_icon = "🛒"
        else:
            status_icon = "✅" if note.get('is_completed') else "📝"

        text_to_show = note.get('summary_text') or note['corrected_text']
        preview_text = f"{shared_icon}{status_icon} #{note['note_id']} - {text_to_show[:35]}"
        if len(text_to_show) > 35:
            preview_text += "..."

        builder.button(
            text=preview_text,
            callback_data=NoteAction(action="view", note_id=note['note_id'], page=current_page,
                                     target_list=target_list_str).pack()
        )
    builder.adjust(1)

    # Пагинация
    pagination_row_items = []
    if current_page > 1:
        pagination_row_items.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=PageNavigation(target="notes", page=current_page - 1,
                                                                               archived=is_archive_list).pack())
        )
    if total_pages > 1:
        pagination_row_items.append(
            InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="ignore_page_display")
        )
    if current_page < total_pages:
        pagination_row_items.append(
            InlineKeyboardButton(text="Вперед ➡️", callback_data=PageNavigation(target="notes", page=current_page + 1,
                                                                                archived=is_archive_list).pack())
        )
    if pagination_row_items:
        builder.row(*pagination_row_items)

    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="go_to_main_menu"))
    return builder.as_markup()


def get_note_view_actions_keyboard(note: dict, current_page: int, current_user_id: int) -> InlineKeyboardMarkup:
    """Формирует клавиатуру для детального просмотра заметки."""
    builder = InlineKeyboardBuilder()
    note_id = note['note_id']
    is_archived = note.get('is_archived', False)
    has_audio = bool(note.get('original_audio_telegram_file_id'))
    is_recurring = bool(note.get('recurrence_rule'))
    is_vip = note.get('is_vip', False)
    target_list_str = 'archive' if is_archived else 'active'
    is_owner = note.get('owner_id') == current_user_id

    # --- Кнопки для Активных заметок ---
    if not is_archived:
        # Не показываем "Выполнено" для Списка покупок, у него своя кнопка "Архивировать"
        if note.get('category') != 'Покупки':
            builder.button(text="✅ Выполнено",
                           callback_data=NoteAction(action="complete", note_id=note_id, page=current_page).pack())
        if is_owner:
            builder.button(text="✏️ Редактировать",
                           callback_data=NoteAction(action="edit", note_id=note_id, page=current_page).pack())
            builder.button(text="🤝 Поделиться",
                           callback_data=NoteAction(action="share", note_id=note_id, page=current_page).pack())

        builder.button(text="🗂️ Изменить категорию",
                       callback_data=NoteAction(action="change_category", note_id=note_id, page=current_page,
                                                target_list=target_list_str).pack())

        if is_recurring and is_vip and is_owner:
            builder.button(text="⭐ 🔁 Сделать разовой",
                           callback_data=NoteAction(action="stop_recurrence", note_id=note_id,
                                                    page=current_page).pack())

        if is_owner:
            builder.button(text="🗄️ В архив",
                           callback_data=NoteAction(action="archive", note_id=note_id, page=current_page).pack())

    # --- Кнопки для Архивных заметок ---
    else:
        if is_owner:
            builder.button(text="↩️ Восстановить",
                           callback_data=NoteAction(action="unarchive", note_id=note_id, page=current_page,
                                                    target_list=target_list_str).pack())
            builder.button(text="🗑️ Удалить навсегда",
                           callback_data=NoteAction(action="confirm_delete", note_id=note_id, page=current_page,
                                                    target_list=target_list_str).pack())

    # --- Общие кнопки ---
    if has_audio:
        builder.button(text="🎧 Прослушать оригинал",
                       callback_data=NoteAction(action="listen_audio", note_id=note_id).pack())

    list_button_text = "⬅️ К архиву" if is_archived else "⬅️ К списку заметок"
    builder.button(text=list_button_text,
                   callback_data=PageNavigation(target="notes", page=current_page, archived=is_archived).pack())

    builder.adjust(1)
    return builder.as_markup()


def get_category_selection_keyboard(note_id: int, page: int, target_list: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора новой категории для заметки."""
    builder = InlineKeyboardBuilder()
    for category in NOTE_CATEGORIES:
        builder.button(
            text=category,
            callback_data=NoteAction(action="set_category", note_id=note_id, page=page, target_list=target_list,
                                     category=category).pack()
        )
    builder.button(
        text="⬅️ Отмена",
        callback_data=NoteAction(action="view", note_id=note_id, page=page, target_list=target_list).pack()
    )
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def get_confirm_delete_keyboard(note_id: int, page: int, target_list: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="‼️ ДА, УДАЛИТЬ НАВСЕГДА ‼️",
        callback_data=NoteAction(action="delete", note_id=note_id, page=page, target_list=target_list).pack()
    )
    builder.button(
        text="Отмена",
        callback_data=NoteAction(action="view", note_id=note_id, page=page, target_list=target_list).pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def get_reminder_notification_keyboard(note_id: int, is_pre_reminder: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для сообщения с напоминанием."""
    builder = InlineKeyboardBuilder()
    # Основные действия доступны только для главного напоминания
    if not is_pre_reminder:
        builder.button(text="✅ Выполнено", callback_data=NoteAction(action="complete", note_id=note_id).pack())
        builder.button(text="Отложить на 1 час",
                       callback_data=NoteAction(action="snooze", note_id=note_id, snooze_minutes=60).pack())
        builder.button(text="Отложить на 3 часа",
                       callback_data=NoteAction(action="snooze", note_id=note_id, snooze_minutes=180).pack())

    builder.button(text="👀 Просмотреть заметку", callback_data=NoteAction(action="view", note_id=note_id).pack())
    builder.adjust(1, 2, 1) if not is_pre_reminder else builder.adjust(1)
    return builder.as_markup()


def get_shopping_list_keyboard(note_id: int, items: list, is_archived: bool) -> InlineKeyboardMarkup:
    """Клавиатура для управления списком покупок."""
    builder = InlineKeyboardBuilder()

    for index, item in enumerate(items):
        status_icon = "✅" if item.get('checked') else "⬜️"
        item_name = item.get('item_name', 'Без названия').strip()
        button_text = f"{status_icon} {item_name}"

        # В архиве кнопки неактивны
        if is_archived:
            builder.button(text=button_text, callback_data="ignore")
        else:
            builder.button(
                text=button_text,
                callback_data=ShoppingListAction(action="toggle", note_id=note_id, item_index=index).pack()
            )

    builder.adjust(1)  # Каждый товар на новой строке

    # Кнопки управления списком
    if not is_archived:
        builder.row(InlineKeyboardButton(
            text="🛒 Завершить и архивировать",
            callback_data=ShoppingListAction(action="archive", note_id=note_id).pack()
        ))

    builder.row(InlineKeyboardButton(
        text="⬅️ Назад к заметке",
        callback_data=NoteAction(action="view", note_id=note_id).pack()
    ))
    return builder.as_markup()