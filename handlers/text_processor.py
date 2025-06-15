# handlers/text_processor.py
import logging
from datetime import datetime, timedelta, time
import pytz

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hcode, hbold, hitalic

import database_setup as db
from config import DEEPSEEK_API_KEY_EXISTS
from inline_keyboards import get_note_confirmation_keyboard
from llm_processor import enhance_text_with_llm
from services.tz_utils import format_datetime_for_user
from states import NoteCreationStates

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.forward_date, F.text)
async def handle_forwarded_text_message(message: types.Message, state: FSMContext):
    """
    Обрабатывает пересланные текстовые сообщения, анализирует их
    и предлагает сохранить как заметку.
    """
    user_profile = await db.get_user_profile(message.from_user.id)
    if not user_profile:
        await message.reply("Не удалось найти ваш профиль. Пожалуйста, нажмите /start.")
        return

    forwarded_text = message.text
    if not forwarded_text.strip():
        return

    status_msg = await message.reply("✔️ Пересланное сообщение получено. Анализирую текст с помощью AI...")

    if not DEEPSEEK_API_KEY_EXISTS:
        await state.set_state(NoteCreationStates.awaiting_confirmation)
        await state.update_data(
            original_stt_text=forwarded_text,
            corrected_text_for_save=forwarded_text,
            llm_analysis_json=None,
            original_audio_telegram_file_id=None,
            voice_message_date=message.date
        )
        await status_msg.edit_text(
            f"Вот текст из пересланного сообщения. Сохранить его как заметку?\n\n{hcode(forwarded_text)}",
            reply_markup=get_note_confirmation_keyboard(),
            parse_mode="HTML"
        )
        return

    user_timezone_str = user_profile.get('timezone', 'UTC')
    is_vip = user_profile.get('is_vip', False)

    llm_result_dict = await enhance_text_with_llm(forwarded_text, user_timezone=user_timezone_str)
    llm_info_for_user_display = ""
    llm_analysis_result_json = None
    corrected_text_for_response = forwarded_text

    if "error" in llm_result_dict:
        logger.error(f"LLM error for forwarded text from user {message.from_user.id}: {llm_result_dict['error']}")
        llm_info_for_user_display = f"\n\n⚠️ {hbold('Ошибка при AI анализе:')} {hcode(llm_result_dict['error'])}"
    else:
        llm_analysis_result_json = llm_result_dict
        corrected_text_for_response = llm_result_dict.get("corrected_text", forwarded_text)

        if llm_result_dict.get("dates_times"):
            try:
                due_date_str_utc = llm_result_dict["dates_times"][0].get("absolute_datetime_start")
                if due_date_str_utc:
                    dt_obj_utc = datetime.fromisoformat(due_date_str_utc.replace('Z', '+00:00'))

                    user_tz = pytz.timezone(user_timezone_str)
                    now_in_user_tz = datetime.now(user_tz)
                    if dt_obj_utc.astimezone(user_tz) < now_in_user_tz:
                        dt_obj_utc += timedelta(days=1)

                    is_time_ambiguous = (dt_obj_utc.time() == time(0, 0, 0))
                    if is_time_ambiguous:
                        default_time = user_profile.get('default_reminder_time', time(9, 0)) if is_vip else time(12, 0)
                        local_due_date = datetime.combine(dt_obj_utc.date(), default_time)
                        aware_local_due_date = user_tz.localize(local_due_date)
                        final_utc_date_to_show = aware_local_due_date.astimezone(pytz.utc)
                    else:
                        final_utc_date_to_show = dt_obj_utc

                    llm_result_dict["dates_times"][0]["absolute_datetime_start"] = final_utc_date_to_show.strftime(
                        '%Y-%m-%dT%H:%M:%SZ')
                    llm_analysis_result_json = llm_result_dict
                    display_date = format_datetime_for_user(final_utc_date_to_show, user_timezone_str)
                    logger.info(
                        f"Дата для предпросмотра (forwarded): {display_date} (исходная UTC: {due_date_str_utc})")

            except Exception as e:
                logger.error(f"Ошибка при коррекции/форматировании даты для предпросмотра (forwarded): {e}")
                display_date = "Ошибка даты"

        details_parts = [f"{hbold('✨ Улучшенный текст (AI):')}\n{hcode(corrected_text_for_response)}"]
        if llm_result_dict.get("task_description"):
            details_parts.append(f"📝 {hbold('Задача:')} {hitalic(llm_result_dict['task_description'])}")

        if llm_result_dict.get("dates_times") and 'display_date' in locals() and display_date:
            mention = llm_result_dict["dates_times"][0].get('original_mention', 'N/A')
            dates_times_str_list = [f"- {hitalic(mention)} -> {hbold(display_date)}"]
            details_parts.append(f"🗓️ {hbold('Распознанные даты/время:')}\n" + "\n".join(dates_times_str_list))

        llm_info_for_user_display = "\n\n" + "\n\n".join(details_parts)

    await state.set_state(NoteCreationStates.awaiting_confirmation)
    await state.update_data(
        original_stt_text=forwarded_text,
        corrected_text_for_save=corrected_text_for_response,
        llm_analysis_json=llm_analysis_result_json,
        original_audio_telegram_file_id=None,
        voice_message_date=message.date
    )

    response_to_user = (
        f"{hbold('📝 Анализ пересланного сообщения:')}"
        f"{llm_info_for_user_display}\n\n"
        "💾 Сохранить эту информацию как новую заметку?"
    )

    try:
        await status_msg.edit_text(
            response_to_user,
            reply_markup=get_note_confirmation_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not edit status message for forwarded text, sending new: {e}")
        await message.answer(
            response_to_user,
            reply_markup=get_note_confirmation_keyboard(),
            parse_mode="HTML"
        )