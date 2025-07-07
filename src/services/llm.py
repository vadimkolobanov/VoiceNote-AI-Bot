# src/services/llm.py
import asyncio
import json
import logging

import aiohttp
from ..core.config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME

logger = logging.getLogger(__name__)


def _parse_llm_json_response(response_text: str, original_text: str) -> dict:
    """
    Внутренняя утилита для безопасного парсинга JSON-ответа от LLM.
    Обрабатывает случаи, когда JSON обернут в markdown-блок.
    """
    # Удаляем markdown-обертку ```json ... ```, если она есть
    if response_text.strip().startswith("```json"):
        response_text = response_text.strip()[7:-3].strip()
    elif response_text.strip().startswith("```"):
        response_text = response_text.strip()[3:-3].strip()

    try:
        extracted_info = json.loads(response_text)
        if not isinstance(extracted_info, dict):
            logger.warning(f"LLM вернула JSON, но это не словарь: {extracted_info}")
            return {"error": "LLM returned non-dict JSON", "corrected_text": original_text}

        # Валидация: если LLM не вернула исправленный текст, используем оригинальный
        if not extracted_info.get("corrected_text"):
            logger.warning(
                f"LLM не вернула 'corrected_text' или поле пустое. Используется оригинальный текст. LLM JSON: {extracted_info}"
            )
            extracted_info["corrected_text"] = original_text
        return extracted_info

    except json.JSONDecodeError as e:
        logger.error(f"Ошибка декодирования JSON от LLM: {e}. Ответ LLM: {response_text[:500]}...")
        return {"error": "Failed to decode JSON from LLM", "corrected_text": original_text}
    except Exception as e:
        logger.error(f"Неожиданная ошибка при парсинге ответа LLM: {e}. Ответ LLM: {response_text[:500]}...")
        return {"error": f"Unexpected error: {str(e)}", "corrected_text": original_text}


async def enhance_text_with_llm(raw_text: str, current_user_datetime_iso: str) -> dict:
    """
    Отправляет текст в DeepSeek API для анализа и структурирования.

    :param raw_text: Необработанный текст от пользователя (например, после STT).
    :param current_user_datetime_iso: Текущая дата и время пользователя в формате ISO для корректного определения дат.
    :return: Словарь со структурированной информацией или словарь с ошибкой.
    """
    if not all([DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME]):
        logger.error("DeepSeek API не сконфигурирован. Пропуск обработки LLM.")
        return {"error": "DeepSeek API not configured", "corrected_text": raw_text}

    system_prompt = f"""
Ты — экспертный AI-ассистент, который обрабатывает сырой, транскрибированный русский текст и превращает его в краткую, действенную задачу. Твоя цель — очистить разговорную речь и извлечь основную суть в виде короткого заголовка.

Локальное время пользователя: `{current_user_datetime_iso}`.

**Твоя задача — вернуть JSON-объект со следующей структурой:**
{{
  "summary_text": "Короткий, понятный заголовок задачи. Максимум 1-7 слов. Это главный результат.",
  "corrected_text": "Полная, исправленная версия оригинального текста, сохраняющая все важные детали.",
  "category": "Категория заметки. По умолчанию 'Общее'. Для списков покупок используй 'Покупки'.",
  "items": [
    {{ "item_name": "название товара", "checked": false }}
  ],
  "dates_times": [
    {{
      "original_mention": "Как было упомянуто время/дата.",
      "absolute_datetime_start": "YYYY-MM-DDTHH:MM:SSZ"
    }}
  ],
  "recurrence_rule": "Строка iCalendar RRULE или null."
}}

**Правила для 'summary_text':**
- Это ДОЛЖЕН быть короткий, действенный заголовок (например, "Позвонить маме", "Заехать в автосервис").
- Для списков покупок — всегда "Список покупок".

**Правила для 'corrected_text':**
- Это должна быть полная, грамматически верная версия текста пользователя.
- Убери речевые артефакты, но сохрани все конкретные детали.

**Специальное правило для списков покупок:**
Если текст — это список товаров для покупки (например, "купить молоко, хлеб, яйца" или "докупить яйца"), сделай следующее:
1. Установи "category" в "Покупки".
2. Заполни поле "items" массивом объектов. Каждый объект должен содержать "item_name" (строка) и "checked" (булево, по умолчанию false).
3. "summary_text" должен быть "Список покупок".
4. Массив "items" не должен быть пустым. Если не удалось извлечь ни одного товара, считай это обычной заметкой.

**Пример списка покупок:**
- Ввод пользователя: "надо будет купить хлеб яйца и молоко"
- Твой JSON-ответ:
  {{
    "summary_text": "Список покупок",
    "corrected_text": "Нужно купить: хлеб, яйца, молоко.",
    "category": "Покупки",
    "items": [
      {{ "item_name": "Хлеб", "checked": false }},
      {{ "item_name": "Яйца", "checked": false }},
      {{ "item_name": "Молоко", "checked": false }}
    ],
    "dates_times": [],
    "recurrence_rule": null
  }}
купить и докупить а так же приобрести - это одно и тоже и значит купить

Все даты и время ДОЛЖНЫ быть в формате UTC ISO 8601, заканчивающемся на 'Z'. Если дат нет, `dates_times` должен быть пустым массивом. Если это не список, `items` должен быть пустым массивом.
"""

    user_prompt = f"Проанализируй следующий текст голосовой заметки (на русском):\n\n\"{raw_text}\""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": DEEPSEEK_MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 2048,
    }

    logger.debug(f"Отправка запроса в DeepSeek. Текущее время пользователя: {current_user_datetime_iso}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=90)
            ) as resp:
                response_text = await resp.text()

                if resp.status == 200:
                    # DeepSeek API возвращает JSON, внутри которого в 'content' лежит строка, которую тоже надо парсить как JSON
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError as e:
                        logger.error(f"Не удалось декодировать внешний JSON от DeepSeek: {e}. Ответ: {response_text[:500]}")
                        return {"error": "DeepSeek outer JSON decode error", "corrected_text": raw_text}

                    if 'choices' in response_data and response_data['choices']:
                        message_content_str = response_data['choices'][0].get('message', {}).get('content')
                        if message_content_str:
                            return _parse_llm_json_response(message_content_str, raw_text)
                        else:
                            error_msg = "В ответе DeepSeek отсутствует 'message.content'."
                            logger.error(f"{error_msg} Полный ответ: {response_data}")
                            return {"error": error_msg, "corrected_text": raw_text}
                    else:
                        error_msg = "Неверный формат ответа DeepSeek (отсутствует поле 'choices')."
                        logger.error(f"{error_msg} Полный ответ: {response_text[:500]}")
                        return {"error": error_msg, "corrected_text": raw_text}
                else:
                    error_message = f"Ошибка API DeepSeek, статус: {resp.status}"
                    logger.error(f"{error_message}. Ответ: {response_text[:500]}")
                    return {"error": error_message, "corrected_text": raw_text}

    except aiohttp.ClientError as e:
        logger.error(f"Ошибка соединения с API DeepSeek: {e}")
        return {"error": "Connection error to LLM API", "corrected_text": raw_text}
    except asyncio.TimeoutError:
        logger.error("Таймаут запроса к API DeepSeek.")
        return {"error": "Request to LLM timed out", "corrected_text": raw_text}
    except Exception as e:
        logger.exception("Неожиданная ошибка во время запроса к DeepSeek.")
        return {"error": f"Unexpected exception: {e}", "corrected_text": raw_text}