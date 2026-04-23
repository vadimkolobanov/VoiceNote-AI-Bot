# src/database/user_repo.py
import json
import logging
from datetime import datetime, timezone, date, time
from aiogram import types, Bot
from aiogram.utils.markdown import hbold

from .connection import get_db_pool
from ..services import cache_service
# ACHIEVEMENTS_BY_CODE импортируется лениво внутри grant_achievement()
# чтобы избежать циклического импорта с gamification_service
from ..web.routes import bot_instance

logger = logging.getLogger(__name__)


# Устаревшие алиасы IANA tzdb, удалённые в PostgreSQL 17+. Приложение уже
# не должно их создавать (миграция в connection.py нормализует users.timezone
# при старте), но на случай, если где-то осталось в памяти/кэше/external source
# — маппим к каноническим именам при чтении.
_DEPRECATED_TZ_ALIASES = {
    'Europe/Kiev': 'Europe/Kyiv',
    'Asia/Calcutta': 'Asia/Kolkata',
    'Asia/Saigon': 'Asia/Ho_Chi_Minh',
    'Asia/Rangoon': 'Asia/Yangon',
    'America/Godthab': 'America/Nuuk',
}


def normalize_timezone(tz: str | None) -> str:
    """Канонизирует IANA tzdb alias. None / пусто → 'UTC'."""
    if not tz:
        return 'UTC'
    return _DEPRECATED_TZ_ALIASES.get(tz, tz)


def get_level_for_xp(xp: int) -> int:
    """Вычисляет уровень на основе накопленного опыта."""
    return int((xp / 100) ** 0.5) + 1


def get_xp_for_level(level: int) -> int:
    """Вычисляет необходимое количество опыта для достижения уровня."""
    if level <= 1:
        return 0
    return int(((level - 1) ** 2) * 100)


async def add_or_update_user(telegram_id: int, username: str = None, first_name: str = None, last_name: str = None,
                             language_code: str = None) -> dict | None:
    """
    Добавляет нового пользователя или обновляет данные существующего.
    Автоматически устанавливает часовой пояс на основе языка, если он не установлен.
    Возвращает полную запись о пользователе из БД.
    """
    from ..services.tz_utils import guess_timezone_from_language
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)
        
        # Проверяем, существует ли пользователь
        existing_user = await conn.fetchrow("SELECT timezone FROM users WHERE telegram_id = $1", telegram_id)
        is_new_user = existing_user is None
        
        # Для новых пользователей пытаемся определить часовой пояс по языку
        auto_timezone = None
        if is_new_user and language_code:
            auto_timezone = guess_timezone_from_language(language_code)
            if auto_timezone != 'UTC':
                logger.info(f"Автоматически определен часовой пояс {auto_timezone} для нового пользователя {telegram_id} на основе языка {language_code}")
        
        # Если это новый пользователь и мы определили часовой пояс, устанавливаем его
        if is_new_user and auto_timezone:
            query = """
                    INSERT INTO users (telegram_id, username, first_name, last_name, language_code, timezone, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $7) ON CONFLICT (telegram_id) DO
                    UPDATE SET
                        username = EXCLUDED.username, first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name, language_code = EXCLUDED.language_code,
                        updated_at = $7
                        RETURNING *;
                    """
            user_record = await conn.fetchrow(query, telegram_id, username, first_name, last_name, language_code, auto_timezone, now)
        else:
            query = """
                    INSERT INTO users (telegram_id, username, first_name, last_name, language_code, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $6) ON CONFLICT (telegram_id) DO
                    UPDATE SET
                        username = EXCLUDED.username, first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name, language_code = EXCLUDED.language_code,
                        updated_at = $6
                        RETURNING *;
                    """
            user_record = await conn.fetchrow(query, telegram_id, username, first_name, last_name, language_code, now)

        await cache_service.delete_user_profile_from_cache(telegram_id)

        return dict(user_record) if user_record else None


