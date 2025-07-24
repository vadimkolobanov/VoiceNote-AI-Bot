# src/database/note_repo.py

import json
import secrets
import logging
import asyncpg
from datetime import datetime, timezone, timedelta

from .connection import get_db_pool
from ..core.config import NOTES_PER_PAGE

logger = logging.getLogger(__name__)


def _process_note_record(record: asyncpg.Record) -> dict | None:
    if not record:
        return None
    note_dict = dict(record)

    if 'owner_id' not in note_dict and 'telegram_id' in note_dict:
        note_dict['owner_id'] = note_dict['telegram_id']

    if 'llm_analysis_json' in note_dict and isinstance(note_dict['llm_analysis_json'], str):
        try:
            note_dict['llm_analysis_json'] = json.loads(note_dict['llm_analysis_json'])
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                f"Не удалось распарсить llm_analysis_json для заметки #{note_dict.get('note_id')}. Оставляем как есть.")
    return note_dict


async def create_note(telegram_id: int, corrected_text: str, **kwargs) -> int | None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                INSERT INTO notes (telegram_id, summary_text, corrected_text, original_stt_text, llm_analysis_json,
                                   original_audio_telegram_file_id, note_taken_at, due_date, recurrence_rule, category)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING note_id; \
                """
        try:
            llm_json_str = json.dumps(kwargs.get("llm_analysis_json")) if kwargs.get("llm_analysis_json") else None
            note_id = await conn.fetchval(
                query,
                telegram_id,
                kwargs.get("summary_text"),
                corrected_text,
                kwargs.get("original_stt_text"),
                llm_json_str,
                kwargs.get("original_audio_telegram_file_id"),
                kwargs.get("note_taken_at"),
                kwargs.get("due_date"),
                kwargs.get("recurrence_rule"),
                kwargs.get("category", "Общее")
            )
            return note_id
        except Exception as e:
            logger.error(f"Ошибка при создании заметки для {telegram_id}: {e}", exc_info=True)
            return None


async def get_note_by_id(note_id: int, telegram_id: int) -> dict | None:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if telegram_id == 0:
            query = "SELECT n.*, n.telegram_id as owner_id FROM notes n WHERE n.note_id = $1 LIMIT 1;"
            record = await conn.fetchrow(query, note_id)
        else:
            query = """
                    SELECT n.*, n.telegram_id as owner_id
                    FROM notes n
                             LEFT JOIN note_shares ns ON n.note_id = ns.note_id
                    WHERE n.note_id = $1
                      AND (n.telegram_id = $2 OR ns.shared_with_telegram_id = $2) LIMIT 1; \
                    """
            record = await conn.fetchrow(query, note_id, telegram_id)
        return _process_note_record(record)


# ... (остальные функции остаются без изменений) ...

async def find_similar_notes(telegram_id: int, summary_text: str, days_ago: int = 90) -> list[dict]:
    """
    Ищет похожие по summary_text заметки пользователя за последние N дней.
    Использует `summary_text` для грубого первичного отсева в БД, чтобы не нагружать AI.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        time_window_start = datetime.now(timezone.utc) - timedelta(days=days_ago)

        # Этот запрос не идеален для поиска по схожести, но он быстрый
        # и отсеет явный мусор. Для production можно использовать pg_trgm.
        query = """
                SELECT note_id, summary_text, corrected_text, due_date, recurrence_rule
                FROM notes
                WHERE telegram_id = $1
                  AND recurrence_rule IS NULL
                  AND created_at >= $2
                  AND summary_text ILIKE $3
                ORDER BY created_at DESC
                    LIMIT 10; \
                """
        # Ищем похожие слова, %word%
        search_pattern = f"%{summary_text.split()[0]}%"

        records = await conn.fetch(query, telegram_id, time_window_start, search_pattern)
        return [_process_note_record(rec) for rec in records]


