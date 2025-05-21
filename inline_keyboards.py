# inline_keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData

# Используем CallbackData для более структурированных callback'ов
class NoteCallbackFactory(CallbackData, prefix="note"):
    action: str # "delete", "view", "edit_category", etc.
    note_id: int | None = None # note_id нужен для действий с конкретной заметкой

def get_action_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру для выбора основного действия.
    """
    buttons = [
        [InlineKeyboardButton(text="📝 Мои заметки", callback_data="my_notes")],

        [InlineKeyboardButton(text="🔊 Профиль", callback_data="user_profile")],
        # [InlineKeyboardButton(text="❌ Настройки", callback_data="settings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_confirm_save_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру для подтверждения или отмены сохранения заметки.
    Используется с FSM.
    """
    buttons = [
        [InlineKeyboardButton(text="✅ Сохранить", callback_data="confirm_save_note")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_save_note")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_note_actions_keyboard(note_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для действий с конкретной заметкой (пока только удаление).
    """
    buttons = [
        # Используем фабрику для callback_data
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=NoteCallbackFactory(action="delete", note_id=note_id).pack())]
        # Сюда можно добавить "✏️ Редактировать", "🏷️ Категория" и т.д. в будущем
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)