async def get_or_create_user(tg_user: types.User) -> dict | None:
    """
    Проверяет наличие пользователя в БД. Если нет - добавляет.
    Если есть - обновляет его данные. Возвращает запись о пользователе из БД.
    """
    user_profile_before_upsert = await get_user_profile(tg_user.id)

    user_record = await add_or_update_user(
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
        language_code=tg_user.language_code
    )

    if not user_profile_before_upsert and user_record:
        logger.info(f"Новый пользователь зарегистрирован: {tg_user.id} (@{tg_user.username or 'N/A'})")
        await log_user_action(tg_user.id, 'user_registered')

    return user_record


async def get_user_profile(telegram_id: int) -> dict | None:
    """Возвращает профиль пользователя по его telegram_id, используя кэш."""
    cached_profile = await cache_service.get_user_profile_from_cache(telegram_id)
    if cached_profile:
        for key in ['created_at', 'updated_at', 'last_stt_reset_date', 'alice_code_expires_at']:
            if key in cached_profile and isinstance(cached_profile[key], str):
                try:
                    cached_profile[key] = datetime.fromisoformat(cached_profile[key])
                except (ValueError, TypeError):
                    pass
        if 'default_reminder_time' in cached_profile and isinstance(cached_profile['default_reminder_time'], str):
            cached_profile['default_reminder_time'] = time.fromisoformat(cached_profile['default_reminder_time'])
        if 'daily_digest_time' in cached_profile and isinstance(cached_profile['daily_digest_time'], str):
            cached_profile['daily_digest_time'] = time.fromisoformat(cached_profile['daily_digest_time'])
        if 'viewed_guides' in cached_profile and isinstance(cached_profile['viewed_guides'], str):
             cached_profile['viewed_guides'] = json.loads(cached_profile['viewed_guides'])
        return cached_profile

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user_record = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        profile = dict(user_record) if user_record else None

    # Phase 6: `level` — производная от `xp`. Всегда отдаём вычисленный уровень,
    # а хранимую колонку лечим, если она отстала (self-heal).
    if profile:
        xp = profile.get('xp') or 0
        stored_level = profile.get('level') or 1
        canonical_level = get_level_for_xp(xp)
        if canonical_level != stored_level:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE users SET level = $1 WHERE telegram_id = $2",
                        canonical_level, telegram_id,
                    )
            except Exception as e:
                logger.warning("Не удалось обновить level для %s: %s", telegram_id, e)
        profile['level'] = canonical_level

        # PostgreSQL 17+ больше не принимает Europe/Kiev и другие устаревшие
        # алиасы — нормализуем, чтобы не упасть в AT TIME ZONE запросах.
        stored_tz = profile.get('timezone')
        canonical_tz = normalize_timezone(stored_tz)
        if canonical_tz != stored_tz:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE users SET timezone = $1 WHERE telegram_id = $2",
                        canonical_tz, telegram_id,
                    )
            except Exception as e:
                logger.warning("Не удалось нормализовать timezone для %s: %s", telegram_id, e)
        profile['timezone'] = canonical_tz

    if profile:
        await cache_service.set_user_profile_to_cache(telegram_id, profile.copy())

    return profile


async def set_onboarding_status(telegram_id: int, status: bool) -> bool:
    """Устанавливает статус прохождения обучения для пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET has_completed_onboarding = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, status, telegram_id)
        success = int(result.split(" ")[1]) > 0
        if success:
            await cache_service.delete_user_profile_from_cache(telegram_id)
        return success


async def set_user_vip_status(telegram_id: int, is_vip: bool) -> bool:
    """Устанавливает VIP-статус для пользователя и инвалидирует кэш.

    M0: вызов check_and_grant_achievements убран вместе с gamification_service.
    Поле is_vip будет вытеснено полем users.pro_until в M1 (docs/PRODUCT_PLAN.md §4.3).
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("UPDATE users SET is_vip = $1, updated_at = NOW() WHERE telegram_id = $2", is_vip,
                                    telegram_id)
        success = int(result.split(" ")[1]) > 0
        if success:
            await cache_service.delete_user_profile_from_cache(telegram_id)
        return success


