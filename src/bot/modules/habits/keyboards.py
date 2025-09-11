# src/bot/modules/habits/keyboards.py
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from ....bot.common_utils.callbacks import HabitAction, HabitTrack


def get_habits_menu_keyboard(has_habits: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_habits:
        builder.button(text="➕ Добавить новые", callback_data="add_new_habits")
        builder.button(text="✏️ Управлять привычками", callback_data="manage_habits")
    else:
        builder.button(text="🚀 Сформировать первые привычки", callback_data="add_new_habits")

    builder.button(text="🏠 Главное меню", callback_data="go_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_habit_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, всё верно", callback_data=HabitAction(action="confirm_add").pack())
    builder.button(text="❌ Отмена", callback_data=HabitAction(action="cancel").pack())
    builder.adjust(1)
    return builder.as_markup()


def get_habit_tracking_keyboard(habit_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выполнено", callback_data=HabitTrack(habit_id=habit_id, status="completed").pack())
    builder.button(text="❌ Пропустить", callback_data=HabitTrack(habit_id=habit_id, status="skipped").pack())
    builder.adjust(2)
    return builder.as_markup()


def get_manage_habits_keyboard(habits: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for habit in habits:
        builder.button(
            text=f"🗑️ Удалить: {habit['name']}",
            callback_data=HabitAction(action="delete", habit_id=habit['id']).pack()
        )

    builder.button(text="⬅️ Назад", callback_data="habits_menu")
    builder.adjust(1)
    return builder.as_markup()