# src/database/user_repo.py
import json
import logging
from datetime import datetime, timezone, date, time
from aiogram import types

from .core import get_db_pool

logger = logging.getLogger(__name__)


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
                RETURNING *;
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
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("UPDATE users SET is_vip = $1, updated_at = NOW() WHERE telegram_id = $2", is_vip,
                                    telegram_id)
        return int(result.split(" ")[1]) > 0


async def reset_user_vip_settings(telegram_id: int) -> bool:
    """Сбрасывает персональные настройки VIP-пользователя к значениям по умолчанию."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET default_reminder_time = DEFAULT, pre_reminder_minutes = DEFAULT, updated_at = NOW() WHERE telegram_id = $1"
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
    """Возвращает VIP-пользователей, для которых настало время отправки утренней сводки (9 утра в их часовом поясе)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
            SELECT telegram_id, first_name, timezone
            FROM users
            WHERE is_vip = TRUE
              AND daily_digest_enabled = TRUE
              AND EXTRACT(HOUR FROM (NOW() AT TIME ZONE timezone)) = 9;
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