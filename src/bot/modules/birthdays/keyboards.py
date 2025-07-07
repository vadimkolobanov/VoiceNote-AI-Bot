# src/bot/modules/birthdays/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ...common_utils.callbacks import BirthdayAction, PageNavigation, SettingsAction
from ....core import config



def get_birthdays_list_keyboard(birthdays: list[dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Формирует список дней рождений с кнопками удаления и пагинацией."""
    builder = InlineKeyboardBuilder()

    # Список дней рождений
    for bday in birthdays:
        year_str = f" ({bday['birth_year']})" if bday['birth_year'] else ""
        date_str = f"{bday['birth_day']:02}.{bday['birth_month']:02}{year_str}"
        builder.button(
            text=f"🎂 {bday['person_name']} - {date_str}",
            callback_data="ignore_bday_view"
        )
        builder.button(
            text="🗑️",
            callback_data=BirthdayAction(action="delete", birthday_id=bday['id'], page=page).pack()
        )
    builder.adjust(2)  # Кнопка с датой и кнопка удаления в один ряд

    # Пагинация
    pagination_row = []
    if page > 1:
        pagination_row.append(
            InlineKeyboardButton(text="⬅️", callback_data=PageNavigation(target="birthdays", page=page - 1).pack())
        )
    if total_pages > 1:
        pagination_row.append(
            InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore")
        )
    if page < total_pages:
        pagination_row.append(
            InlineKeyboardButton(text="➡️", callback_data=PageNavigation(target="birthdays", page=page + 1).pack())
        )

    if pagination_row:
        builder.row(*pagination_row)

    return builder.as_markup()


def get_birthdays_menu_keyboard(is_vip: bool, current_count: int) -> InlineKeyboardMarkup:
    """Формирует меню управления под списком дней рождений."""
    builder = InlineKeyboardBuilder()

    # Кнопка добавления или предложение купить VIP
    if is_vip or current_count < config.MAX_NOTES_MVP:
        builder.button(
            text="➕ Добавить вручную",
            callback_data=BirthdayAction(action="add_manual").pack()
        )
    else:
        builder.button(
            text=f"⭐ Увеличить лимит (>{config.MAX_NOTES_MVP})",
            callback_data=SettingsAction(action="request_vip").pack()
        )

    # Кнопка импорта для VIP
    if is_vip:
        builder.button(
            text="📥 Импорт из файла (VIP)",
            callback_data=BirthdayAction(action="import_file").pack()
        )

    # Кнопка "назад"
    builder.button(
        text="👤 Назад в профиль",
        callback_data="user_profile"  # Простая строка, т.к. это уникальный колбэк
    )

    builder.adjust(1)
    return builder.as_markup()


def get_full_birthdays_keyboard(
        birthdays: list[dict],
        page: int,
        total_pages: int,
        is_vip: bool,
        total_count: int
) -> InlineKeyboardMarkup:
    """Собирает единую клавиатуру из списка и меню."""
    list_kb = get_birthdays_list_keyboard(birthdays, page, total_pages)
    menu_kb = get_birthdays_menu_keyboard(is_vip, total_count)

    # Объединяем клавиатуры
    combined_builder = InlineKeyboardBuilder()
    if birthdays:  # Добавляем список, только если он есть
        for row in list_kb.inline_keyboard:
            combined_builder.row(*row)

    for row in menu_kb.inline_keyboard:
        combined_builder.row(*row)

    return combined_builder.as_markup()