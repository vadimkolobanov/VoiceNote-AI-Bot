# src/bot/modules/common/keyboards.py
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ....core import config
from ..common_utils.callbacks import PageNavigation, SettingsAction, InfoAction


def get_main_menu_keyboard(is_vip: bool = False) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру главного меню."""
    builder = InlineKeyboardBuilder()

    if not is_vip:
        builder.button(
            text="🚀 Получить VIP бесплатно",
            callback_data=SettingsAction(action="get_free_vip").pack()
        )

    builder.button(text="📝 Мои заметки", callback_data=PageNavigation(target="notes", page=1, archived=False).pack())
    builder.button(text="🗄️ Архив", callback_data=PageNavigation(target="notes", page=1, archived=True).pack())
    builder.button(text="👤 Профиль", callback_data="user_profile")
    builder.button(text="⚙️ Настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.button(text="ℹ️ Инфо", callback_data=InfoAction(action="main").pack())

    if config.DONATION_URL:
        builder.button(text="❤️ Поддержать проект", callback_data="show_donate_info")

    builder.button(text="💬 Сообщить о проблеме", callback_data="report_problem")

    # Адаптивная верстка
    if not is_vip:
        builder.adjust(1, 2, 2, 2, 1)
    else:
        builder.adjust(2, 2, 2, 1)

    return builder.as_markup()


def get_info_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для информационного раздела."""
    builder = InlineKeyboardBuilder()
    builder.button(text="❓ Как пользоваться", callback_data=InfoAction(action="how_to_use").pack())
    builder.button(text="⭐ VIP-возможности", callback_data=InfoAction(action="vip_features").pack())

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


def get_donation_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для раздела поддержки проекта."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Поддержать (ЮMoney)", url=config.DONATION_URL)
    builder.button(text="🏠 Главное меню", callback_data="go_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()