async def count_active_notes_for_user(telegram_id: int) -> int:
    """Считает количество активных (не в архиве) заметок пользователя."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM notes WHERE telegram_id = $1 AND is_archived = FALSE AND is_completed = FALSE",
            telegram_id) or 0


async def get_paginated_notes_for_user(telegram_id: int, page: int = 1, per_page: int = NOTES_PER_PAGE,
                                       archived: bool = False) -> tuple[list[dict], int]:
    """Возвращает пагинированный список заметок пользователя (активных или архивных)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        archived_filter_sql = "is_archived = TRUE" if archived else "is_archived = FALSE AND is_completed = FALSE"

        count_query = f"""
            SELECT COUNT(*) FROM (
                SELECT note_id FROM notes
                WHERE telegram_id = $1 AND {archived_filter_sql}
                UNION
                SELECT n.note_id FROM notes n
                JOIN note_shares ns ON n.note_id = ns.note_id
                WHERE ns.shared_with_telegram_id = $1 AND n.{archived_filter_sql}
            ) as combined_notes;
        """
        total_items = await conn.fetchval(count_query, telegram_id) or 0

        offset = (page - 1) * per_page
        fetch_query = f"""
            SELECT * FROM (
                SELECT *, telegram_id as owner_id FROM notes
                WHERE telegram_id = $1 AND {archived_filter_sql}
                UNION
                SELECT n.*, n.telegram_id as owner_id FROM notes n
                JOIN note_shares ns ON n.note_id = ns.note_id
                WHERE ns.shared_with_telegram_id = $1 AND n.{archived_filter_sql}
            ) as combined_notes
            ORDER BY due_date ASC NULLS LAST, created_at DESC
            LIMIT $2 OFFSET $3;
        """
        notes_records = await conn.fetch(fetch_query, telegram_id, per_page, offset)
        return [_process_note_record(rec) for rec in notes_records], total_items


async def update_note_text(note_id: int, new_text: str, telegram_id: int) -> bool:
    """Обновляет основной текст заметки. Проверяет, что `telegram_id` является владельцем."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notes SET corrected_text = $1, updated_at = NOW() WHERE note_id = $2 AND telegram_id = $3",
            new_text, note_id, telegram_id)
        return int(result.split(" ")[1]) > 0


async def update_note_category(note_id: int, new_category: str) -> bool:
    """Обновляет категорию заметки."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notes SET category = $1, updated_at = NOW() WHERE note_id = $2", new_category,
            note_id)
        return int(result.split(" ")[1]) > 0


async def update_note_llm_json(note_id: int, new_llm_json: dict) -> bool:
    """Обновляет JSON-поле с результатом анализа от LLM."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        json_str = json.dumps(new_llm_json)
        query = "UPDATE notes SET llm_analysis_json = $1, updated_at = NOW() WHERE note_id = $2"
        result = await conn.execute(query, json_str, note_id)
        return int(result.split(" ")[1]) > 0


async def set_note_archived_status(note_id: int, archived: bool) -> bool:
    """Устанавливает статус архивации для заметки."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notes SET is_archived = $1, updated_at = NOW() WHERE note_id = $2", archived,
            note_id)
        return int(result.split(" ")[1]) > 0


async def set_note_completed_status(note_id: int, completed: bool) -> bool:
    """Устанавливает статус 'выполнено' для заметки (и также архивирует ее)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE notes SET is_completed = $1, is_archived = $1, updated_at = NOW() WHERE note_id = $2",
            completed, note_id)
        return int(result.split(" ")[1]) > 0


async def update_note_due_date(note_id: int, new_due_date: datetime) -> bool:
    """Обновляет дату и время напоминания."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("UPDATE notes SET due_date = $1, updated_at = NOW() WHERE note_id = $2",
                                    new_due_date, note_id)
        return int(result.split(" ")[1]) > 0


async def set_note_recurrence_rule(note_id: int, telegram_id: int, rule: str | None) -> bool:
    """Устанавливает или сбрасывает правило повторения для заметки."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE notes SET recurrence_rule = $1, updated_at = NOW() WHERE note_id = $2 AND telegram_id = $3"
        result = await conn.execute(query, rule, note_id, telegram_id)
        return int(result.split(" ")[1]) > 0


async def delete_note(note_id: int, telegram_id: int) -> bool:
    """Полностью удаляет заметку из БД. Проверяет, что `telegram_id` является владельцем."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM notes WHERE note_id = $1 AND telegram_id = $2", note_id, telegram_id)
        return int(result.split(" ")[1]) > 0


