# src/bot/modules/profile/handlers/settings.py
import logging
from datetime import time, datetime

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.markdown import hbold, hcode, hitalic

from .....core.config import ADMIN_TELEGRAM_ID
from .....database import user_repo
from .....services.tz_utils import ALL_PYTZ_TIMEZONES
from .....web.routes import get_link_code_for_user
from ....common_utils.callbacks import SettingsAction, TimezoneAction
from ....common_utils.states import ProfileSettingsStates
from ..keyboards import (
    get_settings_menu_keyboard,
    get_timezone_selection_keyboard,
    get_reminder_time_keyboard,
    get_pre_reminder_keyboard,
    get_request_vip_keyboard,
    get_digest_time_keyboard,
    get_city_actions_keyboard,
)
from ...common.keyboards import get_main_menu_keyboard

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


async def get_settings_text_and_keyboard(telegram_id: int):
    """Формирует текст и клавиатуру для главного меню настроек."""
    user_profile = await user_repo.get_user_profile(telegram_id)
    if not user_profile:
        return None, None

    is_vip = user_profile.get('is_vip', False)
    current_rem_time_str = user_profile.get('default_reminder_time', time(9, 0)).strftime('%H:%M')
    current_digest_time_str = user_profile.get('daily_digest_time', time(9, 0)).strftime('%H:%M')
    city_name = user_profile.get('city_name')

    text_parts = [
        f"{hbold('⚙️ Ваши настройки')}\n",
        "Здесь вы можете персонализировать работу бота.\n",
        f"▪️ Текущий часовой пояс: {hcode(user_profile.get('timezone', 'UTC'))}",
        f"▪️ Город для погоды: {hcode(city_name or 'Не указан')}",
    ]
    if is_vip:
        digest_status = "Включена" if user_profile.get('daily_digest_enabled', True) else "Выключена"
        text_parts.extend([
            f"▪️ Время напоминаний по умолч.: {hcode(current_rem_time_str)} (⭐ VIP)",
            f"▪️ Предв. напоминания: {hbold(format_pre_reminder_minutes(user_profile.get('pre_reminder_minutes', 60)))} (⭐ VIP)",
            f"▪️ Утренняя сводка: {hbold(digest_status)} в {hcode(current_digest_time_str)} (⭐ VIP)",
        ])

    text = "\n".join(text_parts)
    keyboard = get_settings_menu_keyboard(
        is_vip=is_vip,
        daily_digest_enabled=user_profile.get('daily_digest_enabled', True),
        is_alice_linked=bool(user_profile.get('alice_user_id'))
    )
    return text, keyboard


@router.callback_query(SettingsAction.filter(F.action == "go_to_main"))
async def show_main_settings_callback(callback: CallbackQuery, state: FSMContext):
    """Отображает главный экран настроек по колбэку."""
    await show_main_settings_handler(callback, state)


