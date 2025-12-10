# src/bot/modules/onboarding/keyboards.py
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from ...common_utils.callbacks import OnboardingAction
from ....services.tz_utils import COMMON_TIMEZONES


def get_welcome_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для первого шага обучения."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🚀 Начать!",
        callback_data=OnboardingAction(action="next_step").pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def get_next_step_keyboard(text: str = "✅ Понятно, дальше") -> InlineKeyboardMarkup:
    """Универсальная клавиатура для перехода к следующему шагу."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=text,
        callback_data=OnboardingAction(action="next_step").pack()
    )
    return builder.as_markup()


def get_timezone_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора часового пояса в процессе обучения."""
    builder = InlineKeyboardBuilder()
    for display_name, iana_name in list(COMMON_TIMEZONES.items())[:6]:
        builder.button(
            text=display_name,
            callback_data=OnboardingAction(action="set_tz", tz_name=iana_name).pack()
        )
    builder.adjust(2)
    return builder.as_markup()


def get_vip_choice_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с выбором: получить VIP или пропустить."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🚀 Да, хочу VIP бесплатно!",
        callback_data=OnboardingAction(action="get_vip").pack()
    )
    builder.button(
        text="Нет, спасибо",
        callback_data=OnboardingAction(action="next_step").pack()
    )
    builder.adjust(1)
    return builder.as_markup()


def get_final_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для завершения обучения."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🎉 Начать работу!",
        callback_data=OnboardingAction(action="finish").pack()
    )
    return builder.as_markup()