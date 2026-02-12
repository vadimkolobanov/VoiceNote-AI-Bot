# src/bot/modules/notes/services.py
import logging
import re
import asyncio
from datetime import datetime, timedelta
import pytz

from aiogram import Bot
from aiogram.utils.markdown import hbold, hcode, hitalic

from .keyboards import get_suggest_recurrence_keyboard
from ....database import note_repo, user_repo
from ....core.config import DEEPSEEK_API_KEY_EXISTS, MAX_NOTES_MVP
from ....services import llm
from ....services.scheduler import add_reminder_to_scheduler
from ....services.tz_utils import format_datetime_for_user
from ....services.gamification_service import check_and_grant_achievements


logger = logging.getLogger(__name__)

TYPO_CORRECTIONS = {
    "напомин": "напомни", "напомнить": "напомни", "напомниь": "напомни",
    "купит": "купить", "купиь": "купить",
}


def _preprocess_text(text: str) -> str:
    """Применяет исправления опечаток к тексту."""
    import re
    result = text
    for typo, correction in TYPO_CORRECTIONS.items():
        result = re.sub(rf'\b{re.escape(typo)}\b', correction, result, count=1, flags=re.IGNORECASE)
    return result


def _calculate_due_date_from_components(time_components: dict, user_tz: pytz.BaseTzInfo) -> datetime | None:
    """
    Вычисляет точную дату напоминания на основе компонентов от LLM.
    Возвращает datetime объект в UTC.
    """
    if not time_components:
        return None

    try:
        now_in_user_tz = datetime.now(user_tz)
        target_dt = now_in_user_tz

        relative_days = time_components.get("relative_days", 0) or 0
        relative_hours = time_components.get("relative_hours", 0) or 0
        relative_minutes = time_components.get("relative_minutes", 0) or 0

        # Защита от конфликтов: если есть relative_hours, игнорируем set_hour (и аналогично для минут)
        set_hour = time_components.get("set_hour")
        set_minute = time_components.get("set_minute")
        if relative_hours and set_hour is not None:
            logger.warning(f"Конфликт: relative_hours={relative_hours} и set_hour={set_hour}. Используем set_hour.")
            relative_hours = 0
        if relative_minutes and set_minute is not None:
            logger.warning(f"Конфликт: relative_minutes={relative_minutes} и set_minute={set_minute}. Используем set_minute.")
            relative_minutes = 0

        if any([relative_days, relative_hours, relative_minutes]):
            target_dt += timedelta(days=relative_days, hours=relative_hours, minutes=relative_minutes)

        replace_kwargs = {
            k: v for k, v in {
                'year': time_components.get("set_year"), 'month': time_components.get("set_month"),
                'day': time_components.get("set_day"), 'hour': set_hour,
                'minute': set_minute, 'second': 0, 'microsecond': 0
            }.items() if v is not None
        }
        if replace_kwargs:
            target_dt = target_dt.replace(**replace_kwargs)

        is_today_explicit = time_components.get("is_today_explicit", False)
        if not is_today_explicit and target_dt <= now_in_user_tz:
            if time_components.get("set_hour") is not None and time_components.get("set_day") is None:
                if target_dt.time() <= now_in_user_tz.time():
                    target_dt += timedelta(days=1)
            elif time_components.get("set_day") is not None and time_components.get("set_month") is not None:
                if target_dt.date() < now_in_user_tz.date():
                    target_dt = target_dt.replace(year=target_dt.year + 1)
                elif target_dt.date() == now_in_user_tz.date() and target_dt.time() <= now_in_user_tz.time():
                    target_dt += timedelta(days=1)

        return target_dt.astimezone(pytz.utc)
    except (TypeError, ValueError) as e:
        logger.error(f"Ошибка при вычислении даты из компонентов: {e}. Компоненты: {time_components}")
        return None


