# handlers/settings.py
import logging
from datetime import time, datetime

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hbold, hcode, hitalic

from alice_webhook import get_link_code_for_user

import database_setup as db
from config import ADMIN_TELEGRAM_ID
from inline_keyboards import (
    get_settings_menu_keyboard,
    get_timezone_selection_keyboard,
    get_reminder_time_keyboard,
    get_pre_reminder_keyboard,
    get_request_vip_keyboard,
    SettingsAction,
    TimezoneAction,
    get_main_menu_keyboard # Добавляем импорт
)
from services.tz_utils import ALL_PYTZ_TIMEZONES
from states import ProfileSettingsStates

logger = logging.getLogger(__name__)
router = Router()


def format_pre_reminder_minutes(minutes: int) -> str:
    """Форматирует минуты в человекочитаемый текст."""
    if minutes == 0:
        return "Отключены"
    if minutes < 60:
        return f"За {minutes} мин."
    hours = minutes // 60
    return f"За {hours} ч."


async def get_settings_text_and_keyboard(telegram_id: int) -> tuple[str, types.InlineKeyboardMarkup] | tuple[
    None, None]:
    """Формирует текст и клавиатуру для главного меню настроек."""
    user_profile = await db.get_user_profile(telegram_id)
    if not user_profile:
        return None, None

    current_tz = user_profile.get('timezone', 'UTC')
    current_rem_time = user_profile.get('default_reminder_time')
    current_pre_rem_minutes = user_profile.get('pre_reminder_minutes', 60)
    is_vip = user_profile.get('is_vip', False)
    digest_enabled = user_profile.get('daily_digest_enabled', True)
    is_alice_linked = bool(user_profile.get('alice_user_id'))

    if isinstance(current_rem_time, time):
        current_rem_time_str = current_rem_time.strftime('%H:%M')
    else:
        current_rem_time_str = "09:00"

    text_parts = [
        f"{hbold('⚙️ Ваши настройки')}\n",
        "Здесь вы можете персонализировать работу бота.\n",
        f"▪️ Текущий часовой пояс: {hcode(current_tz)}",
        f"▪️ Время напоминаний по умолчанию: {hcode(current_rem_time_str)} (⭐ VIP)",
        f"▪️ Предварительные напоминания: {hbold(format_pre_reminder_minutes(current_pre_rem_minutes))} (⭐ VIP)",
    ]
    if is_vip:
        digest_status = "Включена" if digest_enabled else "Выключена"
        text_parts.append(f"▪️ Утренняя сводка: {hbold(digest_status)} (⭐ VIP)")

    text = "\n".join(text_parts)
    keyboard = get_settings_menu_keyboard(
        daily_digest_enabled=digest_enabled if is_vip else False,
        is_alice_linked=is_alice_linked
    )
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
    except Exception:
        await callback_query.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    await callback_query.answer()

# --- НОВЫЙ ХЕНДЛЕР для возврата в главное меню из любого места ---
@router.callback_query(F.data == "go_to_main_menu")
async def go_to_main_menu_from_anywhere_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🏠 Вы в главном меню.", reply_markup=get_main_menu_keyboard())
    await callback.answer()


# --- Раздел "Утренняя сводка" (VIP) ---
@router.callback_query(SettingsAction.filter(F.action == "toggle_digest"))
async def toggle_daily_digest_handler(callback: CallbackQuery, state: FSMContext):
    user_profile = await db.get_user_profile(callback.from_user.id)
    if not user_profile.get('is_vip'):
        await callback.answer("⭐ Эта функция доступна только для VIP-пользователей.", show_alert=True)
        return

    current_status = user_profile.get('daily_digest_enabled', True)
    new_status = not current_status
    await db.set_user_daily_digest_status(callback.from_user.id, new_status)

    status_text = "включена" if new_status else "выключена"
    await callback.answer(f"✅ Утренняя сводка {status_text}", show_alert=False)
    await show_main_settings_handler(callback, state)


