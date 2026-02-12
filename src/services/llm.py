# src/services/llm.py
import asyncio
import json
import logging
from enum import Enum
from datetime import datetime

import aiohttp
from ..core.config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME
from ..services.tz_utils import get_day_of_week_str

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
    import re

    text = response_text.strip()

    # Извлекаем JSON из markdown fence (```json ... ``` или ``` ... ```)
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    elif text.startswith("```"):
        # Незакрытый fence — убираем открывающий маркер
        text = re.sub(r'^```(?:json)?\s*\n?', '', text).strip()

    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            # LLM иногда возвращает массив (например, search_notes_with_llm) — оборачиваем
            if isinstance(data, list):
                return {"results": data}
            logger.warning(f"LLM вернула JSON, но это не словарь и не список: {type(data)}")
            return {"error": "LLM returned non-dict JSON"}
        return data
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Ошибка декодирования JSON от LLM: {e}. Ответ LLM: {text[:500]}...")
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

    except asyncio.TimeoutError:
        logger.error("Таймаут запроса к DeepSeek API (90 сек)")
        return {"error": "LLM API timeout (90s)"}
    except aiohttp.ClientError as e:
        logger.error(f"Сетевая ошибка при запросе к DeepSeek: {e}")
        return {"error": f"Network error: {e}"}
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
Ты — AI для списков покупок. Твоя задача — извлечь из текста все товары и структурировать их.

**ПРАВИЛА:**

1. **Названия товаров:**
   - Всегда в именительном падеже
   - Сохраняй оригинальные единицы измерения, если указаны
   - Если единицы не указаны, добавляй разумные по умолчанию:
     * Жидкости (молоко, сок, вода, кефир) → "1 л"
     * Твердые продукты (хлеб, сыр, колбаса) → "1 шт" или "500 г" (в зависимости от контекста)
     * Овощи/фрукты → "1 кг" или количество (если указано: "3 яблока" → "яблоки, 3 шт")
     * Яйца → "10 шт" (стандартная упаковка)
     * Мясо/рыба → "500 г" (если не указано)
     * Крупы/макароны → "1 кг" (если не указано)

2. **Дополнительная информация:**
   - Если упомянут магазин ("в Пятерочке", "в Магните", "в Ашане") → добавь в название товара в скобках: "молоко, 1 л (Пятерочка)"
   - Если упомянут рынок ("на рынке", "на базаре") → добавь "(рынок)"
   - Если упомянута аптека → категория "Аптека" (но это не список покупок, это отдельная категория)

3. **Обработка списков:**
   - "молоко, хлеб, яйца" → три отдельных товара
   - "2 кг сахара, 3 литра молока" → сохрани количество: "сахар, 2 кг", "молоко, 3 л"
   - "молоко 2 литра" → "молоко, 2 л"
   - "хлеб белый" → "хлеб белый, 1 шт"
   - "яйца куриные 10 штук" → "яйца куриные, 10 шт"

4. **Формат ответа:**
   Верни JSON-объект со структурой:
   {
     "summary_text": "Список покупок",
     "corrected_text": "Полный исправленный текст, например, 'Нужно купить: ...'",
     "items": [
       { "item_name": "Название товара с единицами измерения и дополнительной информацией", "checked": false }
     ]
   }

**ПРИМЕРЫ:**

Вход: "купить молоко, хлеб, яйца в Пятерочке"
Выход: {
  "summary_text": "Список покупок",
  "corrected_text": "Купить молоко, хлеб, яйца в Пятерочке.",
  "items": [
    {"item_name": "молоко, 1 л (Пятерочка)", "checked": false},
    {"item_name": "хлеб, 1 шт (Пятерочка)", "checked": false},
    {"item_name": "яйца, 10 шт (Пятерочка)", "checked": false}
  ]
}

Вход: "нужно купить 2 кг сахара, 3 литра молока, хлеб белый"
Выход: {
  "summary_text": "Список покупок",
  "corrected_text": "Нужно купить 2 кг сахара, 3 литра молока, хлеб белый.",
  "items": [
    {"item_name": "сахар, 2 кг", "checked": false},
    {"item_name": "молоко, 3 л", "checked": false},
    {"item_name": "хлеб белый, 1 шт", "checked": false}
  ]
}

Вход: "молоко хлеб яйца"
Выход: {
  "summary_text": "Список покупок",
  "corrected_text": "Молоко, хлеб, яйца.",
  "items": [
    {"item_name": "молоко, 1 л", "checked": false},
    {"item_name": "хлеб, 1 шт", "checked": false},
    {"item_name": "яйца, 10 шт", "checked": false}
  ]
}
"""
    user_prompt = f"Извлеки товары из: \"{raw_text}\""
    return await _call_deepseek_api(system_prompt, user_prompt, is_json_output=True)


async def extract_reminder_details(raw_text: str, current_user_datetime_iso: str) -> dict:
    current_dt = datetime.fromisoformat(current_user_datetime_iso)
    day_of_week = get_day_of_week_str(current_dt)

    system_prompt = f"""
