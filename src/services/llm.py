# src/services/llm.py
import asyncio
import json
import logging
from enum import Enum
from datetime import datetime

import aiohttp
from ..core.config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME
from ..services.tz_utils import get_day_of_week_str # Добавим утилиту для дня недели

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
    system_prompt = """
Ты — AI для списков покупок. Извлеки из текста все товары и верни JSON-объект со структурой:
{
  "summary_text": "Список покупок",
  "corrected_text": "Полный исправленный текст, например, 'Нужно купить: ...'",
  "items": [
    { "item_name": "Название товара 1 (вес, единица измерения, дополнительная информация)", "checked": false },
    { "item_name": "Название товара 2(вес, единица измерения, дополнительная информация)", "checked": false }
  ]
}
Очень важное правило: Названия товаров должны быть в именительном падеже. Указывай единицы измерения или вес если они есть и дополнительную информацию (если пользователь написал в Пятерочке в Магните или еще в таком ключе значит это магазин или может быть просто указан купить на Рынке - это рынок).
"""
    user_prompt = f"Извлеки товары из: \"{raw_text}\""
    return await _call_deepseek_api(system_prompt, user_prompt, is_json_output=True)


# --- ИЗМЕНЕНИЕ: Полностью переписан промпт для лучшего распознавания дат ---
async def extract_reminder_details(raw_text: str, current_user_datetime_iso: str) -> dict:
    current_dt = datetime.fromisoformat(current_user_datetime_iso)
    day_of_week = get_day_of_week_str(current_dt)

    system_prompt = f"""
Ты — AI-парсер времени. Твоя задача — извлечь из текста суть задачи и компоненты времени.
**Контекст:** Текущая дата и время пользователя: `{current_user_datetime_iso}` (это {day_of_week}). Используй эту дату как точку отсчета для "сегодня", "завтра", "в среду" и т.д.

Твой ответ ДОЛЖЕН быть JSON-объектом следующей структуры:
{{
  "summary_text": "Краткая суть задачи (до 7 слов).",
  "corrected_text": "Полный исправленный текст.",
  "time_components": {{
    "original_mention": "Фраза, которой было упомянуто время.",
    "relative_days": <int | null>,
    "relative_hours": <int | null>,
    "relative_minutes": <int | null>,
    "set_year": <int | null>,
    "set_month": <int | null>,
    "set_day": <int | null>,
    "set_hour": <int | null>,
    "set_minute": <int | null>,
    "is_today_explicit": <boolean | null>
  }},
  "recurrence_rule": "Строка iCalendar RRULE или null."
}}

**ПРАВИЛА АНАЛИЗА:**
1.  `summary_text` и `corrected_text` обязательны всегда.
2.  Если время не упомянуто, `time_components` и `recurrence_rule` должны быть `null`.
3.  `relative_`: Используй для "через 2 часа", "послезавтра" (relative_days: 2), "через неделю" (relative_days: 7).
4.  `set_`: Используй для точных дат и времени: "в 10 утра" (set_hour: 10), "15го числа" (set_day: 15), "31 июля" (set_day: 31, set_month: 7).
5.  Если пользователь говорит "вечером", считай это как 19:00. "Утром" - 9:00. "Днем" - 14:00.
6.  `is_today_explicit`: `true` только если есть слово "сегодня".
7.  `recurrence_rule`: Если есть слова "каждый день", "ежедневно", "каждую неделю" - создай RRULE. Например, "каждый день" -> "FREQ=DAILY". "Каждый вторник" -> "FREQ=WEEKLY;BYDAY=TU".

**ПРИМЕРЫ (учитывая, что сегодня {current_dt.strftime('%Y-%m-%d')}):**
- **Вход:** "встреча с командой завтра в 10:00"
- **Выход:** {{"summary_text": "Встреча с командой", "corrected_text": "Встреча с командой завтра в 10:00.", "time_components": {{"original_mention": "завтра в 10:00", "relative_days": 1, "set_hour": 10, "set_minute": 0}}, "recurrence_rule": null}}

- **Вход:** "позвонить маме в субботу вечером"
- **Выход:** {{"summary_text": "Позвонить маме", "corrected_text": "Позвонить маме в субботу вечером.", "time_components": {{"original_mention": "в субботу вечером", "set_hour": 19, "set_minute": 0 /* ... и set_day/month/year для ближайшей субботы */}}, "recurrence_rule": null}}

- **Вход:** "Напомни мне 31.07 пойти в театр"
- **Выход:** {{"summary_text": "Пойти в театр", "corrected_text": "Напомни мне 31.07 пойти в театр.", "time_components": {{"original_mention": "31.07", "set_day": 31, "set_month": 7}}, "recurrence_rule": null}}

- **Вход:** "просто мысль"
- **Выход:** {{"summary_text": "Просто мысль", "corrected_text": "Просто мысль.", "time_components": null, "recurrence_rule": null}}

- **Вход:** "платить за интернет каждый месяц 25го числа"
- **Выход:** {{"summary_text": "Платить за интернет", "corrected_text": "Платить за интернет каждый месяц 25го числа.", "time_components": {{"original_mention": "25го числа", "set_day": 25}}, "recurrence_rule": "FREQ=MONTHLY;BYMONTHDAY=25"}}
"""
    user_prompt = f"Извлеки данные из: \"{raw_text}\""
    return await _call_deepseek_api(system_prompt, user_prompt, is_json_output=True)


