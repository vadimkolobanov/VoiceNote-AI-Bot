# llm_processor.py
import asyncio
import json
import logging
from datetime import datetime

import aiohttp
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME

logger = logging.getLogger(__name__)


def _parse_llm_json_response(response_text: str, original_text: str) -> dict:
    if response_text.strip().startswith("```json"):
        response_text = response_text.strip()[7:-3]

    try:
        extracted_info = json.loads(response_text)
        if not isinstance(extracted_info, dict):
            logger.warning(f"LLM returned JSON, but it's not a dictionary: {extracted_info}")
            return {"error": "LLM returned non-dict JSON", "corrected_text": original_text}

        if not extracted_info.get("corrected_text"):
            logger.warning(
                f"LLM did not return 'corrected_text' or it was empty. Using original text. Full LLM JSON: {extracted_info}"
            )
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
        current_user_datetime_iso: str
) -> dict:
    if not all([DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME]):
        logger.error("DeepSeek API is not fully configured. Skipping LLM processing.")
        return {"error": "DeepSeek API not configured", "corrected_text": raw_text}

    system_prompt = f"""You are an expert AI assistant that processes raw, transcribed Russian text into a concise, actionable task. Your goal is to clean up messy speech and extract the core task into a short summary.

The user's local time is: `{current_user_datetime_iso}`.

**Your task is to return a JSON object with the following structure:**
{{
  "summary_text": "A short, clear task title. Max 1-7 words. This is the main output.",
  "corrected_text": "The full, cleaned-up version of the original text, preserving all important details.",
  "dates_times": [
    {{
      "original_mention": "How the date/time was mentioned.",
      "absolute_datetime_start": "YYYY-MM-DDTHH:MM:SSZ"
    }}
  ],
  "recurrence_rule": "iCalendar RRULE string or null."
}}

**Rules for 'summary_text':**
- It MUST be a short, actionable title (e.g., "Позвонить маме", "Купить продукты", "Заехать в автосервис (стук)").
- Remove all filler words ("так", "ну", "значит", "короче").
- If the user provides context, add it concisely in parentheses. Example: "проверить почту насчет билетов" -> "Проверить почту (билеты)".
- It should be in the infinitive form if it's a task.

**Rules for 'corrected_text':**
- This should be the full, grammatically correct version of the user's text.
- Clean up speech disfluencies but preserve all specific details that might be lost in the summary.

**Example:**
- **User input:** "Так, короче, это я себе, надо не забыть в пятницу вечером заехать в сервис, а то у меня там что-то стучит под капотом"
- **Your JSON output:**
  {{
    "summary_text": "Заехать в автосервис (стук под капотом)",
    "corrected_text": "В пятницу вечером нужно заехать в автосервис, так как что-то стучит под капотом.",
    "dates_times": [],
    "recurrence_rule": null
  }}

All datetimes MUST be in UTC ISO 8601 format ending with 'Z'.
"""

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
        "temperature": 0.1,
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
                            return _parse_llm_json_response(message_content_str, raw_text)
                        else:
                            error_msg = "DeepSeek response 'message.content' is missing or empty."
                            logger.error(error_msg)
                            return {"error": error_msg, "corrected_text": raw_text}
                    else:
                        error_msg = "Invalid DeepSeek response (no 'choices' field)."
                        logger.error(f"{error_msg} Full response: {response_text[:500]}")
                        return {"error": error_msg, "corrected_text": raw_text}
                else:
                    error_message = f"DeepSeek API error status: {resp.status}"
                    logger.error(f"{error_message}. Response: {response_text[:500]}")
                    try:
                        error_details = json.loads(response_text)
                        if isinstance(error_details, dict) and "error" in error_details:
                            err_obj = error_details["error"]
                            if isinstance(err_obj, dict) and "message" in err_obj:
                                error_message += f": {err_obj['message']}"
                    except (json.JSONDecodeError, TypeError):
                        pass
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