async def reset_user_vip_settings(telegram_id: int) -> bool:
    """Сбрасывает персональные настройки VIP-пользователя и инвалидирует кэш."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET default_reminder_time = DEFAULT, pre_reminder_minutes = DEFAULT, daily_digest_time = DEFAULT, updated_at = NOW() WHERE telegram_id = $1"
        result = await conn.execute(query, telegram_id)
        success = int(result.split(" ")[1]) > 0
        if success:
            await cache_service.delete_user_profile_from_cache(telegram_id)
        return success


async def get_all_users_paginated(page: int = 1, per_page: int = 5) -> tuple[list[dict], int]:
    """Возвращает пагинированный список пользователей для админ-панели."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total_items = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
        offset = (page - 1) * per_page
        users_records = await conn.fetch(
            "SELECT telegram_id, username, first_name, is_vip FROM users ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            per_page, offset)
        return [dict(record) for record in users_records], total_items


async def update_user_stt_counters(telegram_id: int, new_count: int, reset_date: date) -> bool:
    """Обновляет счетчик STT и инвалидирует кэш."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET daily_stt_recognitions_count = $1, last_stt_reset_date = $2, updated_at = NOW() WHERE telegram_id = $3",
            new_count, reset_date, telegram_id)
        success = int(result.split(" ")[1]) > 0
        if success:
            await cache_service.delete_user_profile_from_cache(telegram_id)
        return success


async def set_user_daily_digest_status(telegram_id: int, enabled: bool) -> bool:
    """Включает или выключает утреннюю сводку и инвалидирует кэш."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET daily_digest_enabled = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, enabled, telegram_id)
        success = int(result.split(" ")[1]) > 0
        if success:
            await cache_service.delete_user_profile_from_cache(telegram_id)
        return success


async def get_vip_users_for_digest() -> list[dict]:
    """Возвращает VIP-пользователей для отправки утренней сводки."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                SELECT telegram_id, first_name, timezone, daily_digest_time, city_name
                FROM users
                WHERE is_vip = TRUE
                  AND daily_digest_enabled = TRUE
                  AND EXTRACT(HOUR FROM (NOW() AT TIME ZONE timezone)) = EXTRACT(HOUR FROM daily_digest_time);
                """
        records = await conn.fetch(query)
        return [dict(rec) for rec in records]


async def set_user_timezone(telegram_id: int, timezone_name: str) -> bool:
    """Устанавливает часовой пояс и инвалидирует кэш."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET timezone = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, timezone_name, telegram_id)
        success = int(result.split(" ")[1]) > 0
        if success:
            await cache_service.delete_user_profile_from_cache(telegram_id)
        return success


async def set_user_city(telegram_id: int, city_name: str | None) -> bool:
    """
    Устанавливает или удаляет город пользователя для прогноза погоды.
    Инвалидирует кэш профиля.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET city_name = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, city_name, telegram_id)
        success = int(result.split(" ")[1]) > 0
        if success:
            await cache_service.delete_user_profile_from_cache(telegram_id)
        return success


async def set_user_default_reminder_time(telegram_id: int, reminder_time: time) -> bool:
    """Устанавливает время напоминаний и инвалидирует кэш."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET default_reminder_time = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, reminder_time, telegram_id)
        success = int(result.split(" ")[1]) > 0
        if success:
            await cache_service.delete_user_profile_from_cache(telegram_id)
        return success


async def set_user_daily_digest_time(telegram_id: int, digest_time: time) -> bool:
    """Устанавливает время сводки и инвалидирует кэш."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET daily_digest_time = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, digest_time, telegram_id)
        success = int(result.split(" ")[1]) > 0
        if success:
            await cache_service.delete_user_profile_from_cache(telegram_id)
        return success