# --- ИЗМЕНЕНИЕ: Полностью заменяем эту функцию ---
async def generate_digest_text(
        user_name: str,
        weather_forecast: str,
        notes_for_prompt: str,
        bdays_for_prompt: str,
        upcoming_for_prompt: str,
        overdue_for_prompt: str
) -> dict:
    """Генерирует текст утренней сводки с помощью LLM."""
    system_prompt = f"""
Ты — дружелюбный и мотивирующий AI-ассистент. Твоя задача — составить короткое, бодрое и информативное утреннее сообщение для пользователя по имени {user_name}.
Ответ должен быть в формате HTML для Telegram.

**ПРАВИЛА:**
1.  Будь кратким, позитивным и используй HTML-теги `<b>` для заголовков и `<i>` для акцентов. Используй иконки для каждого блока.
2.  Используй `\n` для переноса строки. Не используй теги `<br>`.
3.  Начни с приветствия. Затем, если есть погода, выведи ее.
4.  Если какой-то из блоков (задачи на сегодня, на неделю, пропущенные, дни рождения) пуст (содержит "Нет..."), НЕ включай этот блок в итоговое сообщение вообще. Это очень важно для компактности.
5.  Порядок блоков: Погода, Задачи на сегодня, Задачи на неделю, Пропущенные задачи, Дни рождения.
6.  Закончи короткой мотивирующей фразой.
"""
    user_prompt = f"""
Вот данные для сводки для пользователя {user_name}:

**🌦️ Прогноз погоды:**
{weather_forecast}

**✅ Задачи на сегодня:**
{notes_for_prompt}

**🗓️ Задачи на ближайшие дни:**
{upcoming_for_prompt}

**⏳ Пропущенные задачи:**
{overdue_for_prompt}

**🎂 Дни рождения на неделе:**
{bdays_for_prompt}
---
Сгенерируй финальное HTML-сообщение, строго следуя правилам.
"""
    # Для генерации текста лучше подходит более высокая температура
    return await _call_deepseek_api(system_prompt, user_prompt, is_json_output=False, temperature=0.4)
# --- КОНЕЦ ИЗМЕНЕНИЯ ---


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
    system_prompt = """
Ты — AI-аналитик. Определи, являются ли две формулировки одной и той же задачей.
Верни JSON с одним ключом "is_same" (boolean).
"""
    user_prompt = f'Задача 1: "{task1_text}"\nЗадача 2: "{task2_text}"\n\nМожно сказать что они одинаковые?'
    result = await _call_deepseek_api(system_prompt, user_prompt, is_json_output=True)
    if "error" in result:
        return False
    return result.get("is_same", False)


async def search_notes_with_llm(notes: list[dict], query: str, max_results: int = 10) -> list[dict]:
    if not notes:
        return []
    notes_for_llm = [
        {
            "id": n["note_id"],
            "title": n.get("summary_text") or n.get("corrected_text", "")[:30],
            "text": n.get("corrected_text", "")
        }
        for n in notes
    ]
    system_prompt = (
        "Ты — интеллектуальный помощник. Пользователь ищет среди своих заметок. "
        "Твоя задача — выбрать наиболее релевантные заметки по запросу пользователя. "
        "Верни JSON-массив с объектами: id, title, snippet (короткий фрагмент из текста заметки, объясняющий релевантность). "
        "Сортируй по убыванию релевантности. Максимум 5 результатов."
    )
    user_prompt = (
        f"Запрос пользователя: {query}\n"
        f"Список заметок (каждая на новой строке):\n" +
        "\n".join([f"id: {n['id']}, title: {n['title']}, text: {n['text']}" for n in notes_for_llm])
    )
    llm_response = await _call_deepseek_api(system_prompt, user_prompt, is_json_output=True)
    if "error" in llm_response:
        return []
    results = llm_response.get("results")
    if not results and isinstance(llm_response, list):
        results = llm_response
    if not results:
        return []
    id_to_note = {n["note_id"]: n for n in notes}
    found = []
    for item in results:
        note_id = item.get("id")
        if note_id in id_to_note:
            note = id_to_note[note_id]
            found.append({
                "id": note_id,
                "title": item.get("title") or note.get("summary_text") or note.get("corrected_text", "")[:30],
                "snippet": item.get("snippet") or note.get("corrected_text", "")[:100],
                "created_at": note.get("created_at"),
                "category": note.get("category"),
                "is_archived": note.get("is_archived"),
                "is_completed": note.get("is_completed"),
            })
            if len(found) >= max_results:
                break
    return found