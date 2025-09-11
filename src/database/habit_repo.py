# src/database/habit_repo.py
import logging
from datetime import datetime, date

from .connection import get_db_pool

logger = logging.getLogger(__name__)


async def get_user_habits(user_telegram_id: int) -> list[dict]:
    """Возвращает список активных привычек пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM habits WHERE user_telegram_id = $1 AND is_active = TRUE ORDER BY created_at"
        records = await conn.fetch(query, user_telegram_id)
        return [dict(rec) for rec in records]


async def add_habits_bulk(user_telegram_id: int, habits: list[dict]) -> list[dict]:
    """Массово добавляет привычки и возвращает их записи из БД."""
    if not habits:
        return []
    pool = await get_db_pool()

    records_to_insert = []
    for h in habits:
        reminder_time_str = h.get('reminder_time')
        reminder_time_obj = None
        if reminder_time_str:
            try:
                reminder_time_obj = datetime.strptime(reminder_time_str, '%H:%M').time()
            except (ValueError, TypeError):
                logger.warning(
                    f"Некорректный формат времени от LLM: '{reminder_time_str}'. Время не будет установлено.")

        records_to_insert.append(
            (user_telegram_id, h['name'], h['frequency_rule'], reminder_time_obj)
        )

    async with pool.acquire() as conn:
        query = """
                INSERT INTO habits (user_telegram_id, name, frequency_rule, reminder_time)
                SELECT * \
                FROM UNNEST($1::bigint[], $2::text[], $3::text[], $4::time[]) RETURNING * \
                """
        user_ids, names, rules, times = zip(*records_to_insert)

        try:
            inserted_records = await conn.fetch(query, list(user_ids), list(names), list(rules), list(times))
            return [dict(rec) for rec in inserted_records]
        except Exception as e:
            logger.error(f"Ошибка при массовом добавлении привычек для {user_telegram_id}: {e}")
            return []


async def track_habit(habit_id: int, user_telegram_id: int, track_date: date, status: str) -> bool:
    """Записывает выполнение или пропуск привычки."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                INSERT INTO habit_trackings (habit_id, user_telegram_id, track_date, status)
                VALUES ($1, $2, $3, $4) ON CONFLICT (habit_id, track_date) DO \
                UPDATE SET status = $4, tracked_at = NOW() \
                """
        try:
            await conn.execute(query, habit_id, user_telegram_id, track_date, status)
            return True
        except Exception as e:
            logger.error(f"Ошибка при трекинге привычки #{habit_id} для пользователя {user_telegram_id}: {e}")
            return False


async def get_all_active_habits_for_scheduler() -> list[dict]:
    """Возвращает все активные привычки всех пользователей для планировщика."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM habits WHERE is_active = TRUE AND reminder_time IS NOT NULL"
        records = await conn.fetch(query)
        return [dict(rec) for rec in records]


async def delete_habit(habit_id: int, user_telegram_id: int) -> bool:
    """Удаляет привычку пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "DELETE FROM habits WHERE id = $1 AND user_telegram_id = $2"
        result = await conn.execute(query, habit_id, user_telegram_id)
        return int(result.split(" ")[1]) > 0


async def get_weekly_stats(habit_id: int, start_date: str) -> list[dict]:
    """Получает статистику по привычке за последние 7 дней."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                SELECT track_date, status
                FROM habit_trackings
                WHERE habit_id = $1 \
                  AND track_date >= $2
                ORDER BY track_date \
                """
        records = await conn.fetch(query, habit_id, start_date)
        return [dict(rec) for rec in records]