async def _check_for_recurring_suggestion(bot: Bot, user_id: int, new_note: dict):
    """
    Проверяет, не является ли новая заметка частью рутины, и предлагает сделать ее повторяющейся.
    """
    await asyncio.sleep(2)

    new_summary = new_note.get('summary_text')
    if not new_summary:
        return

    candidate_notes = await note_repo.find_similar_notes(user_id, new_summary)

    similar_notes_count = 0
    for old_note in candidate_notes:
        if old_note['note_id'] == new_note['note_id']:
            continue
        if await llm.are_tasks_same(new_note['corrected_text'], old_note['corrected_text']):
            similar_notes_count += 1

    if similar_notes_count >= 2:
        logger.info(f"Найдена потенциальная рутина для пользователя {user_id} (заметка #{new_note['note_id']})")

        user_profile = await user_repo.get_user_profile(user_id)
        if not user_profile or not user_profile.get('is_vip', False):
            logger.info(f"Пользователь {user_id} не VIP, предложение о повторении не отправлено.")
            return

        text = (
            f"💡 Я заметил, что вы уже создавали похожую задачу: «{hitalic(new_summary)}».\n\n"
            "Хотите, чтобы я напоминал вам об этом регулярно, чтобы не вводить задачу вручную?"
        )
        keyboard = get_suggest_recurrence_keyboard(new_note['note_id'])
        await bot.send_message(user_id, text, reply_markup=keyboard, parse_mode="HTML")


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

    preprocessed_text = _preprocess_text(text_to_process)

    if not DEEPSEEK_API_KEY_EXISTS:
        note_id = await note_repo.create_note(
            telegram_id=telegram_id, corrected_text=text_to_process, summary_text=text_to_process[:80],
            original_audio_telegram_file_id=audio_file_id, note_taken_at=message_date or datetime.now(pytz.utc)
        )
        if note_id:
            note = await note_repo.get_note_by_id(note_id, telegram_id)
            user_message = f"✅ Заметка #{hbold(str(note_id))} сохранена (без AI-анализа)."
            return True, user_message, note, False
        else:
            return False, "❌ Ошибка при сохранении заметки.", None, False

    intent_result = await llm.classify_intent(preprocessed_text)
    if "error" in intent_result:
        return False, "❌ Ошибка AI: не удалось определить ваше намерение.", None, False

    intent = llm.UserIntent(intent_result.get("intent", "неизвестно"))
    logger.info(f"Определено намерение '{intent.value}' для пользователя {telegram_id}")

    llm_analysis_json, category_to_save, due_date_obj, recurrence_rule = {}, "Общее", None, None

    if intent == llm.UserIntent.CREATE_SHOPPING_LIST:
        llm_analysis_json = await llm.extract_shopping_list(preprocessed_text)
        category_to_save = "Покупки"
    elif intent == llm.UserIntent.CREATE_REMINDER:
        user_timezone_str = user_profile.get('timezone', 'UTC')
        user_tz = pytz.timezone(user_timezone_str)
        current_user_dt_iso = datetime.now(user_tz).isoformat()
        llm_analysis_json = await llm.extract_reminder_details(preprocessed_text, current_user_dt_iso)
        category_to_save = "Задачи"
    else:
        llm_analysis_json = await llm.extract_note_details(preprocessed_text)

    if "error" in llm_analysis_json:
        return False, "❌ Ошибка AI: не удалось извлечь детали из вашего сообщения.", None, False

    corrected_text_to_save = llm_analysis_json.get("corrected_text", text_to_process)
    summary_text_to_save = llm_analysis_json.get("summary_text", corrected_text_to_save[:80])

    if intent == llm.UserIntent.CREATE_REMINDER:
        time_components = llm_analysis_json.get("time_components")
        user_timezone_str = user_profile.get('timezone', 'UTC')
        user_tz = pytz.timezone(user_timezone_str)
        due_date_obj = _calculate_due_date_from_components(time_components, user_tz)
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
        telegram_id=telegram_id, corrected_text=corrected_text_to_save, summary_text=summary_text_to_save,
        original_stt_text=text_to_process, llm_analysis_json=llm_analysis_json,
        original_audio_telegram_file_id=audio_file_id, note_taken_at=message_date or datetime.now(pytz.utc),
        due_date=due_date_obj, recurrence_rule=recurrence_rule, category=category_to_save
    )

    if not note_id:
        return False, "❌ Ошибка при сохранении заметки в базу.", None, False

    if recurrence_rule:
        await check_and_grant_achievements(bot, telegram_id)

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

    asyncio.create_task(_check_for_recurring_suggestion(bot, telegram_id, new_note))

    return True, full_response, new_note, needs_tz_prompt