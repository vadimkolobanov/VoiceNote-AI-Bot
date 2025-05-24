# handlers/profile.py
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hcode, hbold, hitalic

from config import MAX_NOTES_MVP
import database_setup as db
from inline_keyboards import get_main_menu_keyboard  # Используем get_main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "user_profile")
async def user_profile_display_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """Отображает профиль пользователя."""
    await state.clear()  # Сбрасываем состояние при переходе в профиль
    telegram_id = callback_query.from_user.id
    user_profile_data = await db.get_user_profile(telegram_id)

    if not user_profile_data:
        await callback_query.answer("Профиль не найден. Пожалуйста, нажмите /start.", show_alert=True)
        # Можно отредактировать сообщение или отправить новое с главной клавиатурой
        try:
            await callback_query.message.edit_text(
                "Произошла ошибка с вашим профилем. Пожалуйста, нажмите /start.",
                reply_markup=get_main_menu_keyboard()
            )
        except:  # Если не удалось отредактировать
            await callback_query.message.answer(
                "Произошла ошибка с вашим профилем. Пожалуйста, нажмите /start.",
                reply_markup=get_main_menu_keyboard()
            )
        return

    active_notes_count = await db.count_active_notes_for_user(telegram_id)  # Используем новую функцию

    profile_info_parts = [f"{hbold('👤 Ваш профиль:')}"]
    profile_info_parts.append(f"Telegram ID: {hcode(user_profile_data['telegram_id'])}")
    if user_profile_data.get('username'):
        profile_info_parts.append(f"Username: @{hitalic(user_profile_data['username'])}")
    if user_profile_data.get('first_name'):
        profile_info_parts.append(f"Имя: {hitalic(user_profile_data['first_name'])}")

    # Отображаем дату регистрации в UTC
    reg_date_utc = user_profile_data['created_at']
    profile_info_parts.append(f"Зарегистрирован: {reg_date_utc.strftime('%d.%m.%Y %H:%M UTC')}")

    subscription_status_text = "Бесплатная (MVP)"  # Заглушка
    profile_info_parts.append(f"Статус подписки: {hitalic(subscription_status_text)}")
    profile_info_parts.append(f"Сохраненных заметок: {hbold(active_notes_count)} из {MAX_NOTES_MVP} (MVP лимит)")

    response_text = "\n".join(profile_info_parts)

    await callback_query.answer()  # Отвечаем на callback
    # Редактируем текущее сообщение или отправляем новое
    try:
        await callback_query.message.edit_text(
            response_text,
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception:
        await callback_query.message.answer(
            response_text,
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )