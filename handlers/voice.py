# handlers/voice.py
import logging
from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hcode, hbold, hitalic

from config import (
    MIN_VOICE_DURATION_SEC, DEEPSEEK_API_KEY_EXISTS, YANDEX_STT_CONFIGURED,
    MIN_STT_TEXT_CHARS, MIN_STT_TEXT_WORDS
)
from inline_keyboards import get_note_confirmation_keyboard
from llm_processor import enhance_text_with_llm
from services.common import get_or_create_user
from states import NoteCreationStates
from utills import download_audio_content, recognize_speech_yandex
from main import bot_instance  # Импортируем экземпляр бота из main.py

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.voice)
async def handle_voice_message(message: types.Message, state: FSMContext):
    """Обрабатывает входящие голосовые сообщения."""
    await get_or_create_user(message.from_user)
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
        file_info = await bot_instance.get_file(file_id)  # Используем bot_instance
        file_url = f"https://api.telegram.org/file/bot{bot_instance.token}/{file_info.file_path}"
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

    if len(raw_text_stt.strip()) < MIN_STT_TEXT_CHARS or \
            len(raw_text_stt.strip().split()) < MIN_STT_TEXT_WORDS:
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
    llm_info_for_user_display = ""  # Инициализируем пустой строкой

    if DEEPSEEK_API_KEY_EXISTS:
        llm_result_dict = await enhance_text_with_llm(raw_text_stt)
        if "error" in llm_result_dict:
            logger.error(f"LLM error for user {message.from_user.id}: {llm_result_dict['error']}")
            llm_info_for_user_display = f"\n\n⚠️ {hbold('Ошибка при AI анализе:')} {hcode(llm_result_dict['error'])}"
        else:
            llm_analysis_result_json = llm_result_dict
            corrected_text_for_response = llm_result_dict.get("corrected_text", raw_text_stt)

            details_parts = [f"{hbold('✨ Улучшенный текст (AI):')}\n{hcode(corrected_text_for_response)}"]
            if llm_result_dict.get("task_description"):
                details_parts.append(f"📝 {hbold('Задача:')} {hitalic(llm_result_dict['task_description'])}")

            dates_times_str_list = []
            for dt_entry in llm_result_dict.get("dates_times", []):
                mention = dt_entry.get('original_mention', 'N/A')
                start_dt = dt_entry.get('absolute_datetime_start', 'N/A')
                dates_times_str_list.append(f"- {hitalic(mention)} -> {hcode(start_dt)}")
            if dates_times_str_list:
                details_parts.append(f"🗓️ {hbold('Даты/Время:')}\n" + "\n".join(dates_times_str_list))

            if llm_result_dict.get("people_mentioned"):
                details_parts.append(f"👥 {hbold('Люди:')} {hitalic(', '.join(llm_result_dict['people_mentioned']))}")
            if llm_result_dict.get("locations_mentioned"):
                details_parts.append(
                    f"📍 {hbold('Места:')} {hitalic(', '.join(llm_result_dict['locations_mentioned']))}")
            if llm_result_dict.get("implied_intent"):
                details_parts.append(f"💡 {hbold('Намерения:')} {hcode(', '.join(llm_result_dict['implied_intent']))}")

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
            reply_markup=get_note_confirmation_keyboard(),  # <--- ИЗМЕНЕНИЕ
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not edit status message, sending new: {e}")
        await message.answer(
            response_to_user,
            reply_markup=get_note_confirmation_keyboard(),  # <--- ИЗМЕНЕНИЕ
            parse_mode="HTML"
        )