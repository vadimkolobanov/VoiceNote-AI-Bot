# services/common.py
import logging
from aiogram import types
import database_setup as db  # Импортируем модуль БД

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
        # logger.debug(f"Данные пользователя {tg_user.id} обновлены.") # Можно логировать, если нужно
        pass

    return user_record