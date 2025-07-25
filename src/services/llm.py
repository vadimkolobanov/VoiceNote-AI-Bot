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
        if isinstance(value, str):
            value_lower = value.lower()
            if "заметк" in value_lower:
                return cls.CREATE_NOTE
            if "покуп" in value_lower:
                return cls.CREATE_SHOPPING_LIST
            if "напоминани" in value_lower:
                return cls.CREATE_REMINDER
        return super()._missing_(value)


def _parse_llm_json_response(response_text: str) -> dict:
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


async def _call_deepseek_api(system_prompt: str, user_prompt: str, is_json_output: bool = True,
                             temperature: float = 0.1) -> dict:
    if not all([DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME]):
        return {"error": "DeepSeek API not configured"}

    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature,
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
    system_prompt = f"""
Ты — AI-классификатор. Твоя задача — проанализировать текст и определить основное намерение пользователя.
Верни JSON с одним ключом "intent", значение которого может быть одним из следующих:
- `{UserIntent.CREATE_SHOPPING_LIST.value}`: если текст явно является списком покупок.
- `{UserIntent.CREATE_REMINDER.value}`: если в тексте есть четкое указание на дату или время.
- `{UserIntent.CREATE_NOTE.value}`: для всех остальных случаев (идеи, мысли, задачи без даты).
- `{UserIntent.UNKNOWN.value}`: если текст бессмысленный или является простым приветствием.
"""
    user_prompt = f"Определи намерение в тексте: \"{raw_text}\""
    return await _call_deepseek_api(system_prompt, user_prompt, is_json_output=True)


async def get_fun_suggestion(user_name: str) -> str:
    """
    Генерирует креативное, саркастичное и смешное предложение для заскучавшего пользователя.
    """
    system_prompt = f"""
Ты — AI-ассистент с яркой личностью. Твоя роль: слегка ленивый, всезнающий, саркастичный, но в глубине души заботливый дворецкий.
Тебя просит о помощи твой "человек", которому стало скучно. Ты должен придумать одно оригинальное, смешное и немного абсурдное занятие, чтобы его развлечь.
Обращайся к пользователю по имени. Твой ответ должен быть коротким (2-3 предложения) и содержать только текст предложения, без лишних вступлений.
"""
    user_prompt = f"Придумай что-нибудь для пользователя по имени {user_name}, которому скучно."
    result = await _call_deepseek_api(system_prompt, user_prompt, is_json_output=False, temperature=0.8)

    if "error" in result:
        return "Так, моя нейронная сеть сейчас занята обдумыванием вечного. Попробуйте развлечь себя самостоятельно. У вас получится, я верю."

    return result.get("content",
                      "Знаете, иногда лучшее занятие — это насладиться моментом ничегонеделания. Но раз уж вы настаиваете... попробуйте научить свой носок новым трюкам.")


async def extract_note_details(raw_text: str) -> dict:
    system_prompt = """
Ты — редактор заметок. Проанализируй текст и верни JSON с двумя ключами:
- "summary_text": Краткая, действенная суть заметки (1-7 слов).
- "corrected_text": Полная, грамматически верная версия оригинального текста.
"""
    user_prompt = f"Обработай текст: \"{raw_text}\""
    return await _call_deepseek_api(system_prompt, user_prompt, is_json_output=True)


async def extract_shopping_list(raw_text: str) -> dict:
    """
    Извлекает список товаров из текста. Возвращает JSON с полной структурой.
    """
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
Названия товаров должны быть в именительном падеже. Очищай их от количества и единиц измерения.
"""
    user_prompt = f"Извлеки товары из: \"{raw_text}\""
    return await _call_deepseek_api(system_prompt, user_prompt, is_json_output=True)


async def extract_reminder_details(raw_text: str, current_user_datetime_iso: str) -> dict:
    """
    Извлекает компоненты времени из текста для создания напоминания.
    """
    system_prompt = f"""
Ты — AI-парсер времени. Твоя единственная задача — извлечь из текста компоненты времени и суть задачи.
Текущее время пользователя для справки: `{current_user_datetime_iso}`. Не используй его для вычислений.
Твой ответ ДОЛЖЕН быть JSON-объектом следующей структуры:
{{
  "summary_text": "Краткая суть задачи.",
  "corrected_text": "Полный исправленный текст.",
  "time_components": {{
    "original_mention": "Фраза, которой было упомянуто время.",
    "relative_days": <int | null>,
    "relative_hours": <int | null>,
    "relative_minutes": <int | null>,
    "set_hour": <int | null>,
    "set_minute": <int | null>
  }},
  "recurrence_rule": "Строка iCalendar RRULE или null."
}}

**ПРАВИЛА:**
- Используй `relative_` поля для фраз "через...", "послезавтра".
- Используй `set_` поля для фраз "в 10 утра", "в 15:30".
- Если время не упомянуто, `time_components` должен быть `null`.

**ПРИМЕРЫ:**
- **Вход:** "пойти за водой через пол часа"
- **Выход:** {{"summary_text": "Пойти за водой", "corrected_text": "Пойти за водой через полчаса.", "time_components": {{"original_mention": "через пол часа", "relative_minutes": 30}}}}

- **Вход:** "пойти за водой через час"
- **Выход:** {{"summary_text": "Пойти за водой", "corrected_text": "Пойти за водой через час.", "time_components": {{"original_mention": "через час", "relative_hours": 1}}}}

- **Вход:** "встреча с командой завтра в 10:00"
- **Выход:** {{"summary_text": "Встреча с командой", "corrected_text": "Встреча с командой завтра в 10:00.", "time_components": {{"original_mention": "завтра в 10:00", "relative_days": 1, "set_hour": 10, "set_minute": 0}}}}

- **Вход:** "просто мысль"
- **Выход:** {{"summary_text": "Просто мысль", "corrected_text": "Просто мысль.", "time_components": null}}
"""
    user_prompt = f"Извлеки данные из: \"{raw_text}\""
    return await _call_deepseek_api(system_prompt, user_prompt, is_json_output=True)


async def are_tasks_conflicting(task1_text: str, task2_text: str) -> bool:
    system_prompt = """
Ты — AI-аналитик продуктивности. Определи, конфликтуют ли две задачи по своей сути.
Верни JSON с одним ключом "is_conflicting" (boolean).
"""
    user_prompt = f'Задача 1: "{task1_text}"\nЗадача 2: "{task2_text}"\n\nКонфликтуют ли они?'
    result = await _call_deepseek_api(system_prompt, user_prompt, is_json_output=True)
    if "error" in result:
        return False
    return result.get("is_conflicting", False)


async def are_tasks_same(task1_text: str, task2_text: str) -> bool:
    """
    Определяет, описывают ли два текста одну и ту же задачу.
    """
    system_prompt = """
Ты — AI-аналитик. Определи, являются ли две формулировки одной и той же задачей.
Верни JSON с одним ключом "is_same" (boolean).
"""
    user_prompt = f'Задача 1: "{task1_text}"\nЗадача 2: "{task2_text}"\n\nЭто одна и та же задача?'
    result = await _call_deepseek_api(system_prompt, user_prompt, is_json_output=True)
    if "error" in result:
        return False
    return result.get("is_same", False)