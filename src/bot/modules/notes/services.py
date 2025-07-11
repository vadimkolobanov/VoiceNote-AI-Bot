# src/bot/modules/notes/services.py
import logging
from datetime import datetime
import pytz

from aiogram import Bot
from aiogram.utils.markdown import hbold, hcode

from ....database import note_repo, user_repo
from ....core.config import DEEPSEEK_API_KEY_EXISTS, MAX_NOTES_MVP
from ....services import llm
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
    """
    user_profile = await user_repo.get_user_profile(telegram_id)
    if not user_profile:
        return False, "Не удалось найти ваш профиль. Пожалуйста, нажмите /start.", None, False

    is_vip = user_profile.get('is_vip', False)

    if not is_vip:
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

    # --- Новая логика с декомпозицией ---

    # Этап 1: Классификация намерения
    intent_result = await llm.classify_intent(text_to_process)
    if "error" in intent_result:
        return False, "❌ Ошибка AI: не удалось определить ваше намерение.", None, False

    intent = llm.UserIntent(intent_result.get("intent", "неизвестно"))
    logger.info(f"Определено намерение '{intent.value}' для пользователя {telegram_id}")

    # Инициализация переменных
    llm_analysis_json = {}
    category_to_save = "Общее"
    due_date_obj = None
    recurrence_rule = None

    # Этап 2: Вызов соответствующего экстрактора
    if intent == llm.UserIntent.CREATE_SHOPPING_LIST:
        llm_analysis_json = await llm.extract_shopping_list(text_to_process)
        category_to_save = "Покупки"
    elif intent == llm.UserIntent.CREATE_REMINDER:
        user_timezone_str = user_profile.get('timezone', 'UTC')
        user_tz = pytz.timezone(user_timezone_str)
        current_user_dt_iso = datetime.now(user_tz).isoformat()
        llm_analysis_json = await llm.extract_reminder_details(text_to_process, current_user_dt_iso)
        category_to_save = "Задачи"
    else:  # CREATE_NOTE или UNKNOWN
        llm_analysis_json = await llm.extract_note_details(text_to_process)

    if "error" in llm_analysis_json:
        return False, "❌ Ошибка AI: не удалось извлечь детали из вашего сообщения.", None, False

    # --- Обработка и сохранение результата ---

    corrected_text_to_save = llm_analysis_json.get("corrected_text", text_to_process)
    summary_text_to_save = llm_analysis_json.get("summary_text", corrected_text_to_save[:80])

    if intent == llm.UserIntent.CREATE_REMINDER:
        if llm_analysis_json.get("dates_times"):
            try:
                date_info = llm_analysis_json["dates_times"][0]
                due_date_str_utc = date_info.get("absolute_datetime_start")
                if due_date_str_utc:
                    due_date_obj = datetime.fromisoformat(due_date_str_utc.replace('Z', '+00:00'))
            except (ValueError, IndexError, KeyError) as e:
                logger.error(f"Ошибка парсинга даты из LLM: {e}")
        recurrence_rule = llm_analysis_json.get("recurrence_rule")

    if category_to_save == "Покупки" and llm_analysis_json.get("items"):
        shopping_note = await note_repo.get_or_create_active_shopping_list_note(telegram_id)
        if not shopping_note:
            return False, "❌ Не удалось обработать список покупок.", None, False

        existing_items = shopping_note.get("llm_analysis_json", {}).get("items", [])
        existing_item_names = {item['item_name'].lower() for item in existing_items}
        new_items_from_llm = llm_analysis_json.get("items", [])

        items_to_add = [item for item in new_items_from_llm if item['item_name'].lower() not in existing_item_names]
        for item in items_to_add:
            item['added_by'] = telegram_id

        existing_items.extend(items_to_add)
        shopping_note["llm_analysis_json"]["items"] = existing_items

        await note_repo.update_note_llm_json(shopping_note['note_id'], shopping_note["llm_analysis_json"])

        user_message = f"✅ Добавлено в ваш список покупок: {len(items_to_add)} поз." if items_to_add else "✅ Список покупок обновлен."
        return True, user_message, shopping_note, False

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
        user_timezone_str = user_profile.get('timezone', 'UTC')
        formatted_date = format_datetime_for_user(new_note['due_date'], user_timezone_str)
        date_info = f"\n🗓️ Срок: {formatted_date}"
        if user_timezone_str == 'UTC':
            needs_tz_prompt = True
            date_info += f"\n\n{hbold('⚠️ Важно!')} Укажите ваш часовой пояс в настройках, чтобы напоминание сработало вовремя."

    full_response = f"{user_message}\n\n{hcode(summary_text_to_save)}{date_info}"

    return True, full_response, new_note, needs_tz_prompt