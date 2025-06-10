# handlers/timezone_selector.py
import logging

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hbold, hcode

import database_setup as db
from inline_keyboards import get_timezone_selection_keyboard, TimezoneAction
from services.tz_utils import ALL_PYTZ_TIMEZONES
from states import ProfileSettingsStates
# Импортируем хендлер профиля, чтобы "перезапустить" его после установки таймзоны
from handlers.profile import user_profile_display_handler

logger = logging.getLogger(__name__)
router = Router()

# Этот хендлер будет вызываться из профиля
@router.callback_query(F.data == "set_timezone")
async def show_timezone_selection_handler(callback_query: CallbackQuery, state: FSMContext):
    """Отображает экран выбора часового пояса."""
    await state.clear() # На всякий случай очищаем состояние
    text = (
        f"{hbold('⚙️ Настройка часового пояса')}\n\n"
        "Ваш текущий часовой пояс используется для корректного отображения всех дат и времени в боте.\n\n"
        "Пожалуйста, выберите ваш часовой пояс из списка или введите его вручную."
    )
    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_timezone_selection_keyboard()
    )
    await callback_query.answer()


@router.callback_query(TimezoneAction.filter(F.action == 'set'))
async def set_timezone_from_button_handler(callback_query: CallbackQuery, callback_data: TimezoneAction, state: FSMContext):
    """Обрабатывает установку часового пояса по нажатию на кнопку."""
    timezone_name = callback_data.tz_name
    telegram_id = callback_query.from_user.id

    success = await db.set_user_timezone(telegram_id, timezone_name)
    if success:
        await callback_query.answer(f"✅ Часовой пояс установлен: {timezone_name}", show_alert=True)
    else:
        await callback_query.answer("❌ Произошла ошибка при установке часового пояса.", show_alert=True)

    # После успешной установки, снова показываем обновленный профиль
    await user_profile_display_handler(callback_query, state)


@router.callback_query(TimezoneAction.filter(F.action == 'manual_input'))
async def manual_timezone_input_handler(callback_query: CallbackQuery, state: FSMContext):
    """Запрашивает ручной ввод часового пояса."""
    await state.set_state(ProfileSettingsStates.awaiting_timezone)
    text = (
        f"{hbold('⌨️ Ручной ввод часового пояса')}\n\n"
        "Пожалуйста, отправьте название вашего часового пояса в формате `Continent/City`, например, `Europe/Paris` или `Asia/Tashkent`.\n\n"
        f"Для отмены вернитесь в профиль, нажав на кнопку в предыдущем сообщении или отправьте /cancel."
    )
    # Редактируем сообщение, но клавиатуру оставляем, чтобы можно было вернуться
    await callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=get_timezone_selection_keyboard())
    await callback_query.answer("Ожидаю ваш ввод...")


@router.message(ProfileSettingsStates.awaiting_timezone, F.text)
async def process_manual_timezone_handler(message: types.Message, state: FSMContext):
    """Обрабатывает введенный вручную часовой пояс."""
    timezone_name = message.text.strip()

    if timezone_name not in ALL_PYTZ_TIMEZONES:
        await message.reply(
            f"❌ Часовой пояс {hcode(timezone_name)} не найден.\n"
            "Пожалуйста, проверьте написание (например, `Europe/Berlin`) и попробуйте снова, или выберите из списка."
        )
        return

    telegram_id = message.from_user.id
    success = await db.set_user_timezone(telegram_id, timezone_name)
    await state.clear()

    if success:
        await message.answer(f"✅ Часовой пояс установлен: {timezone_name}")
    else:
        await message.answer("❌ Произошла ошибка при установке часового пояса.")

    # Создаем "фейковый" callback_query, чтобы переиспользовать хендлер профиля
    # Это распространенный прием, чтобы не дублировать код
    fake_callback_query = types.CallbackQuery(
        id="fake_callback",
        from_user=message.from_user,
        chat_instance="fake_chat_instance",
        message=message, # Передаем текущее сообщение
        data="user_profile"
    )
    # После успешной установки, снова показываем обновленный профиль
    await user_profile_display_handler(fake_callback_query, state)