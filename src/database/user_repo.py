# src/database/user_repo.py
import json
import logging
from datetime import datetime, timezone, date, time

import asyncpg
from aiogram import types, Bot
from aiogram.utils.markdown import hbold

from .connection import get_db_pool
from ..services.gamification_service import ACHIEVEMENTS_BY_CODE

logger = logging.getLogger(__name__)


def get_level_for_xp(xp: int) -> int:
    return int((xp / 100) ** 0.5) + 1


def get_xp_for_level(level: int) -> int:
    if level <= 1:
        return 0
    return int(((level - 1) ** 2) * 100)


async def add_or_update_user(telegram_id: int, username: str = None, first_name: str = None, last_name: str = None,
                             language_code: str = None) -> dict | None:
    """
    Добавляет нового пользователя или обновляет данные существующего.
    Возвращает полную запись о пользователе из БД.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        now = datetime.now(timezone.utc)
        query = """
                INSERT INTO users (telegram_id, username, first_name, last_name, language_code, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $6) ON CONFLICT (telegram_id) DO
                UPDATE SET
                    username = EXCLUDED.username, first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name, language_code = EXCLUDED.language_code,
                    updated_at = $6
                    RETURNING *; \
                """
        user_record = await conn.fetchrow(query, telegram_id, username, first_name, last_name, language_code, now)
        return dict(user_record) if user_record else None


async def get_or_create_user(tg_user: types.User) -> dict | None:
    """
    Упрощенная функция: проверяет наличие пользователя в БД. Если нет - добавляет.
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
    """Возвращает профиль пользователя по его telegram_id."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user_record = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        return dict(user_record) if user_record else None


async def set_user_vip_status(telegram_id: int, is_vip: bool) -> bool:
    """Устанавливает VIP-статус для пользователя."""
    from ..services.gamification_service import check_and_grant_achievements
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("UPDATE users SET is_vip = $1, updated_at = NOW() WHERE telegram_id = $2", is_vip,
                                    telegram_id)

        # Проверка на ачивку после смены статуса
        if is_vip:
            from ..main import bot_instance
            await check_and_grant_achievements(bot_instance, telegram_id)

        return int(result.split(" ")[1]) > 0


async def reset_user_vip_settings(telegram_id: int) -> bool:
    """Сбрасывает персональные настройки VIP-пользователя к значениям по умолчанию."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET default_reminder_time = DEFAULT, pre_reminder_minutes = DEFAULT, daily_digest_time = DEFAULT, updated_at = NOW() WHERE telegram_id = $1"
        result = await conn.execute(query, telegram_id)
        return int(result.split(" ")[1]) > 0


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
    """Обновляет счетчик STT и дату сброса для пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET daily_stt_recognitions_count = $1, last_stt_reset_date = $2, updated_at = NOW() WHERE telegram_id = $3",
            new_count, reset_date, telegram_id)
        return int(result.split(" ")[1]) > 0


async def set_user_daily_digest_status(telegram_id: int, enabled: bool) -> bool:
    """Включает или выключает утреннюю сводку для пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET daily_digest_enabled = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, enabled, telegram_id)
        return int(result.split(" ")[1]) > 0


async def get_vip_users_for_digest() -> list[dict]:
    """Возвращает VIP-пользователей, для которых настало время отправки утренней сводки."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                SELECT telegram_id, first_name, timezone, daily_digest_time
                FROM users
                WHERE is_vip = TRUE
                  AND daily_digest_enabled = TRUE
                  AND EXTRACT(HOUR FROM (NOW() AT TIME ZONE timezone)) = EXTRACT(HOUR FROM daily_digest_time); \
                """
        records = await conn.fetch(query)
        return [dict(rec) for rec in records]


async def set_user_timezone(telegram_id: int, timezone_name: str) -> bool:
    """Устанавливает часовой пояс для пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET timezone = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, timezone_name, telegram_id)
        return int(result.split(" ")[1]) > 0


async def set_user_default_reminder_time(telegram_id: int, reminder_time: time) -> bool:
    """Устанавливает время напоминаний по умолчанию для VIP-пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET default_reminder_time = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, reminder_time, telegram_id)
        return int(result.split(" ")[1]) > 0


async def set_user_daily_digest_time(telegram_id: int, digest_time: time) -> bool:
    """Устанавливает время утренней сводки для VIP-пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET daily_digest_time = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, digest_time, telegram_id)
        return int(result.split(" ")[1]) > 0


async def set_user_pre_reminder_minutes(telegram_id: int, minutes: int) -> bool:
    """Устанавливает время предварительного напоминания (в минутах) для VIP-пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET pre_reminder_minutes = $1, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, minutes, telegram_id)
        return int(result.split(" ")[1]) > 0


# --- Функции для интеграции с Алисой ---