async def get_notes_with_reminders() -> list[dict]:
    """Возвращает все активные заметки с установленным напоминанием в будущем для загрузки в планировщик."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                SELECT n.*, u.default_reminder_time, u.timezone, u.pre_reminder_minutes, u.is_vip
                FROM notes n
                         JOIN users u ON n.telegram_id = u.telegram_id
                WHERE n.is_archived = FALSE
                  AND n.is_completed = FALSE
                  AND n.due_date IS NOT NULL
                  AND n.due_date > NOW(); \
                """
        records = await conn.fetch(query)
        processed_records = [_process_note_record(rec) for rec in records]
        return processed_records


async def create_share_token(note_id: int, owner_id: int) -> str | None:
    """Создает одноразовый токен для шаринга заметки по ссылке."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        token = secrets.token_urlsafe(16)
        expires_at = datetime.now(timezone.utc) + timedelta(days=2)
        query = "INSERT INTO share_tokens (token, note_id, owner_id, expires_at) VALUES ($1, $2, $3, $4) RETURNING token;"
        try:
            return await conn.fetchval(query, token, note_id, owner_id, expires_at)
        except Exception as e:
            logger.error(f"Failed to create share token for note {note_id}: {e}")
            return None


async def get_share_token_data(token: str) -> dict | None:
    """Возвращает данные по токену, если он действителен."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM share_tokens WHERE token = $1 AND expires_at > NOW() AND is_used = FALSE"
        record = await conn.fetchrow(query, token)
        return dict(record) if record else None


async def mark_share_token_as_used(token: str) -> bool:
    """Помечает токен как использованный."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE share_tokens SET is_used = TRUE WHERE token = $1"
        result = await conn.execute(query, token)
        return int(result.split(" ")[1]) > 0


async def share_note_with_user(note_id: int, owner_id: int, shared_with_id: int) -> bool:
    """Создает запись о шаринге в таблице note_shares."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            query = "INSERT INTO note_shares (note_id, owner_telegram_id, shared_with_telegram_id) VALUES ($1, $2, $3);"
            await conn.execute(query, note_id, owner_id, shared_with_id)
            return True
        except asyncpg.UniqueViolationError:
            logger.warning(f"Попытка повторно поделиться заметкой {note_id} с пользователем {shared_with_id}.")
            return False
        except Exception as e:
            logger.error(f"Ошибка при шаринге заметки {note_id}: {e}")
            return False


async def get_shared_note_participants(note_id: int) -> list[dict]:
    """Возвращает список всех участников заметки (владельца и тех, с кем поделились)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        owner_query = "SELECT telegram_id, username, first_name FROM users WHERE telegram_id = (SELECT telegram_id FROM notes WHERE note_id = $1)"
        owner_rec = await conn.fetchrow(owner_query, note_id)
        participants = [dict(owner_rec)] if owner_rec else []

        shared_query = """
                       SELECT u.telegram_id, u.username, u.first_name
                       FROM users u
                                JOIN note_shares ns ON u.telegram_id = ns.shared_with_telegram_id
                       WHERE ns.note_id = $1; \
                       """
        shared_recs = await conn.fetch(shared_query, note_id)

        existing_ids = {p['telegram_id'] for p in participants}
        for rec in shared_recs:
            if rec['telegram_id'] not in existing_ids:
                participants.append(dict(rec))

        return participants


async def store_shared_message_id(note_id: int, user_id: int, message_id: int):
    """Сохраняет или обновляет message_id для конкретного пользователя и заметки, чтобы синхронизировать его."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                INSERT INTO shared_note_messages (note_id, user_id, message_id)
                VALUES ($1, $2, $3) ON CONFLICT (note_id, user_id) DO
                UPDATE SET message_id = $3; \
                """
        await conn.execute(query, note_id, user_id, message_id)


async def get_shared_message_ids(note_id: int) -> list[dict]:
    """Возвращает все сохраненные message_id для заметки."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT user_id, message_id FROM shared_note_messages WHERE note_id = $1"
        records = await conn.fetch(query, note_id)
        return [dict(rec) for rec in records]


