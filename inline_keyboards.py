# inline_keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder


# --- CallbackData Factories ---

class NoteAction(CallbackData, prefix="note_act"):
    """
    CallbackData для действий с конкретной заметкой.
    `action`: 'view', 'delete', 'edit', 'archive', 'unarchive', 'confirm_delete'
    `note_id`: ID заметки.
    `page`: Текущая страница списка заметок (для возврата).
    `target_list`: 'active' или 'archive', чтобы знать, в какой список возвращаться.
    """
    action: str
    note_id: int
    page: int = 1
    target_list: str = 'active'


class PageNavigation(CallbackData, prefix="pg_nav"):
    """
    CallbackData для пагинации.
    `target`: 'notes'
    `page`: Номер страницы для отображения.
    `archived`: Флаг для отображения архивированных заметок (True/False).
    """
    target: str
    page: int
    archived: bool = False


# --- Keyboard Generators ---

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру главного меню."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📝 Мои заметки",
        callback_data=PageNavigation(target="notes", page=1, archived=False).pack()
    )
    builder.button(
        text="🗄️ Архив",
        callback_data=PageNavigation(target="notes", page=1, archived=True).pack()
    )
    builder.button(
        text="👤 Профиль",
        callback_data="user_profile"
    )
    builder.adjust(2, 1)  # Первые две кнопки в ряд, третья на новой строке
    return builder.as_markup()


def get_note_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения или отмены сохранения заметки."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Сохранить", callback_data="confirm_save_note")
    builder.button(text="❌ Отмена", callback_data="cancel_save_note")
    builder.adjust(2)
    return builder.as_markup()


def get_notes_list_display_keyboard(
        notes: list[dict],
        current_page: int,
        total_pages: int,
        is_archive_list: bool
) -> InlineKeyboardMarkup:
    """
    Формирует универсальную клавиатуру для списка активных или архивных заметок.
    """
    builder = InlineKeyboardBuilder()

    target_list_str = 'archive' if is_archive_list else 'active'

    if not notes and current_page == 1:
        pass  # Клавиатура будет содержать только кнопки управления ниже
    else:
        for note in notes:
            preview_text = f"#{note['note_id']} - {note['corrected_text'][:35]}"
            if len(note['corrected_text']) > 35:
                preview_text += "..."
            builder.button(
                text=preview_text,
                callback_data=NoteAction(action="view", note_id=note['note_id'], page=current_page,
                                         target_list=target_list_str).pack()
            )

    # Кнопки пагинации
    pagination_row_items = []
    if current_page > 1:
        pagination_row_items.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=PageNavigation(target="notes", page=current_page - 1, archived=is_archive_list).pack()
        ))

    if total_pages > 1:
        pagination_row_items.append(InlineKeyboardButton(
            text=f"{current_page}/{total_pages}",
            callback_data="ignore_page_display"  # Заглушка
        ))

    if current_page < total_pages:
        pagination_row_items.append(InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=PageNavigation(target="notes", page=current_page + 1, archived=is_archive_list).pack()
        ))

    builder.adjust(1)  # Каждая заметка на новой строке

    if pagination_row_items:
        builder.row(*pagination_row_items)

    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu_from_notes"))
    return builder.as_markup()


def get_note_view_actions_keyboard(note_id: int, current_page: int, is_archived: bool) -> InlineKeyboardMarkup:
    """
    Клавиатура действий при детальном просмотре заметки.
    Меняется в зависимости от того, архивирована заметка или нет.
    """
    builder = InlineKeyboardBuilder()
    target_list_str = 'archive' if is_archived else 'active'

    if not is_archived:
        # Действия для активной заметки
        builder.button(
            text="✏️ Редактировать",
            callback_data=NoteAction(action="edit", note_id=note_id, page=current_page,
                                     target_list=target_list_str).pack()
        )
        builder.button(
            text="🗄️ В архив",
            callback_data=NoteAction(action="archive", note_id=note_id, page=current_page,
                                     target_list=target_list_str).pack()
        )
        builder.adjust(2)  # Редактировать и В архив в один ряд
    else:
        # Действия для архивированной заметки
        builder.button(
            text="↩️ Восстановить",
            callback_data=NoteAction(action="unarchive", note_id=note_id, page=current_page,
                                     target_list=target_list_str).pack()
        )

    # Общие действия для всех заметок
    builder.button(
        text="🗑️ Удалить навсегда",
        callback_data=NoteAction(action="confirm_delete", note_id=note_id, page=current_page,
                                 target_list=target_list_str).pack()
    )

    # Кнопка возврата к соответствующему списку
    list_button_text = "⬅️ К архиву" if is_archived else "⬅️ К списку заметок"
    builder.button(
        text=list_button_text,
        callback_data=PageNavigation(target="notes", page=current_page, archived=is_archived).pack()
    )

    if not is_archived:
        builder.adjust(2, 1, 1)  # (Редакт, Архив), (Удалить), (К списку)
    else:
        builder.adjust(1, 1, 1)  # (Восстановить), (Удалить), (К списку)

    return builder.as_markup()


def get_confirm_delete_keyboard(note_id: int, page: int, target_list: str) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения окончательного удаления заметки."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="‼️ ДА, УДАЛИТЬ НАВСЕГДА ‼️",
        callback_data=NoteAction(action="delete", note_id=note_id, page=page, target_list=target_list).pack()
    )
    builder.button(
        text="Отмена",
        callback_data=NoteAction(action="view", note_id=note_id, page=page, target_list=target_list).pack()
        # Возврат к просмотру
    )
    builder.adjust(1)
    return builder.as_markup()