# llm_processor.py
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
import os

import aiohttp
from dotenv import load_dotenv

load_dotenv()
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL_NAME = "deepseek-chat"

logger = logging.getLogger(__name__)


def _get_current_datetime_utc_iso() -> str:
    """Возвращает текущую дату и время в UTC в формате ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def _parse_llm_json_response(response_text: str, original_text: str) -> dict:
    # ... (эта функция без изменений) ...
    try:
        extracted_info = json.loads(response_text)
        if not isinstance(extracted_info, dict):
            logger.warning(f"LLM returned JSON, but it's not a dictionary: {extracted_info}")
            return {"error": "LLM returned non-dict JSON", "corrected_text": extracted_info.get("corrected_text", original_text)}
        if "corrected_text" not in extracted_info or not extracted_info["corrected_text"]:
            logger.warning(f"LLM did not return 'corrected_text' or it was empty. Using original text. Full LLM JSON: {extracted_info}")
            extracted_info["corrected_text"] = original_text
        return extracted_info
    except json.JSONDecodeError as e:
        logger.error(f"LLM JSONDecodeError: {e}. LLM Response: {response_text[:500]}...")
        return {"error": "Failed to decode JSON from LLM", "corrected_text": original_text}
    except Exception as e:
        logger.error(f"Unexpected error parsing LLM response: {e}. LLM Response: {response_text[:500]}...")
        return {"error": f"Unexpected error: {str(e)}", "corrected_text": original_text}


async def enhance_text_with_llm(
    raw_text: str,
    api_key: str = DEEPSEEK_API_KEY,
    api_url: str = DEEPSEEK_API_URL,
    model_name: str = DEEPSEEK_MODEL_NAME
) -> dict:
    if not api_key:
        # ... (проверки без изменений) ...
        logger.error("DeepSeek API key is not configured. Set DEEPSEEK_API_KEY environment variable.")
        return {"error": "DeepSeek API key not configured", "corrected_text": raw_text}
    if not api_url or not model_name:
        logger.error("DeepSeek API URL or Model Name is not configured.")
        return {"error": "DeepSeek API URL or Model Name not configured", "corrected_text": raw_text}

    # <--- ИСПОЛЬЗУЕМ НОВУЮ ФУНКЦИЮ И ОБНОВЛЯЕМ ПРОМПТ --->
    current_datetime_utc_str = _get_current_datetime_utc_iso()
    system_prompt = f"""You are an AI assistant specialized in processing transcribed voice notes in Russian.
Your tasks are:
1. Correct transcription errors, improve grammar, and punctuation of the provided Russian text.
2. Analyze the corrected text and extract structured information.
3. Return the output ONLY as a single, valid JSON object. Do NOT include any explanatory text before or after the JSON.

The JSON object must strictly follow this structure:
{{
  "corrected_text": "...",
  "task_description": "...",
  "event_description": "...",
  "dates_times": [
    {{
      "original_mention": "Как дата/время было упомянуто в тексте.",
      "absolute_datetime_start": "Рассчитанное абсолютное время в UTC, в формате ISO 8601 (YYYY-MM-DDTHH:MM:SSZ). Это поле ОБЯЗАТЕЛЬНО должно быть в UTC.",
      "absolute_datetime_end": "..."
    }}
  ],
  "people_mentioned": [...],
  "locations_mentioned": [...],
  "implied_intent": ["..."]
}}

IMPORTANT:
- Current date and time for reference is: {current_datetime_utc_str}. This is the point in time from which all relative times ('in 2 minutes', 'tomorrow at 5 PM') should be calculated.
- All absolute date/time values in the output JSON ('absolute_datetime_start', 'absolute_datetime_end') MUST be calculated and returned in UTC timezone, ending with 'Z'.
- If a time is mentioned without a date (e.g., 'at 7 PM'), assume it's for the current day or the next day if that time has already passed today in UTC.
- If a date is mentioned without a time (e.g., 'on Friday'), use T00:00:00Z for the time part.
- If no date or time is mentioned in the text, the "dates_times" array should be empty.
- If a date/time is mentioned, the "implied_intent" array MUST include 'create_reminder'.
"""
    user_prompt = f"Проанализируй следующий текст голосовой заметки (он на русском языке):\n\n\"{raw_text}\""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2, # Снижаем температуру для большей точности в датах
        "max_tokens": 2048,
    }

    logger.debug(f"Sending request to DeepSeek. Current UTC time for prompt: {current_datetime_utc_str}")
    try:
        # ... (остальной код функции без изменений) ...
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=90)) as resp:
                response_text = await resp.text()
                if resp.status == 200:
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode outer JSON from DeepSeek: {e}. Response: {response_text[:500]}")
                        return {"error": f"DeepSeek outer JSON decode error: {e}", "corrected_text": raw_text, "raw_llm_response": response_text}

                    if 'choices' in response_data and response_data['choices']:
                        message_content_str = response_data['choices'][0].get('message', {}).get('content')
                        if message_content_str:
                            parsed_result = _parse_llm_json_response(message_content_str, raw_text)
                            parsed_result["raw_llm_response_content"] = message_content_str
                            return parsed_result
                        else:
                            logger.error("DeepSeek response 'message.content' is missing or empty.")
                            error_info = response_data.get("error")
                            err_msg = f"DeepSeek 'message.content' is missing. API Error: {error_info.get('message', str(error_info)) if error_info else 'N/A'}"
                            return {"error": err_msg, "corrected_text": raw_text, "raw_llm_response": response_text}
                    else:
                        error_info = response_data.get("error")
                        err_msg = f"Invalid DeepSeek response (no 'choices'). API Error: {error_info.get('message', str(error_info)) if error_info else 'N/A'}"
                        logger.error(f"{err_msg} Full response: {response_text[:500]}")
                        return {"error": err_msg, "corrected_text": raw_text, "raw_llm_response": response_text}
                else:
                    logger.error(f"DeepSeek API request failed with status {resp.status}: {response_text[:500]}")
                    error_message = f"DeepSeek API error {resp.status}"
                    try:
                        error_details = json.loads(response_text)
                        if isinstance(error_details, dict) and "error" in error_details:
                           err_obj = error_details["error"]
                           if isinstance(err_obj, dict) and "message" in err_obj: error_message += f": {err_obj['message']}"
                           elif isinstance(err_obj, str): error_message += f": {err_obj}"
                    except json.JSONDecodeError: error_message += f" - {response_text[:200]}"
                    return {"error": error_message, "corrected_text": raw_text, "raw_llm_response": response_text}
    except aiohttp.ClientConnectorError as e:
        logger.error(f"DeepSeek API connection error: {e}")
        return {"error": f"Connection error: {e}", "corrected_text": raw_text}
    except asyncio.TimeoutError:
        logger.error("DeepSeek API request timed out.")
        return {"error": "Request to DeepSeek timed out", "corrected_text": raw_text}
    except Exception as e:
        logger.exception("An unexpected error occurred during DeepSeek request.")
        return {"error": f"Unexpected exception: {e}", "corrected_text": raw_text}