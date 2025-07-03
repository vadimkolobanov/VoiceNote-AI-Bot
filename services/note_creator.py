# services/note_creator.py
import logging
from datetime import datetime, time
import pytz

from aiogram import Bot
from aiogram.utils.markdown import hbold, hcode

import database_setup as db
from config import DEEPSEEK_API_KEY_EXISTS, MAX_NOTES_MVP
from llm_processor import enhance_text_with_llm
from services.scheduler import add_reminder_to_scheduler
from services.tz_utils import format_datetime_for_user

logger = logging.getLogger(__name__)


async def process_and_save_note(
        bot: Bot,
        telegram_id: int,
        text_to_process: str,
        audio_file_id: str | None = None,
        message_date: datetime | None = None
) -> tuple[bool, str, dict | None, bool]:
    user_profile = await db.get_user_profile(telegram_id)
    if not user_profile:
        return False, "Не удалось найти ваш профиль. Пожалуйста, нажмите /start.", None, False

    is_vip = user_profile.get('is_vip', False)
    note_taken_at = message_date or datetime.now(pytz.utc)

    if not is_vip:
        active_notes_count = await db.count_active_notes_for_user(telegram_id)
        if active_notes_count >= MAX_NOTES_MVP:
            return False, f"⚠️ Достигнут лимит в {MAX_NOTES_MVP} заметок. Чтобы добавить новую, удалите старую.", None, False

    if not DEEPSEEK_API_KEY_EXISTS:
        note_id = await db.create_note(
            telegram_id=telegram_id,
            summary_text=text_to_process[:80],
            corrected_text=text_to_process,
            original_stt_text=text_to_process,
            original_audio_telegram_file_id=audio_file_id,
            note_taken_at=note_taken_at
        )
        if note_id:
            note = await db.get_note_by_id(note_id, telegram_id)
            user_message = f"✅ Заметка #{hbold(str(note_id))} сохранена (без AI-анализа)."
            return True, user_message, note, False
        else:
            return False, "❌ Ошибка при сохранении заметки.", None, False

    user_timezone_str = user_profile.get('timezone', 'UTC')
    user_tz = pytz.timezone(user_timezone_str)
    current_user_dt = datetime.now(user_tz)
    current_user_dt_iso = current_user_dt.isoformat()

    llm_result_dict = await enhance_text_with_llm(text_to_process, current_user_datetime_iso=current_user_dt_iso)
    llm_analysis_json = None
    warning_message = ""

    if "error" in llm_result_dict:
        logger.error(f"LLM error for user {telegram_id}: {llm_result_dict['error']}")
        summary_text_to_save = text_to_process[:80]
        corrected_text_to_save = text_to_process
        warning_message = "\n\n⚠️ Заметка сохранена, но при AI-анализе произошла ошибка. Текст сохранен как есть."
    else:
        llm_analysis_json = llm_result_dict
        summary_text_to_save = llm_result_dict.get("summary_text", text_to_process[:80])
        corrected_text_to_save = llm_result_dict.get("corrected_text", text_to_process)


    due_date_obj = None
    recurrence_rule = llm_analysis_json.get("recurrence_rule") if llm_analysis_json else None

    if recurrence_rule and not is_vip:
        recurrence_rule = None
        warning_message += f"\n\n⭐ Повторяющиеся задачи — это VIP-функция. Заметка сохранена как разовая."

    if llm_analysis_json and llm_analysis_json.get("dates_times"):
        try:
            due_date_str_utc = llm_analysis_json["dates_times"][0].get("absolute_datetime_start")
            if due_date_str_utc:
                dt_obj_utc = datetime.fromisoformat(due_date_str_utc.replace('Z', '+00:00'))

                is_time_ambiguous = (dt_obj_utc.time() == time(0, 0))
                if is_time_ambiguous:
                    default_time = user_profile.get('default_reminder_time', time(9, 0)) if is_vip else time(12, 0)
                    local_due_date = datetime.combine(dt_obj_utc.date(), default_time)
                    due_date_obj = user_tz.localize(local_due_date).astimezone(pytz.utc)
                else:
                    due_date_obj = dt_obj_utc
        except Exception as e:
            logger.error(f"Ошибка парсинга даты из LLM: {e}")

    note_id = await db.create_note(
        telegram_id=telegram_id,
        summary_text=summary_text_to_save,
        corrected_text=corrected_text_to_save,
        original_stt_text=text_to_process,
        llm_analysis_json=llm_analysis_json,
        original_audio_telegram_file_id=audio_file_id,
        note_taken_at=note_taken_at,
        due_date=due_date_obj,
        recurrence_rule=recurrence_rule
    )

    if not note_id:
        return False, "❌ Ошибка при сохранении заметки в базу.", None, False

    new_note = await db.get_note_by_id(note_id, telegram_id)
    if due_date_obj:
        add_reminder_to_scheduler(bot, {**new_note, **user_profile})

    user_message = f"✅ Заметка #{hbold(str(note_id))} успешно сохранена!{warning_message}"
    date_info = ""
    needs_tz_prompt = False

    if new_note.get('due_date'):
        formatted_date = format_datetime_for_user(new_note['due_date'], user_timezone_str)
        date_info = f"\n🗓️ Срок: {formatted_date}"
        if user_timezone_str == 'UTC':
            needs_tz_prompt = True
            date_info += f"\n\n{hbold('⚠️ Важно!')} Ваше напоминание установлено по UTC. Чтобы оно сработало вовремя, пожалуйста, укажите ваш часовой пояс."

    full_response = f"{user_message}\n\n{hcode(new_note.get('summary_text', new_note['corrected_text']))}{date_info}"

    return True, full_response, new_note, needs_tz_prompt