async def delete_shared_message_id(note_id: int, user_id: int) -> bool:
    """Удаляет сохраненный message_id (например, если сообщение стало недоступно)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "DELETE FROM shared_note_messages WHERE note_id = $1 AND user_id = $2"
        result = await conn.execute(query, note_id, user_id)
        return int(result.split(" ")[1]) > 0


async def get_active_shopping_list(telegram_id: int) -> dict | None:
    """Возвращает активный список покупок, где пользователь либо владелец, либо получатель."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                SELECT n.*, n.telegram_id as owner_id
                FROM notes n
                         LEFT JOIN note_shares ns ON n.note_id = ns.note_id
                WHERE (n.telegram_id = $1 OR ns.shared_with_telegram_id = $1)
                  AND n.category = 'Покупки'
                  AND n.is_archived = FALSE
                  AND n.is_completed = FALSE
                ORDER BY n.created_at DESC LIMIT 1;
                """
        record = await conn.fetchrow(query, telegram_id)
        return _process_note_record(record)


async def get_or_create_active_shopping_list_note(telegram_id: int) -> dict | None:
    """
    Ищет активный список покупок у пользователя. Если не находит - создает новый, пустой.
    """
    active_list = await get_active_shopping_list(telegram_id)
    if active_list:
        return active_list

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        create_query = """
                       INSERT INTO notes (telegram_id, summary_text, corrected_text, category, llm_analysis_json,
                                          is_archived, is_completed)
                       VALUES ($1, 'Мой список покупок', 'Список товаров для покупки.', 'Покупки', '{"items": []}',
                               FALSE, FALSE) RETURNING *; \
                       """
        try:
            new_record = await conn.fetchrow(create_query, telegram_id)
            logger.info(f"Создан новый персистентный список покупок для пользователя {telegram_id}")
            return _process_note_record(new_record)
        except Exception as e:
            logger.error(f"Не удалось создать персистентный список покупок для {telegram_id}: {e}")
            return None


async def get_notes_for_today_digest(telegram_id: int, user_timezone: str) -> list[dict]:
    """Возвращает заметки на 'сегодня' в часовом поясе пользователя для утренней сводки."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                SELECT corrected_text, due_date
                FROM notes
                WHERE telegram_id = $1
                  AND is_archived = FALSE
                  AND is_completed = FALSE
                  AND due_date IS NOT NULL
                  AND (due_date AT TIME ZONE $2)::date = (NOW() AT TIME ZONE $2):: date
                ORDER BY due_date ASC; \
                """
        records = await conn.fetch(query, telegram_id, user_timezone)
        return [dict(rec) for rec in records]


async def count_total_and_voice_notes(telegram_id: int) -> tuple[int, int]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
                SELECT COUNT(*) AS total_notes, \
                       COUNT(*)    FILTER (WHERE original_audio_telegram_file_id IS NOT NULL) AS voice_notes
                FROM notes
                WHERE telegram_id = $1; \
                """
        record = await conn.fetchrow(query, telegram_id)
        return (record['total_notes'] or 0, record['voice_notes'] or 0)


async def count_completed_notes(telegram_id: int) -> int:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT COUNT(*) FROM notes WHERE telegram_id = $1 AND is_completed = TRUE;"
        return await conn.fetchval(query, telegram_id) or 0


async def did_user_share_note(telegram_id: int) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT 1 FROM note_shares WHERE owner_telegram_id = $1 LIMIT 1;"
        return await conn.fetchval(query, telegram_id) is not None


async def find_conflicting_notes(telegram_id: int, due_date: datetime, note_id_to_exclude: int) -> list[dict]:
    """
    Ищет активные заметки пользователя, которые пересекаются по времени с новой задачей.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        time_window_start = due_date - timedelta(hours=1)
        time_window_end = due_date + timedelta(hours=1)

        query = """
                SELECT note_id, summary_text, corrected_text, due_date
                FROM notes
                WHERE telegram_id = $1
                  AND is_archived = FALSE
                  AND is_completed = FALSE
                  AND due_date IS NOT NULL
                  AND note_id != $2
                  AND due_date BETWEEN $3 \
                  AND $4
                ORDER BY due_date; \
                """
        records = await conn.fetch(query, telegram_id, note_id_to_exclude, time_window_start, time_window_end)
        return [_process_note_record(rec) for rec in records]