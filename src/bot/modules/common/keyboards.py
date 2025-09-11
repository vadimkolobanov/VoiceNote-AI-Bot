# src/bot/modules/common/keyboards.py
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ....core import config
from ...common_utils.callbacks import PageNavigation, SettingsAction, InfoAction


def get_main_menu_keyboard(is_vip: bool = False, has_active_list: bool = False) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру главного меню."""
    builder = InlineKeyboardBuilder()

    if has_active_list:
        builder.button(
            text="🛒 Мой список покупок",
            callback_data="show_active_shopping_list"
        )

    if not is_vip:
        builder.button(
            text="🚀 Получить VIP бесплатно",
            callback_data=SettingsAction(action="get_free_vip").pack()
        )

    builder.button(text="📝 Мои заметки", callback_data=PageNavigation(target="notes", page=1, archived=False).pack())
    builder.button(text="💪 Мои привычки", callback_data="habits_menu")
    builder.button(text="👤 Профиль", callback_data="user_profile")
    builder.button(text="⚙️ Настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.button(text="❓ Помощь", callback_data=InfoAction(action="main").pack())

    if config.DONATION_URL:
        builder.button(text="❤️ Поддержать проект", callback_data="show_donate_info")

    adjust_layout = []
    if has_active_list:
        adjust_layout.append(1)
    if not is_vip:
        adjust_layout.append(1)

    # Обновляем layout: теперь у нас 2 кнопки в ряду (Заметки, Привычки), потом 2 (Профиль, Настройки)
    adjust_layout.extend([2, 2, 1, 1])
    builder.adjust(*adjust_layout)

    return builder.as_markup()


def get_help_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для раздела Помощи."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📖 Как пользоваться (Гайды)", callback_data=InfoAction(action="guides").pack())
    builder.button(text="💬 Сообщить о проблеме", callback_data="report_problem")

    if config.NEWS_CHANNEL_URL:
        builder.button(text="📢 Новости бота", url=config.NEWS_CHANNEL_URL)
    if config.CHAT_URL:
        builder.button(text="💬 Чат для обсуждений", url=config.CHAT_URL)

    builder.button(text="🏠 Главное меню", callback_data="go_to_main_menu")

    layout = [2]
    if config.NEWS_CHANNEL_URL and config.CHAT_URL:
        layout.append(2)
    elif config.NEWS_CHANNEL_URL or config.CHAT_URL:
        layout.append(1)
    layout.append(1)
    builder.adjust(*layout)

    return builder.as_markup()


def get_guides_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру со списком гайдов."""
    builder = InlineKeyboardBuilder()

    guides = {
        "Как создать заметку?": "create_note",
        "Как создать список покупок?": "shopping_list",
        "Как поделиться списком/заметкой?": "share_note",
        "Как записать день рождения?": "add_birthday",
        "💪 Как пользоваться трекером привычек?": "habit_tracker",
        "Что такое утренняя сводка? (VIP)": "daily_digest",
        "Как настроить часовой пояс?": "set_timezone",
    }

    for text, topic in guides.items():
        builder.button(text=text, callback_data=InfoAction(action="guide_topic", guide_topic=topic).pack())

    builder.button(text="⬅️ Назад в Помощь", callback_data=InfoAction(action="main").pack())

    builder.adjust(1)
    return builder.as_markup()


def get_back_to_guides_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для возврата к списку гайдов."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ К списку гайдов", callback_data=InfoAction(action="guides").pack())
    return builder.as_markup()


def get_donation_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для раздела поддержки проекта."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Поддержать (ЮMoney)", url=config.DONATION_URL)
    builder.button(text="🏠 Главное меню", callback_data="go_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()