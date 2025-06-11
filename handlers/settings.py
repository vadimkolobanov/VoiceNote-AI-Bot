# handlers/settings.py
import logging
from datetime import time, datetime

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hbold, hcode

import database_setup as db
from inline_keyboards import (
    get_settings_menu_keyboard,
    get_timezone_selection_keyboard,
    get_reminder_time_keyboard,
    SettingsAction,
    TimezoneAction
)
from services.tz_utils import ALL_PYTZ_TIMEZONES
from states import ProfileSettingsStates

# handlers.profile больше не нужен здесь
# from handlers.profile import user_profile_display_handler

logger = logging.getLogger(__name__)
router = Router()


# --- Вспомогательная функция, чтобы не дублировать код ---
async def get_settings_text_and_keyboard(telegram_id: int) -> tuple[str, types.InlineKeyboardMarkup] | tuple[
    None, None]:
    """Формирует текст и клавиатуру для главного меню настроек."""
    user_profile = await db.get_user_profile(telegram_id)
    if not user_profile:
        return None, None

    current_tz = user_profile.get('timezone', 'UTC')
    current_rem_time = user_profile.get('default_reminder_time')
    if isinstance(current_rem_time, time):
        current_rem_time_str = current_rem_time.strftime('%H:%M')
    else:
        current_rem_time_str = "09:00"  # Fallback

    text = (
        f"{hbold('⚙️ Ваши настройки')}\n\n"
        f"Здесь вы можете персонализировать работу бота.\n\n"
        f"▪️ Текущий часовой пояс: {hcode(current_tz)}\n"
        f"▪️ Время напоминаний по умолчанию: {hcode(current_rem_time_str)}\n"
    )
    keyboard = get_settings_menu_keyboard()
    return text, keyboard


# --- Главное меню настроек ---

@router.callback_query(SettingsAction.filter(F.action == "go_to_main"))
async def show_main_settings_handler(callback_query: CallbackQuery, state: FSMContext):
    """Отображает главный экран настроек."""
    await state.clear()

    text, keyboard = await get_settings_text_and_keyboard(callback_query.from_user.id)
    if not text:
        await callback_query.answer("Профиль не найден. Пожалуйста, нажмите /start.", show_alert=True)
        return

    try:
        await callback_query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.warning(f"Could not edit settings message, sending new one: {e}")
        # Если редактирование не удалось, отправляем новое сообщение
        await callback_query.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    await callback_query.answer()


# --- Раздел "Часовой пояс" ---

@router.callback_query(SettingsAction.filter(F.action == "go_to_timezone"))
async def show_timezone_selection_handler(callback_query: CallbackQuery, state: FSMContext):
    """Отображает экран выбора часового пояса."""
    await state.clear()
    text = (
        f"{hbold('🕒 Настройка часового пояса')}\n\n"
        "Ваш часовой пояс используется для корректного отображения всех дат и времени в боте.\n\n"
        "Выберите ваш часовой пояс из списка или введите его вручную."
    )
    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_timezone_selection_keyboard()
    )
    await callback_query.answer()


@router.callback_query(TimezoneAction.filter(F.action == 'set'))
async def set_timezone_from_button_handler(callback_query: CallbackQuery, callback_data: TimezoneAction,
                                           state: FSMContext):
    """Обрабатывает установку часового пояса по кнопке."""
    telegram_id = callback_query.from_user.id

    success = await db.set_user_timezone(telegram_id, callback_data.tz_name)
    if success:
        await callback_query.answer(f"✅ Часовой пояс установлен: {callback_data.tz_name}", show_alert=True)
    else:
        await callback_query.answer("❌ Ошибка при установке часового пояса.", show_alert=True)

    # Возвращаемся в главное меню настроек
    await show_main_settings_handler(callback_query, state)


@router.callback_query(TimezoneAction.filter(F.action == 'manual_input'))
async def manual_timezone_input_handler(callback_query: CallbackQuery, state: FSMContext):
    """Запрашивает ручной ввод часового пояса."""
    await state.set_state(ProfileSettingsStates.awaiting_timezone)
    text = (
        f"{hbold('⌨️ Ручной ввод часового пояса')}\n\n"
        "Отправьте название в формате `Continent/City` (например, `Europe/Moscow`).\n\n"
        f"Для отмены отправьте /cancel."
    )
    await callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=get_timezone_selection_keyboard())
    await callback_query.answer("Ожидаю ваш ввод...")


@router.message(ProfileSettingsStates.awaiting_timezone, F.text)
async def process_manual_timezone_handler(message: types.Message, state: FSMContext):
    """Обрабатывает ручной ввод часового пояса."""
    timezone_name = message.text.strip()

    if timezone_name not in ALL_PYTZ_TIMEZONES:
        await message.reply(
            f"❌ Часовой пояс {hcode(timezone_name)} не найден.\n"
            "Проверьте написание (например, `Europe/Berlin`) и попробуйте снова, или выберите из списка."
        )
        return

    telegram_id = message.from_user.id
    await db.set_user_timezone(telegram_id, timezone_name)
    await state.clear()

    await message.answer(f"✅ Часовой пояс установлен: {timezone_name}")

    # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
    # Не используем фейковый колбэк, а просто отправляем новое сообщение с меню настроек
    text, keyboard = await get_settings_text_and_keyboard(telegram_id)
    if text:
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


# --- Раздел "Время напоминаний" ---

@router.callback_query(SettingsAction.filter(F.action == "go_to_reminders"))
async def show_reminder_time_handler(callback_query: CallbackQuery):
    """Отображает экран выбора времени напоминаний по умолчанию."""
    text = (
        f"{hbold('⏰ Время напоминаний по умолчанию')}\n\n"
        "Это время будет использоваться для напоминаний, у которых в тексте была указана только дата (например, 'завтра' или '15 июля')."
    )
    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_reminder_time_keyboard()
    )
    await callback_query.answer()


@router.callback_query(SettingsAction.filter(F.action == "set_rem_time"))
async def set_reminder_time_from_button_handler(callback: CallbackQuery, callback_data: SettingsAction,
                                                state: FSMContext):
    """Устанавливает время напоминания по кнопке."""
    time_str = callback_data.value.replace('-', ':')

    try:
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        success = await db.set_user_default_reminder_time(callback.from_user.id, time_obj)
        if success:
            await callback.answer(f"✅ Время напоминаний установлено на {time_str}", show_alert=True)
        else:
            await callback.answer("❌ Ошибка при установке времени.", show_alert=True)
    except ValueError:
        await callback.answer("Неверный формат времени.", show_alert=True)

    await show_main_settings_handler(callback, state)


@router.callback_query(SettingsAction.filter(F.action == "manual_rem_time"))
async def manual_reminder_time_handler(callback: CallbackQuery, state: FSMContext):
    """Запрашивает ручной ввод времени напоминания."""
    await state.set_state(ProfileSettingsStates.awaiting_reminder_time)
    text = (
        f"{hbold('⌨️ Ручной ввод времени')}\n\n"
        "Пожалуйста, отправьте желаемое время в формате `ЧЧ:ММ` (например, `09:30` или `22:00`).\n\n"
        f"Для отмены отправьте /cancel."
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_reminder_time_keyboard())
    await callback.answer("Ожидаю ваш ввод...")


@router.message(ProfileSettingsStates.awaiting_reminder_time, F.text)
async def process_manual_reminder_time_handler(message: types.Message, state: FSMContext):
    """Обрабатывает ручной ввод времени напоминания."""
    try:
        time_obj = datetime.strptime(message.text.strip(), '%H:%M').time()
        telegram_id = message.from_user.id
        await db.set_user_default_reminder_time(telegram_id, time_obj)
        await state.clear()
        await message.answer(f"✅ Время напоминаний установлено на {message.text.strip()}.")

        # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
        # Не используем фейковый колбэк, а просто отправляем новое сообщение с меню настроек
        text, keyboard = await get_settings_text_and_keyboard(telegram_id)
        if text:
            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

    except ValueError:
        await message.reply(
            "❌ Неверный формат времени. Пожалуйста, введите время в формате `ЧЧ:ММ`, например, `09:30`.")
        return