Ты — умный AI-парсер времени и задач. Твоя задача — извлечь из текста суть задачи и все компоненты времени.

**КОНТЕКСТ:** Текущая дата и время пользователя: `{current_user_datetime_iso}` (это {day_of_week}). Используй эту дату как точку отсчета для "сегодня", "завтра", "в среду" и т.д.

**ТВОЯ ЛИЧНОСТЬ:**
- Ты внимательный и точный помощник
- Ты понимаешь контекст и намерения пользователя
- Ты учитываешь культурные особенности (рабочие дни, праздники)

Твой ответ ДОЛЖЕН быть JSON-объектом следующей структуры:
{{
  "summary_text": "Краткая суть задачи (до 7 слов, в именительном падеже).",
  "corrected_text": "Полный исправленный текст (грамматически правильное предложение).",
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

**ПРАВИЛА АНАЛИЗА ВРЕМЕНИ:**

1. **Относительные даты:**
   - "сегодня" → relative_days: 0, is_today_explicit: true
   - "завтра" → relative_days: 1
   - "послезавтра" → relative_days: 2
   - "через неделю" → relative_days: 7
   - "через месяц" → относительная дата через 30 дней от текущей
   - "через 2 часа" → relative_hours: 2
   - "через 30 минут" → relative_minutes: 30

2. **Время суток (если не указано конкретное время):**
   - "рано утром" → set_hour: 7, set_minute: 0
   - "утром" → set_hour: 9, set_minute: 0
   - "в обед" / "днем" → set_hour: 14, set_minute: 0
   - "вечером" → set_hour: 19, set_minute: 0
   - "поздно вечером" → set_hour: 22, set_minute: 0
   - "ночью" → set_hour: 23, set_minute: 0

3. **Дни недели:**
   - "в понедельник" → найти ближайший понедельник от текущей даты
   - "в выходные" → ближайшая суббота или воскресенье
   - "в рабочий день" / "в будни" → ближайший понедельник-пятница

4. **Повторяющиеся задачи:**
   - "каждый день" / "ежедневно" → FREQ=DAILY
   - "каждый понедельник" → FREQ=WEEKLY;BYDAY=MO
   - "каждую неделю" → FREQ=WEEKLY
   - "каждый месяц 25го" → FREQ=MONTHLY;BYMONTHDAY=25
   - "каждый второй вторник" → FREQ=WEEKLY;BYDAY=TU;INTERVAL=2
   - "по будням" → FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR
   - "по выходным" → FREQ=WEEKLY;BYDAY=SA,SU

5. **Точные даты:**
   - "31 июля" → set_day: 31, set_month: 7 (год текущий, если не указан)
   - "31.07.2024" → set_day: 31, set_month: 7, set_year: 2024
   - "в 10:30" → set_hour: 10, set_minute: 30
   - "15го числа" → set_day: 15 (месяц текущий)

**ВАЖНО:**
- summary_text должен быть кратким (до 7 слов) и в именительном падеже
- corrected_text должен быть полным, грамматически правильным предложением
- Если время не упомянуто, time_components и recurrence_rule = null
- Всегда проверяй разумность дат (не в прошлом, не слишком далеко в будущем - максимум 2 года)

**ПРИМЕРЫ (учитывая, что сегодня {current_dt.strftime('%Y-%m-%d')}):**
- **Вход:** "встреча с командой завтра в 10:00"
- **Выход:** {{"summary_text": "Встреча с командой", "corrected_text": "Встреча с командой завтра в 10:00.", "time_components": {{"original_mention": "завтра в 10:00", "relative_days": 1, "set_hour": 10, "set_minute": 0}}, "recurrence_rule": null}}

- **Вход:** "позвонить маме в субботу вечером"
- **Выход:** {{"summary_text": "Позвонить маме", "corrected_text": "Позвонить маме в субботу вечером.", "time_components": {{"original_mention": "в субботу вечером", "set_hour": 19, "set_minute": 0}}, "recurrence_rule": null}}

- **Вход:** "Напомни мне 31.07 пойти в театр"
- **Выход:** {{"summary_text": "Пойти в театр", "corrected_text": "Напомни мне 31.07 пойти в театр.", "time_components": {{"original_mention": "31.07", "set_day": 31, "set_month": 7}}, "recurrence_rule": null}}

- **Вход:** "просто мысль"
- **Выход:** {{"summary_text": "Просто мысль", "corrected_text": "Просто мысль.", "time_components": null, "recurrence_rule": null}}

- **Вход:** "платить за интернет каждый месяц 25го числа"
- **Выход:** {{"summary_text": "Платить за интернет", "corrected_text": "Платить за интернет каждый месяц 25го числа.", "time_components": {{"original_mention": "25го числа", "set_day": 25}}, "recurrence_rule": "FREQ=MONTHLY;BYMONTHDAY=25"}}

- **Вход:** "пить витамины каждый день в 9 утра"
- **Выход:** {{"summary_text": "Пить витамины", "corrected_text": "Пить витамины каждый день в 9 утра.", "time_components": {{"original_mention": "каждый день в 9 утра", "set_hour": 9, "set_minute": 0}}, "recurrence_rule": "FREQ=DAILY"}}

- **Вход:** "встреча в понедельник в 15:00"
- **Выход:** {{"summary_text": "Встреча", "corrected_text": "Встреча в понедельник в 15:00.", "time_components": {{"original_mention": "в понедельник в 15:00", "set_hour": 15, "set_minute": 0}}, "recurrence_rule": null}}
"""
    user_prompt = f"Извлеки данные из: \"{raw_text}\""
    return await _call_deepseek_api(system_prompt, user_prompt, is_json_output=True)


async def generate_digest_text(
        user_name: str,
        weather_forecast: str,
        notes_for_prompt: str,
        bdays_for_prompt: str,
        upcoming_for_prompt: str,
        overdue_for_prompt: str
) -> dict:
    """Генерирует текст утренней сводки с помощью LLM."""
    # Определяем контекст для адаптации тона
    has_many_tasks = notes_for_prompt and "На сегодня задач нет" not in notes_for_prompt and len(notes_for_prompt.split('\n')) > 3
    has_overdue = overdue_for_prompt and "Нет пропущенных задач" not in overdue_for_prompt
    has_few_tasks = notes_for_prompt and "На сегодня задач нет" not in notes_for_prompt and len(notes_for_prompt.split('\n')) <= 2
    
    system_prompt = f"""
Ты — дружелюбный и мотивирующий AI-ассистент. Твоя задача — составить персональное утреннее сообщение для пользователя по имени {user_name}.

**ТВОЯ ЛИЧНОСТЬ:**
- Ты позитивный, но не навязчивый
- Ты поддерживающий, но не осуждающий
- Ты мотивирующий, но не давящий
- Ты адаптируешь тон под ситуацию

**ПРАВИЛА СОСТАВЛЕНИЯ СВОДКИ:**

1. **Структура:**
   - Начни с персонализированного приветствия (используй разные варианты: "Доброе утро", "С добрым утром", "Приветствую" и т.д.)
   - Если есть погода — добавь её с эмодзи 🌦️
   - Задачи на сегодня — обязательно, если есть
   - Задачи на неделю — только если есть
   - Пропущенные задачи — только если есть (тон должен быть поддерживающим, не осуждающим)
   - Дни рождения — только если есть
   - Заверши мотивирующей фразой

2. **Адаптация тона:**
   - Если много задач → "У вас насыщенный день! Вы справитесь! 💪"
   - Если пропущенные задачи → "Не переживайте, сегодня новый день! 🌟" или "Все в порядке, главное — двигаться вперед! 💪"
   - Если задач мало → "Отличный день для новых свершений! 🚀"
   - Если есть дни рождения → "Не забудьте поздравить близких! 🎂"

3. **Форматирование:**
   - Используй HTML-теги: <b> для заголовков, <i> для акцентов
   - Используй эмодзи для визуального разделения
   - Используй \\n для переносов строк (НЕ <br>)
   - Будь кратким, но информативным

4. **Важно:**
   - НЕ включай блоки, которые пусты (содержат "Нет..." или "На сегодня задач нет")
   - Используй разные формулировки для разнообразия
   - Будь естественным, не роботичным
   - Обращайся к пользователю по имени в приветствии
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
Сгенерируй финальное HTML-сообщение, строго следуя правилам. Будь естественным и дружелюбным.
"""
    return await _call_deepseek_api(system_prompt, user_prompt, is_json_output=False, temperature=0.5)


async def extract_habits_from_text(raw_text: str, current_user_datetime_iso: str) -> dict:
    system_prompt = f"""
Ты — AI-аналитик привычек. Твоя задача — извлечь из текста пользователя все желаемые привычки и их параметры.
Контекст: Текущая дата и время пользователя: `{current_user_datetime_iso}`.
Правила времени: "Утром" - 08:00, "Днем" - 14:00, "Вечером" - 20:00.
Правила дней недели: "По будням" -> MO,TU,WE,TH,FR. "По выходным" -> SA,SU.

Верни JSON-объект со списком привычек:
{{
  "habits": [
    {{
      "name": "Краткое название привычки (2-4 слова в инфинитиве, например 'Делать зарядку')",
      "frequency_rule": "Строка iCalendar RRULE (например, FREQ=DAILY или FREQ=WEEKLY;BYDAY=SA,SU)",
      "reminder_time": "Время в формате HH:MM"
    }}
  ]
}}

ПРАВИЛА АНАЛИЗА:
1.  "Каждый день" -> FREQ=DAILY.
2.  "Каждую неделю", "еженедельно" -> FREQ=WEEKLY. Если дни не указаны, не добавляй BYDAY.
3.  Если время не указано, но есть "утром", "вечером" и т.д., подставь время по умолчанию. Если времени нет совсем, верни null для reminder_time.
4.  Название привычки должно быть лаконичным и в инфинитиве.
"""
    user_prompt = f"Извлеки привычки из текста: \"{raw_text}\""
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