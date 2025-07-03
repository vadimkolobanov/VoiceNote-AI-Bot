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
            # Исключение для списков покупок, т.к. они не создают новые заметки, а обновляют одну
            if 'купить' not in text_to_process.lower() and 'покупки' not in text_to_process.lower():
                return False, f"⚠️ Достигнут лимит в {MAX_NOTES_MVP} заметок. Чтобы добавить новую, удалите старую.", None, False

    if not DEEPSEEK_API_KEY_EXISTS:
        # Логика без LLM остается прежней
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
        # При ошибке LLM просто создаем обычную заметку
        category_to_save = "Общее"
        summary_text_to_save = text_to_process[:80]
        corrected_text_to_save = text_to_process
    else:
        llm_analysis_json = llm_result_dict
        summary_text_to_save = llm_result_dict.get("summary_text", text_to_process[:80])
        corrected_text_to_save = llm_result_dict.get("corrected_text", text_to_process)
        category_to_save = llm_result_dict.get("category", "Общее")

    due_date_obj = None
    if llm_analysis_json and llm_analysis_json.get("dates_times"):
        try:
            date_time_info = llm_analysis_json["dates_times"][0]
            due_date_str_utc = date_time_info.get("absolute_datetime_start")
            if due_date_str_utc:
                dt_obj_utc = datetime.fromisoformat(due_date_str_utc.replace('Z', '+00:00'))
                is_time_ambiguous = (dt_obj_utc.time() == time(0, 0))
                if is_time_ambiguous:
                    default_time = user_profile.get('default_reminder_time', time(9, 0)) if is_vip else time(12, 0)
                    local_due_date = datetime.combine(dt_obj_utc.date(), default_time)
                    due_date_obj = user_tz.localize(local_due_date).astimezone(pytz.utc)
                else:
                    due_date_obj = dt_obj_utc
        except (ValueError, IndexError, KeyError) as e:
            logger.error(f"Ошибка парсинга даты из LLM: {e}")

    # --- НОВАЯ ЛОГИКА ОБРАБОТКИ СПИСКОВ ПОКУПОК ---
    if category_to_save == "Покупки":
        new_items = llm_analysis_json.get("items", [])
        if not new_items:  # Если LLM определил как покупки, но не нашел товаров, делаем обычной заметкой
            category_to_save = "Общее"
        else:
            shopping_note = await db.get_or_create_active_shopping_list_note(telegram_id)
            if not shopping_note:
                return False, "❌ Не удалось обработать список покупок. Попробуйте снова.", None, False

            # Добавляем новые товары к существующим
            existing_items = shopping_note.get("llm_analysis_json", {}).get("items", [])
            existing_item_names = {item['item_name'].lower() for item in existing_items}

            items_to_add = [item for item in new_items if item['item_name'].lower() not in existing_item_names]
            existing_items.extend(items_to_add)

            shopping_note["llm_analysis_json"]["items"] = existing_items
            await db.update_note_llm_json(shopping_note['note_id'], shopping_note["llm_analysis_json"], telegram_id)

            # Обновляем дату, если она была в запросе
            if due_date_obj:
                await db.update_note_due_date(shopping_note['note_id'], due_date_obj)
                shopping_note['due_date'] = due_date_obj
                add_reminder_to_scheduler(bot, {**shopping_note, **user_profile})

            added_count = len(items_to_add)
            user_message = f"✅ Добавлено в ваш список покупок: {added_count} поз."
            return True, user_message, shopping_note, False
    # ---------------------------------------------------

    # Стандартная логика для всех остальных заметок
    recurrence_rule = llm_analysis_json.get("recurrence_rule") if llm_analysis_json else None
    if recurrence_rule and not is_vip:
        recurrence_rule = None
        warning_message += f"\n\n⭐ Повторяющиеся задачи — VIP-функция. Заметка сохранена как разовая."

    note_id = await db.create_note(
        telegram_id=telegram_id, summary_text=summary_text_to_save,
        corrected_text=corrected_text_to_save, original_stt_text=text_to_process,
        llm_analysis_json=llm_analysis_json, original_audio_telegram_file_id=audio_file_id,
        note_taken_at=note_taken_at, due_date=due_date_obj,
        recurrence_rule=recurrence_rule, category=category_to_save
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