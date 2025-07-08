# src/bot/modules/notes/services.py
import logging
from datetime import datetime, time
import pytz

from aiogram import Bot
from aiogram.utils.markdown import hbold, hcode

from ....database import note_repo, user_repo
from ....core.config import DEEPSEEK_API_KEY_EXISTS, MAX_NOTES_MVP
from ....services.llm import enhance_text_with_llm
from ....services.scheduler import add_reminder_to_scheduler
from ....services.tz_utils import format_datetime_for_user

logger = logging.getLogger(__name__)


async def process_and_save_note(
        bot: Bot,
        telegram_id: int,
        text_to_process: str,
        audio_file_id: str | None = None,
        message_date: datetime | None = None
) -> tuple[bool, str, dict | None, bool]:
    """
    Главная сервисная функция для обработки текста, анализа и сохранения заметки.
    :return: (успех, сообщение_пользователю, созданная_заметка, нужен_ли_запрос_про_таймзону)
    """
    user_profile = await user_repo.get_user_profile(telegram_id)
    if not user_profile:
        return False, "Не удалось найти ваш профиль. Пожалуйста, нажмите /start.", None, False

    is_vip = user_profile.get('is_vip', False)

    # Проверка лимита для не-VIP пользователей
    if not is_vip:
        # Исключение для списков покупок, они обновляют одну и ту же заметку
        is_potential_shopping_list = 'купить' in text_to_process.lower() or 'покупки' in text_to_process.lower()
        if not is_potential_shopping_list:
            active_notes_count = await note_repo.count_active_notes_for_user(telegram_id)
            if active_notes_count >= MAX_NOTES_MVP:
                return False, f"⚠️ Достигнут лимит в {MAX_NOTES_MVP} активных заметок. Чтобы добавить новую, удалите или заархивируйте старую.", None, False

    if not DEEPSEEK_API_KEY_EXISTS:
        # Логика без LLM: просто сохраняем текст как есть
        note_id = await note_repo.create_note(
            telegram_id=telegram_id,
            corrected_text=text_to_process,
            summary_text=text_to_process[:80],
            original_audio_telegram_file_id=audio_file_id,
            note_taken_at=message_date or datetime.now(pytz.utc)
        )
        if note_id:
            note = await note_repo.get_note_by_id(note_id, telegram_id)
            user_message = f"✅ Заметка #{hbold(str(note_id))} сохранена (без AI-анализа)."
            return True, user_message, note, False
        else:
            return False, "❌ Ошибка при сохранении заметки.", None, False

    # --- Логика с LLM ---
    user_timezone_str = user_profile.get('timezone', 'UTC')
    user_tz = pytz.timezone(user_timezone_str)
    current_user_dt_iso = datetime.now(user_tz).isoformat()

    llm_result = await enhance_text_with_llm(text_to_process, current_user_dt_iso)

    if "error" in llm_result:
        logger.error(f"LLM error for user {telegram_id}: {llm_result['error']}")
        # При ошибке LLM создаем простую заметку
        corrected_text_to_save = text_to_process
        summary_text_to_save = text_to_process[:80]
        category_to_save = "Общее"
        llm_analysis_json = {"error": llm_result['error']}
        due_date_obj = None
        recurrence_rule = None
    else:
        llm_analysis_json = llm_result
        corrected_text_to_save = llm_result.get("corrected_text", text_to_process)
        summary_text_to_save = llm_result.get("summary_text", corrected_text_to_save[:80])
        category_to_save = llm_result.get("category", "Общее")

        # Извлечение даты
        due_date_obj = None
        if llm_result.get("dates_times"):
            try:
                date_info = llm_result["dates_times"][0]
                due_date_str_utc = date_info.get("absolute_datetime_start")
                if due_date_str_utc:
                    due_date_obj = datetime.fromisoformat(due_date_str_utc.replace('Z', '+00:00'))
            except (ValueError, IndexError, KeyError) as e:
                logger.error(f"Ошибка парсинга даты из LLM: {e}")

        recurrence_rule = llm_result.get("recurrence_rule")

    # --- Обработка списков покупок ---
    if category_to_save == "Покупки" and llm_analysis_json.get("items"):
        shopping_note = await note_repo.get_or_create_active_shopping_list_note(telegram_id)
        if not shopping_note:
            return False, "❌ Не удалось обработать список покупок.", None, False

        existing_items = shopping_note.get("llm_analysis_json", {}).get("items", [])
        existing_item_names = {item['item_name'].lower() for item in existing_items}
        new_items_from_llm = llm_analysis_json["items"]

        items_to_add = []
        for item in new_items_from_llm:
            if item['item_name'].lower() not in existing_item_names:
                item['added_by'] = telegram_id
                items_to_add.append(item)

        existing_items.extend(items_to_add)
        shopping_note["llm_analysis_json"]["items"] = existing_items

        await note_repo.update_note_llm_json(shopping_note['note_id'], shopping_note["llm_analysis_json"])

        user_message = f"✅ Добавлено в ваш список покупок: {len(items_to_add)} поз."
        return True, user_message, shopping_note, False

    # --- Обработка обычных заметок ---
    warning_message = ""
    if recurrence_rule and not is_vip:
        recurrence_rule = None
        warning_message = f"\n\n⭐ Повторяющиеся задачи — VIP-функция. Заметка сохранена как разовая."

    note_id = await note_repo.create_note(
        telegram_id=telegram_id,
        corrected_text=corrected_text_to_save,
        summary_text=summary_text_to_save,
        original_stt_text=text_to_process,
        llm_analysis_json=llm_analysis_json,
        original_audio_telegram_file_id=audio_file_id,
        note_taken_at=message_date or datetime.now(pytz.utc),
        due_date=due_date_obj,
        recurrence_rule=recurrence_rule,
        category=category_to_save
    )

    if not note_id:
        return False, "❌ Ошибка при сохранении заметки в базу.", None, False

    new_note = await note_repo.get_note_by_id(note_id, telegram_id)
    if new_note.get('due_date'):
        add_reminder_to_scheduler(bot, {**new_note, **user_profile})

    user_message = f"✅ Заметка #{hbold(str(note_id))} успешно сохранена!{warning_message}"
    date_info = ""
    needs_tz_prompt = False
    if new_note.get('due_date'):
        formatted_date = format_datetime_for_user(new_note['due_date'], user_timezone_str)
        date_info = f"\n🗓️ Срок: {formatted_date}"
        if user_timezone_str == 'UTC':
            needs_tz_prompt = True
            date_info += f"\n\n{hbold('⚠️ Важно!')} Укажите ваш часовой пояс в настройках, чтобы напоминание сработало вовремя."

    full_response = f"{user_message}\n\n{hcode(summary_text_to_save)}{date_info}"

    return True, full_response, new_note, needs_tz_prompt