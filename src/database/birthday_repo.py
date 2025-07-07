# src/database/birthday_repo.py

import logging
from .core import get_db_pool

logger = logging.getLogger(__name__)


async def add_birthday(user_telegram_id: int, person_name: str, day: int, month: int, year: int | None) -> dict | None:
    """Добавляет новую запись о дне рождения."""
    pool = await get_db_pool()
    query = "INSERT INTO birthdays (user_telegram_id, person_name, birth_day, birth_month, birth_year) VALUES ($1, $2, $3, $4, $5) RETURNING *;"
    async with pool.acquire() as conn:
        record = await conn.fetchrow(query, user_telegram_id, person_name, day, month, year)
        return dict(record) if record else None


async def add_birthdays_bulk(user_telegram_id: int, birthdays_data: list[tuple]) -> int:
    """Массово добавляет дни рождения из списка (например, при импорте из файла)."""
    if not birthdays_data:
        return 0
    pool = await get_db_pool()
    # Данные должны быть в формате [(name, day, month, year), ...]
    data_to_insert = [(user_telegram_id, name, day, month, year) for name, day, month, year in birthdays_data]

    async with pool.acquire() as conn:
        # executemany может быть не самым быстрым способом для очень больших объемов,
        # но для сотен записей он отлично подходит и безопасен.
        query = "INSERT INTO birthdays (user_telegram_id, person_name, birth_day, birth_month, birth_year) VALUES ($1, $2, $3, $4, $5);"
        try:
            await conn.executemany(query, data_to_insert)
            return len(data_to_insert)
        except Exception as e:
            logger.error(f"Ошибка при массовом добавлении дней рождений для пользователя {user_telegram_id}: {e}")
            return 0


async def get_birthdays_for_user(telegram_id: int, page: int = 1, per_page: int = 5) -> tuple[list[dict], int]:
    """Возвращает пагинированный список дней рождений для пользователя, отсортированный по ближайшей дате."""
    pool = await get_db_pool()
    offset = (page - 1) * per_page
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM birthdays WHERE user_telegram_id = $1", telegram_id) or 0
        # Сложная сортировка: сначала идут будущие дни рождения этого года, потом - прошедшие (т.е. дни рождения следующего года)
        query = """
            SELECT *
            FROM birthdays
            WHERE user_telegram_id = $1
            ORDER BY
                CASE
                    WHEN (birth_month, birth_day) >= (EXTRACT(MONTH FROM NOW()), EXTRACT(DAY FROM NOW())) THEN 0
                    ELSE 1
                END,
                birth_month,
                birth_day
            LIMIT $2 OFFSET $3;
            """
        records = await conn.fetch(query, telegram_id, per_page, offset)
    return [dict(rec) for rec in records], total


async def count_birthdays_for_user(telegram_id: int) -> int:
    """Считает общее количество сохраненных дней рождений у пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM birthdays WHERE user_telegram_id = $1", telegram_id) or 0


async def delete_birthday(birthday_id: int, user_telegram_id: int) -> bool:
    """Удаляет запись о дне рождения. Проверяет, что удаляет владелец."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM birthdays WHERE id = $1 AND user_telegram_id = $2", birthday_id,
                                    user_telegram_id)
        return int(result.split(" ")[1]) > 0


async def get_all_birthdays_for_reminders() -> list[dict]:
    """Возвращает ВСЕ дни рождения из базы для ежедневной проверки в планировщике."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch("SELECT * FROM birthdays")
        return [dict(rec) for rec in records]


async def get_birthdays_for_upcoming_digest(telegram_id: int) -> list[dict]:
    """Возвращает дни рождения на ближайшие 7 дней для утренней сводки."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Запрос учитывает переход через конец года
        query = """
            SELECT person_name, birth_day, birth_month, birth_year
            FROM birthdays
            WHERE user_telegram_id = $1
              AND to_date(
                    to_char(NOW(), 'YYYY') || '-' || to_char(birth_month, 'FM00') || '-' || to_char(birth_day, 'FM00'),
                    'YYYY-MM-DD'
                  ) BETWEEN date_trunc('day', NOW()) AND date_trunc('day', NOW()) + interval '7 days'
            ORDER BY birth_month, birth_day;
            """
        records = await conn.fetch(query, telegram_id)
        return [dict(rec) for rec in records]