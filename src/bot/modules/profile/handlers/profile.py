# src/bot/modules/profile/handlers/profile.py
import logging
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hcode, hbold, hitalic

from .....core import config
from .....database import user_repo, note_repo, birthday_repo
from .....services.tz_utils import format_datetime_for_user
from ..keyboards import get_profile_actions_keyboard
from ...notes.handlers import shopping_list

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "user_profile")
async def user_profile_display_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Отображает главный экран профиля пользователя со статистикой и кнопками действий.
    """
    await state.clear()
    telegram_id = callback_query.from_user.id
    user_profile_data = await user_repo.get_user_profile(telegram_id)

    if not user_profile_data:
        await callback_query.answer("Профиль не найден. Пожалуйста, нажмите /start.", show_alert=True)
        return

    active_notes_count = await note_repo.count_active_notes_for_user(telegram_id)
    birthdays_count = await birthday_repo.count_birthdays_for_user(telegram_id)
    active_shopping_list = await note_repo.get_active_shopping_list(telegram_id)

    user_timezone = user_profile_data.get('timezone', 'UTC')
    reg_date_local_str = format_datetime_for_user(user_profile_data['created_at'], user_timezone)
    is_vip = user_profile_data.get('is_vip', False)
    has_active_shopping_list = active_shopping_list is not None

    profile_header = f"👤 {hbold('Ваш профиль')}\n\n"

    user_info_parts = [f"▪️ {hbold('ID')}: {hcode(user_profile_data['telegram_id'])}"]
    if user_profile_data.get('username'):
        user_info_parts.append(f"▪️ {hbold('Username')}: @{hitalic(user_profile_data['username'])}")
    user_info_block = "\n".join(user_info_parts)

    notes_limit_str = "Безлимитно" if is_vip else f"{config.MAX_NOTES_MVP}"
    stt_limit_str = "Безлимитно" if is_vip else f"{config.MAX_DAILY_STT_RECOGNITIONS_MVP}"
    birthdays_limit_str = "Безлимитно" if is_vip else f"{config.MAX_NOTES_MVP}"

    stats_info_parts = [
        f"Активные заметки: {hbold(active_notes_count)} / {notes_limit_str}",
        f"Дни рождения: {hbold(birthdays_count)} / {birthdays_limit_str}",
        f"Распознавания сегодня: {hbold(user_profile_data.get('daily_stt_recognitions_count', 0))} / {stt_limit_str}"
    ]
    stats_block = f"📊 {hbold('Статистика')}:\n" + "\n".join(stats_info_parts)

    subscription_status = f"👑 VIP" if is_vip else "Free"
    settings_info_parts = [
        f"Статус: {hitalic(subscription_status)}",
        f"Зарегистрирован: {hitalic(reg_date_local_str)}"
    ]
    settings_block = f"⚙️ {hbold('Данные')}:\n" + "\n".join(settings_info_parts)

    response_text = "\n\n".join([profile_header, user_info_block, stats_block, settings_block])

    keyboard = get_profile_actions_keyboard(has_active_shopping_list=has_active_shopping_list)

    try:
        await callback_query.message.edit_text(response_text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение профиля, отправляю новое: {e}")
        await callback_query.message.answer(response_text, parse_mode="HTML", reply_markup=keyboard)

    await callback_query.answer()


@router.callback_query(F.data == "show_active_shopping_list")
async def show_active_shopping_list_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    active_list = await note_repo.get_active_shopping_list(user_id)
    if not active_list:
        await callback.answer("У вас нет активного списка покупок.", show_alert=True)
        return

    await shopping_list.render_shopping_list(callback, active_list['note_id'], user_id)
    await callback.answer()


@router.callback_query(F.data == "share_active_shopping_list")
async def share_shopping_list_handler(callback: types.CallbackQuery, state: FSMContext):
    """
    Генерирует и отправляет пользователю ссылку для шаринга активного списка покупок.
    """
    user_id = callback.from_user.id
    active_list = await note_repo.get_active_shopping_list(user_id)
    if not active_list:
        await callback.answer("У вас нет активного списка покупок, чтобы поделиться.", show_alert=True)
        return

    note_id = active_list['note_id']
    token = await note_repo.create_share_token(note_id, user_id)
    if not token:
        await callback.answer("❌ Не удалось создать ссылку. Попробуйте позже.", show_alert=True)
        return

    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username
    share_link = f"https://t.me/{bot_username}?start=share_{token}"

    text = (
        f"🤝 {hbold('Ссылка для шаринга списка покупок')}\n\n"
        "Отправьте эту ссылку человеку, с которым хотите вести совместный список покупок.\n\n"
        f"🔗 {hbold('Ваша ссылка:')}\n"
        f"{hcode(share_link)}\n\n"
        f"{hitalic('Ссылка действительна 48 часов и может быть использована только один раз.')}"
    )

    back_button = types.InlineKeyboardButton(
        text="⬅️ Назад в профиль",
        callback_data="user_profile"
    )
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[back_button]])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)
    await callback.answer()