# --- Раздел "Часовой пояс" (доступен всем) ---
@router.callback_query(SettingsAction.filter(F.action == "go_to_timezone"))
async def show_timezone_selection_handler(callback_query: CallbackQuery, state: FSMContext):
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
    telegram_id = callback_query.from_user.id

    success = await db.set_user_timezone(telegram_id, callback_data.tz_name)
    if success:
        await callback_query.answer(f"✅ Часовой пояс установлен: {callback_data.tz_name}", show_alert=True)
    else:
        await callback_query.answer("❌ Ошибка при установке часового пояса.", show_alert=True)

    await show_main_settings_handler(callback_query, state)


@router.callback_query(TimezoneAction.filter(F.action == 'manual_input'))
async def manual_timezone_input_handler(callback_query: CallbackQuery, state: FSMContext):
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

    text, keyboard = await get_settings_text_and_keyboard(telegram_id)
    if text:
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


# --- Раздел "Время напоминаний" (VIP) ---

@router.callback_query(SettingsAction.filter(F.action == "go_to_reminders"))
async def show_reminder_time_handler(callback_query: CallbackQuery):
    user_profile = await db.get_user_profile(callback_query.from_user.id)
    if not user_profile.get('is_vip'):
        text = (
            f"⭐ {hbold('Настройка времени напоминаний')}\n\n"
            "Эта функция доступна только для **VIP-пользователей**.\n\n"
            "Она позволяет боту автоматически устанавливать напоминания на удобное вам время, "
            "даже если вы сказали только дату (например, 'завтра').\n\n"
            "Хотите получить тестовый VIP-доступ?"
        )
        await callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=get_request_vip_keyboard())
        await callback_query.answer()
        return

    text = (
        f"{hbold('⏰ Время напоминаний по умолчанию')}\n\n"
        "Это время будет использоваться для напоминаний, у которых в тексте была указана только дата."
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
    time_str = callback_data.value.replace('-', ':')

    try:
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        success = await db.set_user_default_reminder_time(callback.from_user.id, time_obj)
        if success:
            await callback.answer(f"✅ Время напоминаний установлено на {time_str}", show_alert=False)
        else:
            await callback.answer("❌ Ошибка при установке времени.", show_alert=True)
    except ValueError:
        await callback.answer("Неверный формат времени.", show_alert=True)

    await show_main_settings_handler(callback, state)


@router.callback_query(SettingsAction.filter(F.action == "manual_rem_time"))
async def manual_reminder_time_handler(callback: CallbackQuery, state: FSMContext):
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
    try:
        time_obj = datetime.strptime(message.text.strip(), '%H:%M').time()
        telegram_id = message.from_user.id
        await db.set_user_default_reminder_time(telegram_id, time_obj)
        await state.clear()
        await message.answer(f"✅ Время напоминаний установлено на {message.text.strip()}.")

        text, keyboard = await get_settings_text_and_keyboard(telegram_id)
        if text:
            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

    except ValueError:
        await message.reply(
            "❌ Неверный формат времени. Пожалуйста, введите время в формате `ЧЧ:ММ`, например, `09:30`.")
        return


# --- Раздел "Предварительные напоминания" (VIP) ---

@router.callback_query(SettingsAction.filter(F.action == "go_to_pre_reminders"))
async def show_pre_reminder_handler(callback: CallbackQuery):
    user_profile = await db.get_user_profile(callback.from_user.id)
    if not user_profile.get('is_vip'):
        text = (
            f"⭐ {hbold('Предварительные напоминания')}\n\n"
            "Эта функция доступна только для **VIP-пользователей**.\n\n"
            "Она позволяет получать напоминания заранее (например, за час до дедлайна), чтобы вы точно ничего не забыли.\n\n"
            "Хотите получить тестовый VIP-доступ?"
        )
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_request_vip_keyboard())
        await callback.answer()
        return

    current_minutes = user_profile.get('pre_reminder_minutes', 60)
    text = (
        f"{hbold('🔔 Пред-напоминания')}\n\n"
        "Выберите, за какое время до основного срока вы хотите получать дополнительное напоминание.\n\n"
        f"Текущая настройка: {hbold(format_pre_reminder_minutes(current_minutes))}"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_pre_reminder_keyboard()
    )
    await callback.answer()