async def show_main_settings_handler(event: Message | CallbackQuery, state: FSMContext):
    """
    Универсальная функция для отображения главного экрана настроек.
    Может быть вызвана как из Message, так и из CallbackQuery.
    """
    await state.clear()
    user_id = event.from_user.id
    message = event if isinstance(event, Message) else event.message

    text, keyboard = await get_settings_text_and_keyboard(user_id)
    if not text:
        if isinstance(event, CallbackQuery):
            await event.answer("Профиль не найден.", show_alert=True)
        else:
            await message.answer("Профиль не найден.")
        return

    if isinstance(event, CallbackQuery):
        try:
            await message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        except TelegramBadRequest:
            # Если сообщение не изменилось, просто игнорируем ошибку
            pass
        await event.answer()
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(SettingsAction.filter(F.action == "get_free_vip"))
async def get_vip_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие кнопки 'Получить VIP' и выдает статус."""
    user_id = callback.from_user.id
    user_profile = await user_repo.get_user_profile(user_id)
    if user_profile and user_profile.get('is_vip'):
        await callback.answer("У вас уже есть VIP-статус!", show_alert=True)
        return

    success = await user_repo.set_user_vip_status(user_id, True)
    if not success:
        await callback.answer("❌ Произошла ошибка. Попробуйте, пожалуйста, позже.", show_alert=True)
        return

    await user_repo.log_user_action(user_id, 'get_free_vip_button')
    user_notification_text = (
        f"🎉 {hbold('Поздравляем!')}\n\n"
        f"Вам присвоен статус 👑 {hbold('VIP')}!\n\n"
        "Теперь вам доступны все эксклюзивные возможности бота. "
        "Изучите их в разделе `⚙️ Настройки`."
    )
    await callback.answer("🎉 Поздравляем! Вам присвоен VIP-статус!", show_alert=True)
    await callback.bot.send_message(user_id, user_notification_text)

    main_menu_kb = await get_main_menu_keyboard(is_vip=True)
    await callback.message.edit_text(
        "🏠 Вы в главном меню.",
        reply_markup=main_menu_kb
    )


@router.callback_query(SettingsAction.filter(F.action == "toggle_digest"))
async def toggle_daily_digest_handler(callback: CallbackQuery, state: FSMContext):
    """Переключает статус утренней сводки."""
    user_profile = await user_repo.get_user_profile(callback.from_user.id)
    if not user_profile.get('is_vip'):
        await callback.answer("⭐ Эта функция доступна только для VIP-пользователей.", show_alert=True)
        return

    current_status = user_profile.get('daily_digest_enabled', True)
    new_status = not current_status
    await user_repo.set_user_daily_digest_status(callback.from_user.id, new_status)

    status_text = "включена" if new_status else "выключена"
    await callback.answer(f"✅ Утренняя сводка {status_text}", show_alert=False)
    await show_main_settings_handler(callback, state)


@router.callback_query(SettingsAction.filter(F.action == "go_to_digest_time"))
async def show_digest_time_handler(callback: CallbackQuery):
    """Показывает меню выбора времени для утренней сводки."""
    user_profile = await user_repo.get_user_profile(callback.from_user.id)
    if not user_profile.get('is_vip'):
        await callback.answer("⭐ Эта функция доступна только для VIP-пользователей.", show_alert=True)
        return

    current_time = user_profile.get('daily_digest_time', time(9, 0)).strftime('%H:%M')
    text = f"{hbold('🕘 Время утренней сводки')}\n\nВыберите, в какое время вы хотите получать ежедневный отчет.\nТекущее время: {hcode(current_time)}"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_digest_time_keyboard())
    await callback.answer()


@router.callback_query(SettingsAction.filter(F.action == "set_digest_time"))
async def set_digest_time_from_button_handler(callback: CallbackQuery, callback_data: SettingsAction,
                                              state: FSMContext):
    """Устанавливает время утренней сводки по нажатию на кнопку."""
    time_str = callback_data.value.replace('-', ':')
    try:
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        success = await user_repo.set_user_daily_digest_time(callback.from_user.id, time_obj)
        if success:
            await callback.answer(f"✅ Время сводки установлено на {time_str}", show_alert=False)
        else:
            await callback.answer("❌ Ошибка при установке времени.", show_alert=True)
    except ValueError:
        await callback.answer("Неверный формат времени.", show_alert=True)
    await show_main_settings_handler(callback, state)


@router.callback_query(SettingsAction.filter(F.action == "go_to_timezone"))
async def show_timezone_selection_handler(callback: CallbackQuery, state: FSMContext):
    """Показывает меню выбора часового пояса."""
    await state.clear()
    text = f"{hbold('🕒 Настройка часового пояса')}\n\nВыберите ваш часовой пояс из списка или введите его вручную."
    await callback.message.edit_text(text, reply_markup=get_timezone_selection_keyboard())
    await callback.answer()


@router.callback_query(TimezoneAction.filter(F.action == 'set'))
async def set_timezone_from_button_handler(callback: CallbackQuery, callback_data: TimezoneAction, state: FSMContext):
    """Устанавливает часовой пояс по нажатию на кнопку."""
    success = await user_repo.set_user_timezone(callback.from_user.id, callback_data.tz_name)
    if success:
        await callback.answer(f"✅ Часовой пояс установлен: {callback_data.tz_name}", show_alert=True)
    else:
        await callback.answer("❌ Ошибка при установке.", show_alert=True)
    await show_main_settings_handler(callback, state)


@router.callback_query(TimezoneAction.filter(F.action == 'manual_input'))
async def manual_timezone_input_handler(callback: CallbackQuery, state: FSMContext):
    """Запрашивает ручной ввод часового пояса."""
    await state.set_state(ProfileSettingsStates.awaiting_timezone)
    text = f"Отправьте название в формате `Continent/City` (например, `Europe/Moscow`).\nДля отмены введите /cancel."
    await callback.message.edit_text(
        f"{callback.message.text}\n\n{text}",
        reply_markup=get_timezone_selection_keyboard()
    )
    await callback.answer("Ожидаю ваш ввод...")


@router.message(ProfileSettingsStates.awaiting_timezone, F.text, ~F.text.startswith('/'))
async def process_manual_timezone_handler(message: types.Message, state: FSMContext):
    """Обрабатывает ручной ввод часового пояса."""
    timezone_name = message.text.strip()
    if timezone_name not in ALL_PYTZ_TIMEZONES:
        await message.reply(f"❌ Часовой пояс {hcode(timezone_name)} не найден. Проверьте написание и попробуйте снова.")
        return

    await user_repo.set_user_timezone(message.from_user.id, timezone_name)
    await state.clear()
    await message.answer(f"✅ Часовой пояс установлен: {timezone_name}")
    await show_main_settings_handler(message, state)


@router.callback_query(SettingsAction.filter(F.action == "go_to_city"))
async def show_city_input_handler(callback: CallbackQuery, state: FSMContext):
    """Показывает меню настройки города."""
    await state.clear()
    user_profile = await user_repo.get_user_profile(callback.from_user.id)
    city_name = user_profile.get('city_name')

    if city_name:
        text = (f"📍 {hbold('Город для прогноза погоды')}\n\n"
                f"Ваш текущий город: {hcode(city_name)}.\n"
                f"Отправьте новое название, чтобы изменить его, или удалите, чтобы отключить прогноз.")
    else:
        text = (f"📍 {hbold('Город для прогноза погоды')}\n\n"
                f"Отправьте название вашего города (например, {hitalic('Москва')}), "
                f"чтобы получать прогноз погоды в утренней сводке.\n\n"
                f"Для отмены введите /cancel.")

    await state.set_state(ProfileSettingsStates.awaiting_city_name)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_city_actions_keyboard(city_is_set=bool(city_name))
    )
    await callback.answer()


@router.callback_query(SettingsAction.filter(F.action == "delete_city"))
async def delete_city_handler(callback: CallbackQuery, state: FSMContext):
    """Удаляет установленный город."""
    await user_repo.set_user_city(callback.from_user.id, None)
    await callback.answer("✅ Город удален. Прогноз погоды отключен.", show_alert=True)
    await show_main_settings_handler(callback, state)


@router.message(ProfileSettingsStates.awaiting_city_name, F.text, ~F.text.startswith('/'))
async def process_city_name_handler(message: types.Message, state: FSMContext):
    """Обрабатывает ввод города и сохраняет его."""
    city_name = message.text.strip()
    await user_repo.set_user_city(message.from_user.id, city_name)
    await message.answer(f"✅ Город для прогноза погоды установлен: {hbold(city_name)}.")
    await show_main_settings_handler(message, state)


@router.callback_query(SettingsAction.filter(F.action == "go_to_reminders"))
async def show_reminder_time_handler(callback: CallbackQuery):
    """Показывает меню выбора времени напоминаний."""
    user_profile = await user_repo.get_user_profile(callback.from_user.id)
    if not user_profile.get('is_vip'):
        text = (
            f"⭐ {hbold('Настройка времени напоминаний')}\n\n"
            "Эта функция доступна только для **VIP-пользователей**.\n\n"
            "Она позволяет боту автоматически устанавливать напоминания на удобное вам время, "
            "даже если вы сказали только дату (например, 'завтра').\n\n"
            "Хотите получить тестовый VIP-доступ?"
        )
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_request_vip_keyboard())
        await callback.answer()
        return

    text = f"{hbold('⏰ Время напоминаний по умолчанию')}\n\nЭто время будет использоваться для напоминаний, у которых в тексте была указана только дата."
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_reminder_time_keyboard())
    await callback.answer()


@router.callback_query(SettingsAction.filter(F.action == "set_rem_time"))
async def set_reminder_time_from_button_handler(callback: CallbackQuery, callback_data: SettingsAction,
                                                state: FSMContext):
    """Устанавливает время напоминаний по нажатию на кнопку."""
    time_str = callback_data.value.replace('-', ':')
    try:
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        success = await user_repo.set_user_default_reminder_time(callback.from_user.id, time_obj)
        if success:
            await callback.answer(f"✅ Время напоминаний установлено на {time_str}", show_alert=False)
        else:
            await callback.answer("❌ Ошибка при установке времени.", show_alert=True)
    except ValueError:
        await callback.answer("Неверный формат времени.", show_alert=True)
    await show_main_settings_handler(callback, state)


@router.callback_query(SettingsAction.filter(F.action == "manual_rem_time"))
async def manual_reminder_time_handler(callback: CallbackQuery, state: FSMContext):
    """Запрашивает ручной ввод времени напоминаний."""
    await state.set_state(ProfileSettingsStates.awaiting_reminder_time)
    text = f"{hbold('⌨️ Ручной ввод времени')}\n\nОтправьте время в формате `ЧЧ:ММ` (например, `09:30`).\nДля отмены введите /cancel."
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_reminder_time_keyboard())
    await callback.answer("Ожидаю ваш ввод...")


@router.message(ProfileSettingsStates.awaiting_reminder_time, F.text, ~F.text.startswith('/'))
async def process_manual_reminder_time_handler(message: types.Message, state: FSMContext):
    """Обрабатывает ручной ввод времени напоминаний."""
    try:
        time_obj = datetime.strptime(message.text.strip(), '%H:%M').time()
        await user_repo.set_user_default_reminder_time(message.from_user.id, time_obj)
        await state.clear()
        await message.answer(f"✅ Время напоминаний установлено на {message.text.strip()}.")
        await show_main_settings_handler(message, state)
    except ValueError:
        await message.reply("❌ Неверный формат времени. Введите в формате `ЧЧ:ММ`, например, `09:30`.")


@router.callback_query(SettingsAction.filter(F.action == "go_to_pre_reminders"))
async def show_pre_reminder_handler(callback: CallbackQuery):
    """Показывает меню выбора времени для пред-напоминаний."""
    user_profile = await user_repo.get_user_profile(callback.from_user.id)
    if not user_profile.get('is_vip'):
        text = (
            f"⭐ {hbold('Предварительные напоминания')}\n\n"
            "Эта функция доступна только для **VIP-пользователей**.\n\n"
            "Хотите получить тестовый VIP-доступ?"
        )
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_request_vip_keyboard())
        await callback.answer()
        return

    current_minutes = user_profile.get('pre_reminder_minutes', 60)
    text = (
        f"{hbold('🔔 Пред-напоминания')}\n\n"
        "Выберите, за какое время до срока получать доп. напоминание.\n\n"
        f"Текущая настройка: {hbold(format_pre_reminder_minutes(current_minutes))}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_pre_reminder_keyboard())
    await callback.answer()


@router.callback_query(SettingsAction.filter(F.action == "set_pre_rem"))
async def set_pre_reminder_handler(callback: CallbackQuery, callback_data: SettingsAction, state: FSMContext):
    """Устанавливает время для пред-напоминаний."""
    try:
        minutes = int(callback_data.value)
        success = await user_repo.set_user_pre_reminder_minutes(callback.from_user.id, minutes)
        if success:
            await callback.answer(f"✅ Настройка сохранена: {format_pre_reminder_minutes(minutes)}", show_alert=False)
        else:
            await callback.answer("❌ Ошибка при сохранении.", show_alert=True)
    except (ValueError, TypeError):
        await callback.answer("❌ Неверное значение.", show_alert=True)
    await show_main_settings_handler(callback, state)


@router.callback_query(SettingsAction.filter(F.action == "request_vip"))
async def request_vip_handler(callback: CallbackQuery, state: FSMContext):
    """Отправляет заявку администратору на получение VIP-статуса."""
    if not ADMIN_TELEGRAM_ID:
        await callback.answer("К сожалению, эта функция временно недоступна.", show_alert=True)
        return

    user = callback.from_user
    admin_text = (
        f"‼️ {hbold('Новая заявка на VIP-доступ!')}\n\n"
        f"Пользователь: {hbold(user.full_name)} (@{user.username if user.username else 'N/A'})\n"
        f"ID: {hcode(user.id)}\n\n"
        f"Для выдачи VIP используйте команду `/admin {user.id}`."
    )
    try:
        await callback.bot.send_message(ADMIN_TELEGRAM_ID, admin_text, parse_mode="HTML")
        await user_repo.log_user_action(user.id, 'request_vip')
        await callback.answer("✅ Ваша заявка отправлена администратору!", show_alert=True)
        await show_main_settings_handler(callback, state)
    except Exception as e:
        logger.error(f"Не удалось отправить заявку на VIP от {user.id}: {e}")
        await callback.answer("❌ Ошибка при отправке заявки.", show_alert=True)


@router.callback_query(SettingsAction.filter(F.action == "link_alice"))
async def link_alice_handler(callback: CallbackQuery, state: FSMContext):
    """Генерирует код для привязки аккаунта к Яндекс.Алисе."""
    telegram_id = callback.from_user.id
    user_profile = await user_repo.get_user_profile(telegram_id)
    if user_profile and user_profile.get('alice_user_id'):
        await callback.answer("Ваш аккаунт уже привязан.", show_alert=True)
        return

    code = await get_link_code_for_user(telegram_id)
    response_text = (
        f"🗝️ {hbold('Привязка к Яндекс.Алисе')}\n\n"
        f"Чтобы я могла сохранять заметки из Алисы, скажите ей:\n\n"
        f"🗣️ {hitalic('Алиса, попроси VoiceNote активировать код')} {hcode(code)}\n\n"
        f"Код действителен 10 минут. Не передавайте его никому."
    )
    await callback.message.answer(response_text, parse_mode="HTML")
    await callback.answer("Код активации отправлен вам в чат.", show_alert=True)