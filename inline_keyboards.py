# inline_keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder


# --- CallbackData Factories ---

class NoteAction(CallbackData, prefix="note_act"):
    """
    CallbackData для действий с конкретной заметкой.
    `action`: 'view', 'delete', 'edit', etc.
    `note_id`: ID заметки.
    `page`: Текущая страница списка заметок (для возврата).
    """
    action: str
    note_id: int
    page: int = 1  # Страница по умолчанию для возврата, если не указана


class PageNavigation(CallbackData, prefix="pg_nav"):
    """
    CallbackData для пагинации.
    `target`: "notes" (для списка заметок), можно расширить для других списков.
    `page`: Номер страницы для отображения.
    """
    target: str
    page: int


# --- Keyboard Generators ---

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру главного меню."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📝 Мои заметки",
        callback_data=PageNavigation(target="notes", page=1).pack()
    )
    builder.button(
        text="👤 Профиль",
        callback_data="user_profile"  # Простой callback для профиля
    )
    builder.adjust(1)  # Каждая кнопка на новой строке
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
        total_pages: int
) -> InlineKeyboardMarkup:
    """
    Формирует клавиатуру для отображения списка заметок с пагинацией.
    Каждая заметка является кнопкой для детального просмотра.
    """
    builder = InlineKeyboardBuilder()

    if not notes and current_page == 1:  # Если заметок нет вообще
        pass  # Клавиатура будет содержать только кнопку "Главное меню" ниже
    elif not notes and current_page > 1:  # Если на текущей странице нет, а раньше были
        builder.button(
            text="⚠️ Заметок нет, обновить список",
            callback_data=PageNavigation(target="notes", page=max(1, current_page - 1)).pack()
        )
    else:
        for note in notes:
            # Отображаем ID и начало текста заметки
            preview_text = f"#{note['note_id']} - {note['corrected_text'][:35]}"
            if len(note['corrected_text']) > 35:
                preview_text += "..."
            builder.button(
                text=preview_text,
                callback_data=NoteAction(action="view", note_id=note['note_id'], page=current_page).pack()
            )

    # Кнопки пагинации
    pagination_row_items = []
    if current_page > 1:
        pagination_row_items.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=PageNavigation(target="notes", page=current_page - 1).pack()
        ))

    if total_pages > 1:  # Показываем номер страницы, если их больше одной
        pagination_row_items.append(InlineKeyboardButton(
            text=f"{current_page}/{total_pages}",
            callback_data="ignore_page_display"  # Кнопка-заглушка для отображения
        ))

    if current_page < total_pages:
        pagination_row_items.append(InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=PageNavigation(target="notes", page=current_page + 1).pack()
        ))

    builder.adjust(1)  # Каждая заметка на новой строке

    if pagination_row_items:
        builder.row(*pagination_row_items)  # Добавляем кнопки пагинации в один ряд

    builder.row(InlineKeyboardButton(text="Главное меню", callback_data="main_menu_from_notes"))
    return builder.as_markup()


def get_note_view_actions_keyboard(note_id: int, current_page: int) -> InlineKeyboardMarkup:
    """Клавиатура действий при детальном просмотре заметки."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🗑️ Удалить",
        callback_data=NoteAction(action="delete", note_id=note_id, page=current_page).pack()
    )
    # Сюда можно добавить "✏️ Редактировать" и т.д.
    builder.button(
        text="⬅️ К списку заметок",
        callback_data=PageNavigation(target="notes", page=current_page).pack()
    )
    builder.adjust(1)  # Каждую кнопку на новой строке для ясности
    return builder.as_markup()