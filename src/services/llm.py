# src/services/llm.py
import asyncio
import json
import logging
from enum import Enum

import aiohttp
from ..core.config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME

logger = logging.getLogger(__name__)


class UserIntent(Enum):
    CREATE_NOTE = "создание_заметки"
    CREATE_SHOPPING_LIST = "список_покупок"
    CREATE_REMINDER = "напоминание"
    UNKNOWN = "неизвестно"

    @classmethod
    def _missing_(cls, value):
        # Этот магический метод вызывается, когда значение не найдено.
        # Он позволяет нам обрабатывать синонимы или опечатки от LLM.
        if isinstance(value, str):
            value_lower = value.lower()
            if "заметк" in value_lower: # Ловит "заметка", "заметки" и т.д.
                return cls.CREATE_NOTE
            if "покуп" in value_lower:
                return cls.CREATE_SHOPPING_LIST
            if "напоминани" in value_lower:
                return cls.CREATE_REMINDER
        return super()._missing_(value)


def _parse_llm_json_response(response_text: str) -> dict:
    """Внутренняя утилита для безопасного парсинга JSON-ответа от LLM."""
    if response_text.strip().startswith("```json"):
        response_text = response_text.strip()[7:-3].strip()
    elif response_text.strip().startswith("```"):
        response_text = response_text.strip()[3:-3].strip()

    try:
        data = json.loads(response_text)
        if not isinstance(data, dict):
            logger.warning(f"LLM вернула JSON, но это не словарь: {data}")
            return {"error": "LLM returned non-dict JSON"}
        return data
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Ошибка декодирования JSON от LLM: {e}. Ответ LLM: {response_text[:500]}...")
        return {"error": "Failed to decode JSON from LLM"}


async def _call_deepseek_api(system_prompt: str, user_prompt: str, is_json_output: bool = True) -> dict:
    """Общая функция для вызова DeepSeek API."""
    if not all([DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME]):
        return {"error": "DeepSeek API not configured"}

    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 2048,
    }
    if is_json_output:
        payload["response_format"] = {"type": "json_object"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    DEEPSEEK_API_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=90)
            ) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    logger.error(f"Ошибка API DeepSeek, статус: {resp.status}. Ответ: {response_text[:500]}")
                    return {"error": f"LLM API Error: Status {resp.status}"}

                response_data = json.loads(response_text)
                message_content_str = response_data.get('choices', [{}])[0].get('message', {}).get('content')
                if not message_content_str:
                    return {"error": "Empty content in LLM response"}

                return _parse_llm_json_response(message_content_str) if is_json_output else {
                    "content": message_content_str}

    except Exception as e:
        logger.exception(f"Неожиданная ошибка во время запроса к DeepSeek: {e}")
        return {"error": f"Unexpected exception: {e}"}


async def classify_intent(raw_text: str) -> dict:
    """Этап 1: Классификация намерения пользователя."""
    system_prompt = f"""
Ты — AI-классификатор. Твоя задача — проанализировать текст и определить основное намерение пользователя.
Верни JSON с одним ключом "intent", значение которого может быть одним из следующих:
- `{UserIntent.CREATE_SHOPPING_LIST.value}`: если текст явно является списком покупок (содержит слова "купить", "список покупок", "в магазин" и перечисление товаров).
- `{UserIntent.CREATE_REMINDER.value}`: если в тексте есть четкое указание на дату или время (завтра, в пятницу, 25 декабря, в 12:30).
- `{UserIntent.CREATE_NOTE.value}`: для всех остальных случаев (идеи, мысли, задачи без конкретной даты).
- `{UserIntent.UNKNOWN.value}`: если текст бессмысленный или является простым приветствием.
"""
    user_prompt = f"Определи намерение в тексте: \"{raw_text}\""
    return await _call_deepseek_api(system_prompt, user_prompt)


async def extract_note_details(raw_text: str) -> dict:
    """Этап 2 (для заметок): Извлечение сути и исправление текста."""
    system_prompt = """
Ты — редактор заметок. Проанализируй текст и верни JSON с двумя ключами:
- "summary_text": Краткая, действенная суть заметки (1-7 слов). Например, "Позвонить маме", "Идея для проекта".
- "corrected_text": Полная, грамматически верная версия оригинального текста.
"""
    user_prompt = f"Обработай текст: \"{raw_text}\""
    return await _call_deepseek_api(system_prompt, user_prompt)


async def extract_shopping_list(raw_text: str) -> dict:
    """Этап 2 (для списка покупок): Извлечение товаров."""
    system_prompt = """
Ты — AI для списков покупок. Извлеки из текста все товары и верни JSON-объект со структурой:
{
  "summary_text": "Список покупок",
  "corrected_text": "Полный исправленный текст, например, 'Нужно купить: ...'",
  "items": [
    { "item_name": "Название товара 1", "checked": false },
    { "item_name": "Название товара 2", "checked": false }
  ]
}
Названия товаров должны быть в именительном падеже.
"""
    user_prompt = f"Извлеки товары из: \"{raw_text}\""
    return await _call_deepseek_api(system_prompt, user_prompt)


async def extract_reminder_details(raw_text: str, current_user_datetime_iso: str) -> dict:
    """Этап 2 (для напоминаний): Извлечение даты, времени и сути."""
    system_prompt = f"""
Ты — AI для создания напоминаний. Проанализируй текст, учитывая, что текущее время пользователя — `{current_user_datetime_iso}`.
Верни JSON со следующей структурой:
{{
  "summary_text": "Краткая суть задачи (1-7 слов)",
  "corrected_text": "Полный исправленный текст.",
  "dates_times": [
    {{
      "original_mention": "Как было упомянуто время/дата.",
      "absolute_datetime_start": "YYYY-MM-DDTHH:MM:SSZ"
    }}
  ],
  "recurrence_rule": "Строка iCalendar RRULE или null."
}}
Всегда возвращай дату в формате UTC ISO 8601 (заканчивается на 'Z').
"""
    user_prompt = f"Извлеки данные для напоминания из: \"{raw_text}\""
    return await _call_deepseek_api(system_prompt, user_prompt)


async def are_tasks_conflicting(task1_text: str, task2_text: str) -> bool:
    """
    Этап 3 (Проактивный): Оценивает, конфликтуют ли две задачи по своей сути.
    """
    system_prompt = """
Ты — AI-аналитик продуктивности. Тебе даны две задачи, которые должны выполняться примерно в одно и то же время.
Твоя задача — определить, конфликтуют ли они по своей сути.

Верни JSON с одним ключом "is_conflicting" (boolean).

Правила для определения конфликта:
- `true`, если задачи требуют физического присутствия в разных местах (например, "встреча в офисе" и "поездка к врачу").
- `true`, если обе задачи требуют полной концентрации и не могут выполняться одновременно (например, "провести совещание" и "написать годовой отчет").
- `false`, если задачи можно совместить или выполнить последовательно без спешки (например, "позвонить маме" и "ответить на письма").
- `false`, если одна из задач короткая и может быть встроена в другую (например, "выпить кофе" и "прочитать новости").
- `false`, если это одна и та же задача, сформулированная по-разному.
"""
    user_prompt = f"""
Задача 1: "{task1_text}"
Задача 2: "{task2_text}"

Конфликтуют ли они?
"""
    result = await _call_deepseek_api(system_prompt, user_prompt)
    if "error" in result:
        # В случае ошибки AI, лучше не беспокоить пользователя
        logger.warning(f"Ошибка при анализе конфликта задач: {result['error']}")
        return False

    return result.get("is_conflicting", False)