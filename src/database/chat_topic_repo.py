# src/database/chat_topic_repo.py
import logging
from .connection import get_db_pool

logger = logging.getLogger(__name__)

# Типы функций для топиков
FUNCTION_TYPES = {
    'notes': 'notes',  # Обычные заметки
    'shopping_list': 'shopping_list',  # Список покупок
    'reminders': 'reminders',  # Напоминания
    'all': 'all'  # Все функции
}


async def is_topic_allowed(chat_id: int, topic_id: int | None, function_type: str = 'all') -> bool:
    """
    Проверяет, разрешен ли топик для обработки сообщений.
    
    Args:
        chat_id: ID чата
        topic_id: ID топика (может быть None для обычных чатов)
        function_type: Тип функции ('notes', 'shopping_list', 'reminders', 'all')
    
    Returns:
        True если топик разрешен, False если нет
    """
    # Если топик не указан (None), значит это обычный чат без топиков
    # В группах без топиков бот не должен реагировать
    if topic_id is None:
        return False
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Проверяем, есть ли настройка для этого топика с типом 'all' или конкретным типом
        query = """
            SELECT 1 FROM chat_topic_settings
            WHERE chat_id = $1 AND topic_id = $2
            AND (function_type = $3 OR function_type = 'all')
            LIMIT 1
        """
        result = await conn.fetchval(query, chat_id, topic_id, function_type)
        return result is not None


async def add_topic_setting(chat_id: int, topic_id: int, function_type: str) -> bool:
    """
    Добавляет настройку топика для обработки сообщений.
    
    Args:
        chat_id: ID чата
        topic_id: ID топика
        function_type: Тип функции ('notes', 'shopping_list', 'reminders', 'all')
    
    Returns:
        True если успешно добавлено
    """
    if function_type not in FUNCTION_TYPES.values():
        logger.warning(f"Неизвестный тип функции: {function_type}")
        return False
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            query = """
                INSERT INTO chat_topic_settings (chat_id, topic_id, function_type, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (chat_id, topic_id, function_type) DO UPDATE
                SET updated_at = NOW()
            """
            await conn.execute(query, chat_id, topic_id, function_type)
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении настройки топика: {e}", exc_info=True)
            return False


async def remove_topic_setting(chat_id: int, topic_id: int, function_type: str | None = None) -> bool:
    """
    Удаляет настройку топика.
    
    Args:
        chat_id: ID чата
        topic_id: ID топика
        function_type: Тип функции (если None, удаляет все настройки для топика)
    
    Returns:
        True если успешно удалено
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            if function_type:
                query = "DELETE FROM chat_topic_settings WHERE chat_id = $1 AND topic_id = $2 AND function_type = $3"
                await conn.execute(query, chat_id, topic_id, function_type)
            else:
                query = "DELETE FROM chat_topic_settings WHERE chat_id = $1 AND topic_id = $2"
                await conn.execute(query, chat_id, topic_id)
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении настройки топика: {e}", exc_info=True)
            return False


async def get_chat_topic_settings(chat_id: int) -> list[dict]:
    """
    Получает все настройки топиков для чата.
    
    Args:
        chat_id: ID чата
    
    Returns:
        Список словарей с настройками топиков
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT topic_id, function_type, created_at FROM chat_topic_settings WHERE chat_id = $1 ORDER BY created_at"
        records = await conn.fetch(query, chat_id)
        return [dict(rec) for rec in records]