async def set_user_pre_reminder_minutes(telegram_id: int, minutes: int) -> bool:
    """Устанавливает время пред-напоминания и инвалидирует кэш."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET pre_reminder_minutes = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, minutes, telegram_id)
        success = int(result.split(" ")[1]) > 0
        if success:
            await cache_service.delete_user_profile_from_cache(telegram_id)
        return success


async def set_alice_activation_code(telegram_id: int, code: str, expires_at: datetime) -> bool:
    """Сохраняет код активации и инвалидирует кэш."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET alice_activation_code = $1, alice_code_expires_at = $2 WHERE telegram_id = $3"
        result = await conn.execute(query, code, expires_at, telegram_id)
        success = int(result.split(" ")[1]) > 0
        if success:
            await cache_service.delete_user_profile_from_cache(telegram_id)
        return success


async def find_user_by_alice_code(code: str) -> dict | None:
    """Находит пользователя по коду активации Алисы."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM users WHERE alice_activation_code = $1 AND alice_code_expires_at > NOW()"
        record = await conn.fetchrow(query, code)
        return dict(record) if record else None


async def link_alice_user(telegram_id: int, alice_id: str) -> bool:
    """Привязывает ID Алисы и инвалидирует кэш."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET alice_user_id = $1, alice_activation_code = NULL, alice_code_expires_at = NULL, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, alice_id, telegram_id)
        success = int(result.split(" ")[1]) > 0
        if success:
            await cache_service.delete_user_profile_from_cache(telegram_id)
        return success


async def find_user_by_alice_id(alice_id: str) -> dict | None:
    """Находит пользователя по его ID из Алисы."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM users WHERE alice_user_id = $1"
        record = await conn.fetchrow(query, alice_id)
        return dict(record) if record else None


async def log_user_action(user_telegram_id: int, action_type: str, metadata: dict = None):
    """Логирует действие пользователя для аналитики."""
    pool = await get_db_pool()
    metadata_json = json.dumps(metadata) if metadata else None
    query = "INSERT INTO user_actions (user_telegram_id, action_type, metadata) VALUES ($1, $2, $3);"
    try:
        async with pool.acquire() as conn:
            await conn.execute(query, user_telegram_id, action_type, metadata_json)
    except Exception as e:
        logger.error(f"Ошибка логирования действия '{action_type}' для {user_telegram_id}: {e}")


async def add_xp_and_check_level_up(bot: Bot, user_id: int, amount: int, silent_level_up: bool = False):
    """Добавляет опыт пользователю и проверяет повышение уровня."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET xp = xp + $1 WHERE telegram_id = $2", amount, user_id)

        user = await conn.fetchrow("SELECT level, xp FROM users WHERE telegram_id = $1", user_id)
        if not user:
            return

        current_level, current_xp = user['level'], user['xp']
        new_level = get_level_for_xp(current_xp)

        if new_level > current_level:
            await conn.execute("UPDATE users SET level = $1 WHERE telegram_id = $2", new_level, user_id)
            await cache_service.delete_user_profile_from_cache(user_id)
            if not silent_level_up:
                try:
                    level_up_text = f"🎉 {hbold('Новый уровень!')} 🎉\n\nПоздравляем, вы достигли {hbold(f'{new_level}-го уровня')}! Так держать!"
                    if bot:
                        await bot.send_message(user_id, level_up_text)
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление о новом уровне пользователю {user_id}: {e}")


async def grant_achievement(bot: Bot, user_id: int, achievement_code: str, silent: bool = False):
    """M0 stub. Геймификация удалена; user_achievements + users.xp вычищаются в M1
    (docs/PRODUCT_PLAN.md §4.9). Функция оставлена как noop, чтобы не ломать
    возможные legacy call-sites до завершения миграции схемы."""
    return None


