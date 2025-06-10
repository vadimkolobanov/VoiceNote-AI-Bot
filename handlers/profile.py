# handlers/profile.py
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hcode, hbold, hitalic

from config import MAX_NOTES_MVP, MAX_DAILY_STT_RECOGNITIONS_MVP
import database_setup as db
from inline_keyboards import get_profile_actions_keyboard
from services.tz_utils import format_datetime_for_user

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "user_profile")
async def user_profile_display_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """Отображает обновленный и красивый профиль пользователя."""
    await state.clear()
    telegram_id = callback_query.from_user.id
    user_profile_data = await db.get_user_profile(telegram_id)

    if not user_profile_data:
        await callback_query.answer("Профиль не найден. Пожалуйста, нажмите /start.", show_alert=True)
        return

    # Получаем все нужные данные
    active_notes_count = await db.count_active_notes_for_user(telegram_id)
    user_timezone = user_profile_data.get('timezone', 'UTC')
    reg_date_utc = user_profile_data['created_at']
    reg_date_local_str = format_datetime_for_user(reg_date_utc, user_timezone)
    is_vip = user_profile_data.get('is_vip', False)  # <--- Получаем VIP-статус

    # --- Формируем красивый текст профиля ---
    profile_header = f"👤 {hbold('Ваш профиль')}\n\n"

    # Блок "О вас"
    user_info_parts = [
        f"▪️ {hbold('ID')}: {hcode(user_profile_data['telegram_id'])}",
    ]
    if user_profile_data.get('username'):
        user_info_parts.append(f"▪️ {hbold('Username')}: @{hitalic(user_profile_data['username'])}")
    if user_profile_data.get('first_name'):
        user_info_parts.append(f"▪️ {hbold('Имя')}: {hitalic(user_profile_data['first_name'])}")
    user_info_block = "\n".join(user_info_parts)

    # Блок "Статистика и лимиты"
    # <--- НОВАЯ ЛОГИКА ОТОБРАЖЕНИЯ ЛИМИТОВ --->
    notes_limit_str = "Безлимитно" if is_vip else f"{MAX_NOTES_MVP}"
    stt_limit_str = "Безлимитно" if is_vip else f"{MAX_DAILY_STT_RECOGNITIONS_MVP}"

    stats_info_parts = [
        f"Активные заметки: {hbold(active_notes_count)} / {notes_limit_str}",
        f"Распознавания сегодня: {hbold(user_profile_data.get('daily_stt_recognitions_count', 0))} / {stt_limit_str}"
    ]
    stats_block = f"📊 {hbold('Статистика')}:\n" + "\n".join(stats_info_parts)

    # Блок "Настройки и подписка"
    subscription_status = f"👑 VIP" if is_vip else "Free (MVP)"
    settings_info_parts = [
        f"Статус: {hitalic(subscription_status)}",
        f"Часовой пояс: {hcode(user_timezone)}",
        f"Зарегистрирован: {hitalic(reg_date_local_str)}"
    ]
    settings_block = f"⚙️ {hbold('Настройки')}:\n" + "\n".join(settings_info_parts)

    response_text = "\n\n".join([profile_header, user_info_block, stats_block, settings_block])

    await callback_query.answer()
    try:
        await callback_query.message.edit_text(
            response_text,
            parse_mode="HTML",
            reply_markup=get_profile_actions_keyboard()
        )
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение профиля, отправляю новое: {e}")
        await callback_query.message.answer(
            response_text,
            parse_mode="HTML",
            reply_markup=get_profile_actions_keyboard()
        )