@router.callback_query(SettingsAction.filter(F.action == "set_pre_rem"))
async def set_pre_reminder_handler(callback: CallbackQuery, callback_data: SettingsAction, state: FSMContext):
    try:
        minutes = int(callback_data.value)
        success = await db.set_user_pre_reminder_minutes(callback.from_user.id, minutes)
        if success:
            await callback.answer(f"✅ Настройка сохранена: {format_pre_reminder_minutes(minutes)}", show_alert=False)
        else:
            await callback.answer("❌ Ошибка при сохранении.", show_alert=True)
    except (ValueError, TypeError):
        await callback.answer("❌ Неверное значение.", show_alert=True)

    await show_main_settings_handler(callback, state)


# --- ХЕНДЛЕР: Обработка заявки на VIP ---

@router.callback_query(SettingsAction.filter(F.action == "request_vip"))
async def request_vip_handler(callback: CallbackQuery, state: FSMContext):
    """Отправляет заявку администратору и уведомляет пользователя."""
    if not ADMIN_TELEGRAM_ID:
        await callback.answer("К сожалению, эта функция временно недоступна.", show_alert=True)
        return

    user = callback.from_user
    username = f"@{user.username}" if user.username else "N/A"

    admin_text = (
        f"‼️ {hbold('Новая заявка на VIP-доступ!')}\n\n"
        f"Пользователь: {hbold(user.full_name)}\n"
        f"Username: {hitalic(username)}\n"
        f"ID: {hcode(user.id)}\n\n"
        f"Чтобы выдать VIP, ответьте на это сообщение командой `/admin` или используйте команду `{hcode(f'/admin {user.id}')}`."
    )

    try:
        await callback.bot.send_message(ADMIN_TELEGRAM_ID, admin_text, parse_mode="HTML")
        await db.log_user_action(user.id, 'request_vip')
        await callback.answer("✅ Ваша заявка отправлена администратору! Он рассмотрит ее в ближайшее время.",
                              show_alert=True)

        await show_main_settings_handler(callback, state)

    except Exception as e:
        logger.error(f"Не удалось отправить заявку на VIP от {user.id} администратору {ADMIN_TELEGRAM_ID}: {e}")
        await callback.answer("❌ Произошла ошибка при отправке заявки. Пожалуйста, попробуйте позже.", show_alert=True)


# --- НОВЫЙ ХЕНДЛЕР ДЛЯ ПРИВЯЗКИ АЛИСЫ ---
@router.callback_query(SettingsAction.filter(F.action == "link_alice"))
async def link_alice_handler(callback: CallbackQuery, state: FSMContext):
    """Генерирует код для привязки аккаунта к Яндекс.Алисе по кнопке."""
    telegram_id = callback.from_user.id

    user_profile = await db.get_user_profile(telegram_id)
    if user_profile and user_profile.get('alice_user_id'):
        await callback.answer("Ваш аккаунт уже привязан.", show_alert=True)
        await show_main_settings_handler(callback, state)
        return

    code = await get_link_code_for_user(telegram_id)

    response_text = (
        f"🗝️ {hbold('Привязка к Яндекс.Алисе')}\n\n"
        f"Чтобы я могла сохранять заметки из Алисы, скажите ей следующую фразу:\n\n"
        f"🗣️ {hitalic('Алиса, попроси VoiceNote активировать код')} {hcode(code)}\n\n"
        f"Код действителен в течение 10 минут. Не передавайте его никому."
    )

    await callback.message.answer(response_text, parse_mode="HTML")
    await callback.answer("Код активации отправлен вам в чат.", show_alert=True)