# src/bot/modules/profile/keyboards.py
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ....services.tz_utils import COMMON_TIMEZONES
from ..common_utils.callbacks import SettingsAction, TimezoneAction, PageNavigation


def get_profile_actions_keyboard(has_active_shopping_list: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура с действиями в профиле пользователя."""
    builder = InlineKeyboardBuilder()

    if has_active_shopping_list:
        builder.button(text="🛒 Активный список покупок", callback_data="show_active_shopping_list")
        builder.button(text="🤝 Поделиться списком", callback_data="share_active_shopping_list")

    builder.button(text="🎂 Дни рождения", callback_data=PageNavigation(target="birthdays", page=1).pack())
    builder.button(text="⚙️ Настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.button(text="🏠 Главное меню", callback_data="go_to_main_menu")

    # Верстка: 2 кнопки в ряд для списка покупок, если он есть
    builder.adjust(2 if has_active_shopping_list else 1, 1, 1)
    return builder.as_markup()


def get_settings_menu_keyboard(
        is_vip: bool,
        daily_digest_enabled: bool,
        is_alice_linked: bool
) -> InlineKeyboardMarkup:
    """Клавиатура главного меню настроек."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🕒 Часовой пояс", callback_data=SettingsAction(action="go_to_timezone").pack())

    if is_vip:
        digest_btn_text = "☀️ Выключить утреннюю сводку" if daily_digest_enabled else "☀️ Включить утреннюю сводку"
        builder.button(text=digest_btn_text, callback_data=SettingsAction(action="toggle_digest").pack())

    builder.button(text="⏰ Время напоминаний (⭐VIP)", callback_data=SettingsAction(action="go_to_reminders").pack())
    builder.button(text="🔔 Пред-напоминания (⭐VIP)", callback_data=SettingsAction(action="go_to_pre_reminders").pack())

    if not is_alice_linked:
        builder.button(text="🔗 Привязать Яндекс.Алису", callback_data=SettingsAction(action="link_alice").pack())

    builder.button(text="👤 Назад в профиль", callback_data="user_profile")

    # Верстка
    layout = [1]
    if is_vip:
        layout.append(1)
    layout.append(2)
    if not is_alice_linked:
        layout.append(1)
    layout.append(1)
    builder.adjust(*layout)

    return builder.as_markup()


def get_request_vip_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой запроса VIP и возврата назад."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Отправить заявку на VIP", callback_data=SettingsAction(action="request_vip").pack())
    builder.button(text="⬅️ Назад в настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.adjust(1)
    return builder.as_markup()


def get_pre_reminder_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора времени для пред-напоминаний."""
    options = {"Не напоминать": 0, "За 30 минут": 30, "За 1 час": 60, "За 3 часа": 180, "За 24 часа": 1440}
    builder = InlineKeyboardBuilder()
    for text, minutes in options.items():
        builder.button(text=text, callback_data=SettingsAction(action="set_pre_rem", value=str(minutes)).pack())
    builder.button(text="⬅️ Назад в настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def get_reminder_time_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора времени напоминаний по умолчанию."""
    builder = InlineKeyboardBuilder()
    times = ["09:00", "10:00", "12:00", "18:00", "20:00", "21:00"]
    for t in times:
        safe_time_value = t.replace(':', '-')
        builder.button(text=t, callback_data=SettingsAction(action="set_rem_time", value=safe_time_value).pack())
    builder.button(text="⌨️ Ввести вручную", callback_data=SettingsAction(action="manual_rem_time").pack())
    builder.button(text="⬅️ Назад в настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.adjust(3, 3, 1, 1)
    return builder.as_markup()


def get_timezone_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора часового пояса."""
    builder = InlineKeyboardBuilder()
    for display_name, iana_name in COMMON_TIMEZONES.items():
        builder.button(text=display_name, callback_data=TimezoneAction(action="set", tz_name=iana_name).pack())
    builder.button(text="⌨️ Ввести вручную", callback_data=TimezoneAction(action="manual_input").pack())
    builder.button(text="⬅️ Назад в настройки", callback_data=SettingsAction(action="go_to_main").pack())
    builder.adjust(2, 2, 2, 2, 2, 1, 1)
    return builder.as_markup()