async def set_alice_activation_code(telegram_id: int, code: str, expires_at: datetime) -> bool:
    """Сохраняет код активации для Алисы и срок его действия."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET alice_activation_code = $1, alice_code_expires_at = $2 WHERE telegram_id = $3"
        result = await conn.execute(query, code, expires_at, telegram_id)
        return int(result.split(" ")[1]) > 0


async def find_user_by_alice_code(code: str) -> dict | None:
    """Находит пользователя по действующему коду активации Алисы."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM users WHERE alice_activation_code = $1 AND alice_code_expires_at > NOW()"
        record = await conn.fetchrow(query, code)
        return dict(record) if record else None


async def link_alice_user(telegram_id: int, alice_id: str) -> bool:
    """Привязывает ID пользователя Алисы к аккаунту в Telegram."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET alice_user_id = $1, alice_activation_code = NULL, alice_code_expires_at = NULL, updated_at = NOW() WHERE telegram_id = $2"
        result = await conn.execute(query, alice_id, telegram_id)
        return int(result.split(" ")[1]) > 0


async def find_user_by_alice_id(alice_id: str) -> dict | None:
    """Находит пользователя по его ID из Алисы."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM users WHERE alice_user_id = $1"
        record = await conn.fetchrow(query, alice_id)
        return dict(record) if record else None


# --- Логирование действий ---

async def log_user_action(user_telegram_id: int, action_type: str, metadata: dict = None):
    """Записывает действие пользователя в таблицу user_actions для аналитики."""
    pool = await get_db_pool()
    metadata_json = json.dumps(metadata) if metadata else None
    query = "INSERT INTO user_actions (user_telegram_id, action_type, metadata) VALUES ($1, $2, $3);"
    try:
        async with pool.acquire() as conn:
            await conn.execute(query, user_telegram_id, action_type, metadata_json)
    except Exception as e:
        logger.error(f"Ошибка логирования действия '{action_type}' для {user_telegram_id}: {e}")


# --- Функции для геймификации ---

async def add_xp_and_check_level_up(bot: Bot, user_id: int, amount: int, silent_level_up: bool = False):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT level, xp FROM users WHERE telegram_id = $1", user_id)
        if not user:
            return

        current_level, current_xp = user['level'], user['xp']
        new_xp = current_xp + amount
        new_level = get_level_for_xp(new_xp)

        await conn.execute("UPDATE users SET xp = $1, level = $2 WHERE telegram_id = $3", new_xp, new_level, user_id)

        if new_level > current_level and not silent_level_up:
            try:
                level_up_text = f"🎉 {hbold('Новый уровень!')} 🎉\n\nПоздравляем, вы достигли {hbold(f'{new_level}-го уровня')}! Так держать!"
                if bot:
                    await bot.send_message(user_id, level_up_text)
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление о новом уровне пользователю {user_id}: {e}")


async def grant_achievement(bot: Bot, user_id: int, achievement_code: str, silent: bool = False):
    pool = await get_db_pool()
    achievement = ACHIEVEMENTS_BY_CODE.get(achievement_code)
    if not achievement:
        return

    async with pool.acquire() as conn:
        try:
            # Сначала пытаемся вставить. Если ачивка уже есть, выйдет ошибка UniqueViolationError
            await conn.execute("INSERT INTO user_achievements (user_telegram_id, achievement_code) VALUES ($1, $2)",
                               user_id, achievement_code)

            # Если вставка прошла успешно, значит ачивка новая. Начисляем XP.
            await add_xp_and_check_level_up(bot, user_id, achievement.xp_reward, silent_level_up=silent)

            # Отправляем уведомление только если это не "тихая" выдача
            if not silent:
                user_profile = await get_user_profile(user_id)
                user_name = user_profile.get('first_name', 'пользователь')

                text = (
                    f"🏆 {hbold('Новое достижение!')} 🏆\n\n"
                    f"{user_name}, вы получили достижение:\n"
                    f"{achievement.icon} {hbold(achievement.name)}\n"
                    f"«{achievement.description}»\n\n"
                    f"Награда: +{achievement.xp_reward} XP ✨"
                )
                if bot:
                    await bot.send_message(user_id, text, parse_mode="HTML")

        except asyncpg.UniqueViolationError:
            pass  # Пользователь уже имеет это достижение
        except Exception as e:
            logger.error(f"Ошибка при выдаче достижения {achievement_code} пользователю {user_id}: {e}")


async def get_user_achievements_codes(user_id: int) -> set:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch("SELECT achievement_code FROM user_achievements WHERE user_telegram_id = $1",
                                   user_id)
        return {rec['achievement_code'] for rec in records}


async def get_all_achievements() -> list[dict]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch("SELECT * FROM achievements ORDER BY id")
        return [dict(rec) for rec in records]