# services/common.py
import logging
from datetime import date

from aiogram import types
import database_setup as db

logger = logging.getLogger(__name__)


async def get_or_create_user(tg_user: types.User) -> dict | None:
    """
    Проверяет наличие пользователя в БД. Если нет - добавляет.
    Если есть - обновляет его данные (username, first_name и т.д.).
    Возвращает запись о пользователе из БД.
    """
    user_profile_before_upsert = await db.get_user_profile(tg_user.id)

    user_record = await db.add_or_update_user(
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
        language_code=tg_user.language_code
    )

    if not user_profile_before_upsert and user_record:
        logger.info(f"Новый пользователь зарегистрирован: {tg_user.id} (@{tg_user.username or 'N/A'})")
    elif user_record:
        pass

    return user_record


async def check_and_update_stt_limit(telegram_id: int) -> tuple[bool, int]:
    """
    Проверяет и обновляет дневной лимит STT для пользователя.
    VIP-пользователи игнорируют лимит.
    Возвращает: (can_recognize: bool, remaining_recognitions: int)
    """
    from config import MAX_DAILY_STT_RECOGNITIONS_MVP

    user_profile = await db.get_user_profile(telegram_id)
    if not user_profile:
        logger.error(f"Профиль пользователя {telegram_id} не найден при проверке лимита STT.")
        return False, 0

    # <--- НОВАЯ ЛОГИКА --->
    if user_profile.get('is_vip', False):
        logger.info(f"Пользователь {telegram_id} (VIP) проигнорировал проверку лимита STT.")
        return True, 999  # Условное большое число для VIP

    today = date.today()
    last_reset_date_from_db = user_profile.get('last_stt_reset_date')
    current_recognitions = user_profile.get('daily_stt_recognitions_count', 0)

    if last_reset_date_from_db != today:
        current_recognitions = 0
        await db.update_user_stt_counters(telegram_id, current_recognitions, today)
        logger.info(f"Сброшен дневной лимит STT для пользователя {telegram_id}.")

    if current_recognitions >= MAX_DAILY_STT_RECOGNITIONS_MVP:
        remaining = MAX_DAILY_STT_RECOGNITIONS_MVP - current_recognitions
        return False, max(0, remaining)

    remaining = MAX_DAILY_STT_RECOGNITIONS_MVP - current_recognitions
    return True, remaining


async def increment_stt_recognition_count(telegram_id: int):
    """Увеличивает счетчик STT распознаваний для пользователя, если он не VIP."""
    user_profile = await db.get_user_profile(telegram_id)
    if not user_profile:
        logger.error(f"Профиль {telegram_id} не найден при инкременте счетчика STT.")
        return

    # <--- НОВАЯ ЛОГИКА --->
    if user_profile.get('is_vip', False):
        logger.info(f"Счетчик STT для пользователя {telegram_id} (VIP) не инкрементирован.")
        return # Не увеличиваем счетчик для VIP

    today = date.today()
    current_recognitions = user_profile.get('daily_stt_recognitions_count', 0)
    last_reset_date_from_db = user_profile.get('last_stt_reset_date')

    if last_reset_date_from_db != today:
        new_count = 1
    else:
        new_count = current_recognitions + 1

    await db.update_user_stt_counters(telegram_id, new_count, today)
    logger.info(f"Инкрементирован счетчик STT для {telegram_id} до {new_count}.")