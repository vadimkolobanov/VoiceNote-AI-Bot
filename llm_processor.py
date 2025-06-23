# llm_processor.py
import asyncio
import json
import logging
from datetime import datetime

import aiohttp
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME

logger = logging.getLogger(__name__)


def _parse_llm_json_response(response_text: str, original_text: str) -> dict:
    """
    Безопасно парсит JSON-ответ от LLM.
    Если LLM вернула некорректный JSON, пытается его "починить".
    """
    # Улучшение: Иногда LLM оборачивает JSON в ```json ... ```. Удаляем эту обертку.
    if response_text.strip().startswith("```json"):
        response_text = response_text.strip()[7:-3]

    try:
        # Пытаемся загрузить JSON
        extracted_info = json.loads(response_text)
        if not isinstance(extracted_info, dict):
            logger.warning(f"LLM returned JSON, but it's not a dictionary: {extracted_info}")
            return {"error": "LLM returned non-dict JSON", "corrected_text": original_text}

        # Улучшение: Если corrected_text пустой или отсутствует, используем исходный текст.
        # Это делает систему более устойчивой к ошибкам LLM.
        if not extracted_info.get("corrected_text"):
            logger.warning(
                f"LLM did not return 'corrected_text' or it was empty. Using original text. Full LLM JSON: {extracted_info}"
            )
            extracted_info["corrected_text"] = original_text
        return extracted_info

    except json.JSONDecodeError as e:
        logger.error(f"LLM JSONDecodeError: {e}. LLM Response: {response_text[:500]}...")
        # Возвращаем ошибку и исходный текст, чтобы система не падала.
        return {"error": "Failed to decode JSON from LLM", "corrected_text": original_text}
    except Exception as e:
        logger.error(f"Unexpected error parsing LLM response: {e}. LLM Response: {response_text[:500]}...")
        return {"error": f"Unexpected error: {str(e)}", "corrected_text": original_text}


async def enhance_text_with_llm(
        raw_text: str,
        current_user_datetime_iso: str
) -> dict:
    """
    Обращается к API DeepSeek для анализа текста и извлечения структурированных данных.
    """
    # Проверка конфигурации API
    if not all([DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME]):
        logger.error("DeepSeek API is not fully configured. Skipping LLM processing.")
        return {"error": "DeepSeek API not configured", "corrected_text": raw_text}

    # --- УЛУЧШЕННЫЙ И БОЛЕЕ СТРОГИЙ СИСТЕМНЫЙ ПРОМПТ ---
    # Решает проблему с округлением времени и делает инструкции более четкими.
    system_prompt = f"""You are an AI assistant specialized in processing transcribed voice notes in Russian.
Your task is to return a single, valid JSON object based on the user's text. You must be extremely precise with time calculations.

JSON Structure:
{{
  "corrected_text": "...",
  "task_description": "...",
  "event_description": "...",
  "dates_times": [
    {{
      "original_mention": "How the date/time was mentioned in the text.",
      "absolute_datetime_start": "The calculated absolute time in UTC, in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ).",
      "absolute_datetime_end": "..."
    }}
  ],
  "people_mentioned": [...],
  "locations_mentioned": [...],
  "recurrence_rule": "The iCalendar RRULE string if the note is recurring, otherwise null."
}}

**Date/Time Calculation Rules (VERY IMPORTANT):**
- **The exact current time is:** `{current_user_datetime_iso}`. This is the user's local time.
- **You MUST use this provided time as the precise starting point for all relative time calculations (like "in two hours" or "in 15 minutes").**
- **DO NOT round the current time.** If the time is 18:48, use 18:48, not 18:50. Your calculations must be exact to the minute.
- **Output Format:** All date/time values in the final JSON MUST be in UTC timezone, ending with 'Z'.
- **Ambiguous Time:** If a user says "at 8 o'clock" without specifying a date, assume they mean "today at 8 o'clock".
- **Date without time:** If a date is mentioned without a time (e.g., "on Friday"), use T00:00:00Z for the time part as a placeholder.

**Recurrence Rule (RRULE) Generation:**
- If the user says "каждый день", use "FREQ=DAILY".
- If "каждую пятницу", use "FREQ=WEEKLY;BYDAY=FR".
- If "каждый месяц 15 числа", use "FREQ=MONTHLY;BYMONTHDAY=15".
- If "каждые 3 недели", use "FREQ=WEEKLY;INTERVAL=3".
- If the event is not recurring, the value for "recurrence_rule" MUST be null.
"""
    # -----------------------------------------------------------------

    user_prompt = f"Analyze the following voice note text (in Russian):\n\n\"{raw_text}\""

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
        "temperature": 0.1,  # Низкая температура для большей предсказуемости
        "max_tokens": 2048,
    }

    logger.debug(f"Sending request to DeepSeek. Current User Time: {current_user_datetime_iso}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(DEEPSEEK_API_URL, headers=headers, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=90)) as resp:
                response_text = await resp.text()

                if resp.status == 200:
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode outer JSON from DeepSeek: {e}. Response: {response_text[:500]}")
                        return {"error": "DeepSeek outer JSON decode error", "corrected_text": raw_text}

                    if 'choices' in response_data and response_data['choices']:
                        message_content_str = response_data['choices'][0].get('message', {}).get('content')
                        if message_content_str:
                            # Парсим внутренний JSON с помощью нашей безопасной функции
                            parsed_result = _parse_llm_json_response(message_content_str, raw_text)
                            return parsed_result
                        else:
                            error_msg = "DeepSeek response 'message.content' is missing or empty."
                            logger.error(error_msg)
                            return {"error": error_msg, "corrected_text": raw_text}
                    else:
                        error_msg = "Invalid DeepSeek response (no 'choices' field)."
                        logger.error(f"{error_msg} Full response: {response_text[:500]}")
                        return {"error": error_msg, "corrected_text": raw_text}
                else:
                    # Улучшенная обработка ошибок API
                    error_message = f"DeepSeek API error status: {resp.status}"
                    logger.error(f"{error_message}. Response: {response_text[:500]}")
                    try:
                        error_details = json.loads(response_text)
                        if isinstance(error_details, dict) and "error" in error_details:
                            err_obj = error_details["error"]
                            if isinstance(err_obj, dict) and "message" in err_obj:
                                error_message += f": {err_obj['message']}"
                    except (json.JSONDecodeError, TypeError):
                        pass  # Не удалось извлечь детали, используем общую ошибку
                    return {"error": error_message, "corrected_text": raw_text}

    except aiohttp.ClientError as e:
        logger.error(f"DeepSeek API connection error: {e}")
        return {"error": "Connection error to LLM API", "corrected_text": raw_text}
    except asyncio.TimeoutError:
        logger.error("DeepSeek API request timed out.")
        return {"error": "Request to LLM timed out", "corrected_text": raw_text}
    except Exception as e:
        logger.exception("An unexpected error occurred during DeepSeek request.")
        return {"error": f"Unexpected exception: {e}", "corrected_text": raw_text}