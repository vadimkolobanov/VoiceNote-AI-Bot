# handlers/voice.py
import logging
from datetime import datetime, timedelta, time
import pytz

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hcode, hbold, hitalic

import database_setup as db
from config import (
    MIN_VOICE_DURATION_SEC, DEEPSEEK_API_KEY_EXISTS, YANDEX_STT_CONFIGURED,
    MIN_STT_TEXT_CHARS, MIN_STT_TEXT_WORDS
)
from inline_keyboards import get_note_confirmation_keyboard
from llm_processor import enhance_text_with_llm
from services.common import get_or_create_user, check_and_update_stt_limit, increment_stt_recognition_count
from services.tz_utils import format_datetime_for_user
from states import NoteCreationStates
from utills import download_audio_content, recognize_speech_yandex

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.voice)
async def handle_voice_message(message: types.Message, state: FSMContext):
    """Обрабатывает входящие голосовые сообщения."""
    user_profile = await get_or_create_user(message.from_user)
    user_tg = message.from_user

    can_recognize, remaining_recognitions = await check_and_update_stt_limit(user_tg.id)
    if not can_recognize:
        logger.info(f"User {user_tg.id} exceeded daily STT limit.")
        await message.reply(
            "Вы достигли дневного лимита на распознавание голосовых сообщений. 😔\n"
            "Попробуйте снова завтра. Спасибо за понимание!"
        )
        return

    voice = message.voice
    if voice.duration < MIN_VOICE_DURATION_SEC:
        logger.info(f"User {message.from_user.id} sent too short voice: {voice.duration}s")
        await message.reply(
            f"🎤 Ваше голосовое сообщение слишком короткое ({voice.duration} сек.).\n"
            f"Пожалуйста, запишите сообщение длительностью не менее {MIN_VOICE_DURATION_SEC} сек."
        )
        return

    file_id = voice.file_id
    voice_message_datetime = message.date
    status_msg = await message.reply("✔️ Запись получена. Скачиваю и начинаю распознавание...")

    try:
        file_info = await message.bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_info.file_path}"
    except Exception as e:
        logger.exception(f"Error getting file info for user {message.from_user.id}")
        await status_msg.edit_text(f"❌ Ошибка при получении файла от Telegram: {e}")
        return

    audio_bytes = await download_audio_content(file_url)
    if not audio_bytes:
        await status_msg.edit_text("❌ Не удалось скачать аудиофайл для обработки.")
        return

    if not YANDEX_STT_CONFIGURED:
        await status_msg.edit_text("❌ Сервис распознавания речи временно недоступен.")
        logger.error("Yandex STT not configured, but voice message received.")
        return

    raw_text_stt = await recognize_speech_yandex(audio_bytes)

    if not raw_text_stt or not raw_text_stt.strip():
        logger.info(f"Yandex STT for user {message.from_user.id} returned empty text.")
        await status_msg.edit_text(
            "❌ К сожалению, не удалось распознать речь в вашем сообщении.\n"
            "Попробуйте записать его четче или в более тихом месте."
        )
        return

    await increment_stt_recognition_count(user_tg.id)
    logger.info(f"STT successful for user {user_tg.id}. Remaining for today: {remaining_recognitions - 1}")

    if len(raw_text_stt.strip()) < MIN_STT_TEXT_CHARS or len(raw_text_stt.strip().split()) < MIN_STT_TEXT_WORDS:
        logger.info(f"Yandex STT for user {message.from_user.id} returned too short text: '{raw_text_stt}'")
        await status_msg.edit_text(
            f"❌ Распознанный текст слишком короткий.\nРаспознано: {hcode(raw_text_stt)}\nПожалуйста, попробуйте еще раз."
        )
        return

    await status_msg.edit_text(
        f"🗣️ Распознано (Yandex STT):\n{hcode(raw_text_stt)}\n\n"
        "✨ Улучшаю текст и извлекаю детали с помощью LLM..."
    )

    llm_analysis_result_json = None
    corrected_text_for_response = raw_text_stt
    llm_info_for_user_display = ""

    if DEEPSEEK_API_KEY_EXISTS:
        user_timezone_str = user_profile.get('timezone', 'UTC')
        is_vip = user_profile.get('is_vip', False)

        llm_result_dict = await enhance_text_with_llm(raw_text_stt, user_timezone=user_timezone_str)

        if "error" in llm_result_dict:
            logger.error(f"LLM error for user {message.from_user.id}: {llm_result_dict['error']}")
            llm_info_for_user_display = f"\n\n⚠️ {hbold('Ошибка при AI анализе:')} {hcode(llm_result_dict['error'])}"
        else:
            llm_analysis_result_json = llm_result_dict
            corrected_text_for_response = llm_result_dict.get("corrected_text", raw_text_stt)

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
                            default_time = user_profile.get('default_reminder_time', time(9, 0)) if is_vip else time(12,
                                                                                                                     0)
                            local_due_date = datetime.combine(dt_obj_utc.date(), default_time)
                            aware_local_due_date = user_tz.localize(local_due_date)
                            final_utc_date_to_show = aware_local_due_date.astimezone(pytz.utc)
                        else:
                            final_utc_date_to_show = dt_obj_utc

                        llm_result_dict["dates_times"][0]["absolute_datetime_start"] = final_utc_date_to_show.strftime(
                            '%Y-%m-%dT%H:%M:%SZ')
                        llm_analysis_result_json = llm_result_dict
                        display_date = format_datetime_for_user(final_utc_date_to_show, user_timezone_str)
                        logger.info(f"Дата для предпросмотра: {display_date} (исходная UTC: {due_date_str_utc})")

                except Exception as e:
                    logger.error(f"Ошибка при коррекции/форматировании даты для предпросмотра (voice): {e}")
                    display_date = "Ошибка даты"

            details_parts = [f"{hbold('✨ Улучшенный текст (AI):')}\n{hcode(corrected_text_for_response)}"]
            if llm_result_dict.get("task_description"):
                details_parts.append(f"📝 {hbold('Задача:')} {hitalic(llm_result_dict['task_description'])}")

            if llm_result_dict.get("dates_times") and 'display_date' in locals() and display_date:
                mention = llm_result_dict["dates_times"][0].get('original_mention', 'N/A')
                dates_times_str_list = [f"- {hitalic(mention)} -> {hbold(display_date)}"]
                details_parts.append(f"🗓️ {hbold('Распознанные даты/время:')}\n" + "\n".join(dates_times_str_list))

            if llm_result_dict.get("people_mentioned"):
                details_parts.append(f"👥 {hbold('Люди:')} {hitalic(', '.join(llm_result_dict['people_mentioned']))}")
            if llm_result_dict.get("locations_mentioned"):
                details_parts.append(
                    f"📍 {hbold('Места:')} {hitalic(', '.join(llm_result_dict['locations_mentioned']))}")

            llm_info_for_user_display = "\n\n" + "\n\n".join(details_parts)
    else:
        llm_info_for_user_display = f"\n\n{hitalic('AI анализ текста пропущен (ключ API не настроен).')}"

    await state.set_state(NoteCreationStates.awaiting_confirmation)
    await state.update_data(
        original_stt_text=raw_text_stt,
        corrected_text_for_save=corrected_text_for_response,
        llm_analysis_json=llm_analysis_result_json,
        original_audio_telegram_file_id=file_id,
        voice_message_date=voice_message_datetime
    )

    response_to_user = (
        f"{hbold('🎙️ Исходный текст (STT):')}\n{hcode(raw_text_stt)}"
        f"{llm_info_for_user_display}\n\n"
        f"{hbold('📊 Параметры аудио:')}\n"
        f"Длительность: {voice.duration} сек, Размер: {voice.file_size // 1024} КБ\n\n"
        "💾 Сохранить эту заметку?"
    )

    try:
        await status_msg.edit_text(
            response_to_user,
            reply_markup=get_note_confirmation_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not edit status message, sending new: {e}")
        await message.answer(
            response_to_user,
            reply_markup=get_note_confirmation_keyboard(),
            parse_mode="HTML"
        )