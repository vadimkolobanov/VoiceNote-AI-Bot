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

    system_prompt = f"""You are a hyper-precise AI assistant for processing Russian text notes into a structured JSON. Your primary goal is absolute accuracy in date and time calculations.

The user's exact local time of making this note is: `{current_user_datetime_iso}`.
This is the single source of truth for all time calculations.

**CRITICAL CALCULATION RULES:**
1.  **Use the Provided Time:** ALL relative time calculations (e.g., "через 5 минут", "через час", "завтра") MUST be based *strictly* on the provided time: `{current_user_datetime_iso}`.
2.  **NO ROUNDING:** Do not round the current time. If it's 23:56, calculate from 23:56.
3.  **Midnight/Date Transition:** Be extremely careful with calculations that cross midnight.
    - If the current time is `2024-07-03T23:56:00+03:00` and the user says "через 5 минут", the result is `2024-07-04T00:01:00+03:00`. The **YEAR** and **MONTH** do not change unless the transition crosses the end of a month or year.
    - If the user says "завтра в 10", it means tomorrow at 10:00 relative to the provided date.
4.  **Date without Time:** If a date is given without a time (e.g., "в пятницу"), the time part MUST be `T00:00:00Z`.
5.  **Final Output Format:** All datetimes in the final JSON MUST be converted to UTC and formatted as `YYYY-MM-DDTHH:MM:SSZ`.

**JSON Structure:**
{{
  "corrected_text": "...",
  "dates_times": [
    {{
      "original_mention": "How the date/time was mentioned in the text.",
      "absolute_datetime_start": "YYYY-MM-DDTHH:MM:SSZ"
    }}
  ],
  "recurrence_rule": "The iCalendar RRULE string or null."
}}

You MUST return only the valid JSON object.
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
                    response_data = json.loads(response_text)
                    if 'choices' in response_data and response_data['choices']:
                        message_content_str = response_data['choices'][0].get('message', {}).get('content')
                        if message_content_str:
                            return _parse_llm_json_response(message_content_str, raw_text)

                    error_msg = "Invalid DeepSeek response structure."
                    logger.error(f"{error_msg} Full response: {response_text[:500]}")
                    return {"error": error_msg, "corrected_text": raw_text}
                else:
                    error_message = f"DeepSeek API error status: {resp.status}"
                    logger.error(f"{error_message}. Response: {response_text[:500]}")
                    return {"error": error_message, "corrected_text": raw_text}

    except Exception as e:
        logger.exception("An unexpected error occurred during DeepSeek request.")
        return {"error": f"Unexpected exception: {e}", "corrected_text": raw_text}