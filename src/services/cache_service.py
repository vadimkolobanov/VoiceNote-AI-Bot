# src/services/cache_service.py
import json
import logging
from redis.asyncio import Redis
from aiogram.fsm.storage.redis import RedisStorage

from src.core.config import REDIS_URL

logger = logging.getLogger(__name__)

# --- Константы ---
USER_PROFILE_CACHE_KEY = "user_profile:{user_id}"
ALL_ACHIEVEMENTS_CACHE_KEY = "achievements:all"
CACHE_TTL_SECONDS = 300  # 5 минут
ACHIEVEMENTS_CACHE_TTL_SECONDS = 3600  # 1 час, т.к. меняются редко

# --- Инициализация ---
_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    """Возвращает экземпляр клиента Redis."""
    global _redis_client
    if _redis_client is None:
        # Используем парсер из aiogram, чтобы не дублировать логику подключения
        storage = RedisStorage.from_url(REDIS_URL)
        _redis_client = storage.redis
    return _redis_client


# --- Функции для работы с кэшем профиля ---

async def get_user_profile_from_cache(user_id: int) -> dict | None:
    """
    Пытается получить профиль пользователя из кэша Redis.
    """
    redis = get_redis_client()
    key = USER_PROFILE_CACHE_KEY.format(user_id=user_id)
    cached_data = await redis.get(key)

    if cached_data:
        try:
            profile = json.loads(cached_data)
            logger.debug(f"Кэш-хит для профиля пользователя {user_id}.")
            return profile
        except json.JSONDecodeError:
            logger.warning(f"Ошибка декодирования JSON из кэша для пользователя {user_id}.")
            return None

    logger.debug(f"Кэш-промах для профиля пользователя {user_id}.")
    return None


async def set_user_profile_to_cache(user_id: int, profile_data: dict):
    """
    Сохраняет профиль пользователя в кэш Redis.
    """
    # Конвертируем datetime и time в строки, т.к. JSON их не поддерживает напрямую
    for key, value in profile_data.items():
        if hasattr(value, 'isoformat'):
            profile_data[key] = value.isoformat()

    redis = get_redis_client()
    key = USER_PROFILE_CACHE_KEY.format(user_id=user_id)
    try:
        await redis.set(key, json.dumps(profile_data), ex=CACHE_TTL_SECONDS)
        logger.debug(f"Профиль пользователя {user_id} сохранен в кэш.")
    except Exception as e:
        logger.error(f"Не удалось сохранить профиль {user_id} в кэш: {e}")


async def delete_user_profile_from_cache(user_id: int):
    """
    Удаляет (инвалидирует) кэш профиля пользователя.
    """
    redis = get_redis_client()
    key = USER_PROFILE_CACHE_KEY.format(user_id=user_id)
    await redis.delete(key)
    logger.info(f"Кэш для профиля пользователя {user_id} инвалидирован.")


# --- Функции для работы с кэшем достижений ---

async def get_all_achievements_from_cache() -> list[dict] | None:
    """Пытается получить список всех достижений из кэша."""
    redis = get_redis_client()
    cached_data = await redis.get(ALL_ACHIEVEMENTS_CACHE_KEY)
    if cached_data:
        try:
            achievements = json.loads(cached_data)
            logger.debug("Кэш-хит для списка всех достижений.")
            return achievements
        except json.JSONDecodeError:
            logger.warning("Ошибка декодирования JSON из кэша для списка достижений.")
            return None
    logger.debug("Кэш-промах для списка всех достижений.")
    return None


async def set_all_achievements_to_cache(achievements_data: list[dict]):
    """Сохраняет список всех достижений в кэш."""
    redis = get_redis_client()
    try:
        await redis.set(ALL_ACHIEVEMENTS_CACHE_KEY, json.dumps(achievements_data), ex=ACHIEVEMENTS_CACHE_TTL_SECONDS)
        logger.debug("Список всех достижений сохранен в кэш.")
    except Exception as e:
        logger.error(f"Не удалось сохранить список достижений в кэш: {e}")