async def get_user_achievements_codes(user_id: int) -> set:
    """Возвращает множество кодов достижений, полученных пользователем."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch("SELECT achievement_code FROM user_achievements WHERE user_telegram_id = $1",
                                   user_id)
        return {rec['achievement_code'] for rec in records}


async def get_all_achievements() -> list[dict]:
    """Возвращает список всех достижений, используя кэш."""
    cached_achievements = await cache_service.get_all_achievements_from_cache()
    if cached_achievements is not None:
        return cached_achievements

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch("SELECT * FROM achievements ORDER BY id")
        achievements = [dict(rec) for rec in records]

    if achievements:
        await cache_service.set_all_achievements_to_cache(achievements)

    return achievements


async def set_mobile_activation_code(telegram_id: int, code: str, expires_at: datetime) -> bool:
    """Сохраняет или обновляет код активации для мобильного приложения."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
            INSERT INTO mobile_activation_codes (telegram_id, code, expires_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id) DO UPDATE
            SET code = $2, expires_at = $3
        """
        await conn.execute(query, telegram_id, code, expires_at)
        await cache_service.delete_user_profile_from_cache(telegram_id)
        return True


async def find_user_by_mobile_code(code: str) -> dict | None:
    """Находит пользователя по коду активации (если код не истёк)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT u.* FROM users u JOIN mobile_activation_codes mac ON u.telegram_id = mac.telegram_id "
            "WHERE mac.code = $1 AND mac.expires_at > NOW()",
            code.upper()
        )
        return dict(record) if record else None


async def clear_mobile_activation_code(telegram_id: int) -> bool:
    """Удаляет код активации для мобильного приложения после его использования."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM mobile_activation_codes WHERE telegram_id = $1",
            telegram_id
        )
        success = int(result.split(" ")[1]) > 0
        if success:
            await cache_service.delete_user_profile_from_cache(telegram_id)
        return success


async def register_user_device(telegram_id: int, fcm_token: str, platform: str) -> bool:
    """Сохраняет или обновляет FCM токен устройства для пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
            INSERT INTO user_devices (user_telegram_id, fcm_token, platform, last_used_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (fcm_token) DO UPDATE
            SET user_telegram_id = EXCLUDED.user_telegram_id, last_used_at = NOW();
        """
        try:
            await conn.execute(query, telegram_id, fcm_token, platform)
            logger.info(f"Зарегистрирован или обновлен FCM токен для пользователя {telegram_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при регистрации FCM токена для {telegram_id}: {e}")
            return False


async def get_user_device_tokens(telegram_id: int) -> list[str]:
    """Получает все активные FCM токены для пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT fcm_token FROM user_devices WHERE user_telegram_id = $1"
        records = await conn.fetch(query, telegram_id)
        return [rec['fcm_token'] for rec in records]


async def delete_user_device_token(fcm_token: str) -> bool:
    """Удаляет конкретный FCM токен из базы данных."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM user_devices WHERE fcm_token = $1", fcm_token)
        deleted_count = int(result.split(" ")[1])
        if deleted_count > 0:
            logger.info(f"Удален невалидный FCM токен: {fcm_token[:15]}...")
            return True
        return False


async def mark_guide_as_viewed(telegram_id: int, guide_topic: str) -> bool:
    """Добавляет топик гайда в список просмотренных пользователем."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                UPDATE users
                SET viewed_guides = (
                    SELECT jsonb_agg(DISTINCT value)
                    FROM jsonb_array_elements_text(viewed_guides || $2::jsonb)
                )
                WHERE telegram_id = $1;
                """
        result = await conn.execute(query, telegram_id, json.dumps([guide_topic]))
        success = int(result.split(" ")[1]) > 0
        if success:
            await cache_service.delete_user_profile_from_cache(telegram_id)
        return success


async def has_self_birthday_record(telegram_id: int) -> bool:
    """Проверяет, добавил ли пользователь свой день рождения."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                SELECT 1 FROM birthdays
                WHERE user_telegram_id = $1
                  AND (person_name ILIKE '%мой др%' OR person_name ILIKE '%моё др%' OR person_name ILIKE 'я')
                LIMIT 1;
                """
        return await conn.fetchval(query, telegram_id) is not None


async def get_all_users_with_habits() -> list[int]:
    """Возвращает ID всех пользователей, у которых есть хотя бы одна активная привычка."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT DISTINCT user_telegram_id FROM habits WHERE is_active = TRUE"
        records = await conn.fetch(query)
        return [rec['user_telegram_id'] for rec in records]