# services/note_creator.py
import logging
from datetime import datetime, time
import pytz

from aiogram import Bot
from aiogram.utils.markdown import hbold

import database_setup as db
from config import DEEPSEEK_API_KEY_EXISTS
from llm_processor import enhance_text_with_llm
from services.scheduler import add_reminder_to_scheduler

logger = logging.getLogger(__name__)


async def process_and_save_note(
        bot: Bot,
        telegram_id: int,
        text_to_process: str,
        audio_file_id: str | None = None
) -> tuple[bool, str, dict | None]:
    """
    Универсальная функция для обработки текста, анализа и сохранения заметки.
    Возвращает (успех, текст_ответа_пользователю, созданная_заметка).
    """
    user_profile = await db.get_user_profile(telegram_id)
    if not user_profile:
        return False, "Не удалось найти ваш профиль.", None

    if not DEEPSEEK_API_KEY_EXISTS:
        note_id = await db.create_note(
            telegram_id=telegram_id,
            corrected_text=text_to_process,
            original_stt_text=text_to_process,
            original_audio_telegram_file_id=audio_file_id,
            note_taken_at=datetime.now(pytz.utc)
        )
        if note_id:
            note = await db.get_note_by_id(note_id, telegram_id)
            return True, f"✅ Заметка #{note_id} сохранена (без AI-анализа).", note
        else:
            return False, "❌ Ошибка при сохранении заметки.", None

    user_timezone_str = user_profile.get('timezone', 'UTC')
    user_tz = pytz.timezone(user_timezone_str)
    current_user_dt = datetime.now(user_tz)
    current_user_dt_iso = current_user_dt.isoformat()
    is_vip = user_profile.get('is_vip', False)

    llm_result_dict = await enhance_text_with_llm(text_to_process, current_user_datetime_iso=current_user_dt_iso)

    if "error" in llm_result_dict:
        logger.error(f"LLM error for user {telegram_id}: {llm_result_dict['error']}")
        note_id = await db.create_note(telegram_id=telegram_id, corrected_text=text_to_process)
        if note_id:
            note = await db.get_note_by_id(note_id, telegram_id)
            msg = "⚠️ Заметка сохранена, но при AI-анализе произошла ошибка. Текст сохранен как есть."
            return True, msg, note
        return False, "Ошибка и при AI-анализе, и при сохранении.", None

    corrected_text_to_save = llm_result_dict.get("corrected_text", text_to_process)
    due_date_obj = None
    recurrence_rule = llm_result_dict.get("recurrence_rule") if is_vip else None

    if llm_result_dict.get("dates_times"):
        try:
            due_date_str_utc = llm_result_dict["dates_times"][0].get("absolute_datetime_start")
            if due_date_str_utc:
                dt_obj_utc = datetime.fromisoformat(due_date_str_utc.replace('Z', '+00:00'))
                if dt_obj_utc.time() == time(0, 0):
                    default_time = user_profile.get('default_reminder_time', time(9, 0)) if is_vip else time(12, 0)
                    local_due_date = datetime.combine(dt_obj_utc.date(), default_time)
                    due_date_obj = user_tz.localize(local_due_date).astimezone(pytz.utc)
                else:
                    due_date_obj = dt_obj_utc
        except Exception as e:
            logger.error(f"Ошибка парсинга даты из LLM: {e}")

    note_id = await db.create_note(
        telegram_id=telegram_id,
        corrected_text=corrected_text_to_save,
        original_stt_text=text_to_process,
        llm_analysis_json=llm_result_dict,
        original_audio_telegram_file_id=audio_file_id,
        note_taken_at=datetime.now(pytz.utc),
        due_date=due_date_obj,
        recurrence_rule=recurrence_rule
    )

    if not note_id:
        return False, "❌ Ошибка при сохранении заметки в базу.", None

    new_note = await db.get_note_by_id(note_id, telegram_id)
    if due_date_obj:
        add_reminder_to_scheduler(bot, {**new_note, **user_profile})

    return True, f"✅ Заметка #{hbold(note_id)} успешно сохранена!", new_note