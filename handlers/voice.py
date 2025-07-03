# handlers/voice.py
import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hcode

import database_setup as db
from config import (
    MIN_VOICE_DURATION_SEC, YANDEX_STT_CONFIGURED,
    MIN_STT_TEXT_CHARS, MIN_STT_TEXT_WORDS, MAX_VOICE_DURATION_SEC
)
from inline_keyboards import get_undo_creation_keyboard
from services.common import get_or_create_user, check_and_update_stt_limit, increment_stt_recognition_count
from services import note_creator
from utills import download_audio_content, recognize_speech_yandex

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.voice)
async def handle_voice_message(message: types.Message, state: FSMContext):
    """Обрабатывает входящие голосовые сообщения с автосохранением."""
    await state.clear()
    await get_or_create_user(message.from_user)
    user_tg = message.from_user

    can_recognize, remaining_recognitions = await check_and_update_stt_limit(user_tg.id)
    if not can_recognize:
        await message.reply("Вы достигли дневного лимита на распознавание голосовых сообщений. 😔")
        return

    voice = message.voice
    if voice.duration < MIN_VOICE_DURATION_SEC:
        await message.reply(f"🎤 Ваше голосовое сообщение слишком короткое ({voice.duration} сек.).")
        return

    if voice.duration > MAX_VOICE_DURATION_SEC:
        await message.reply(f"🎤 Ваше голосовое сообщение слишком длинное ({voice.duration} сек.).")
        return

    status_msg = await message.reply("✔️ Запись получена. Распознаю речь...")

    try:
        file_info = await message.bot.get_file(voice.file_id)
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка при получении файла от Telegram: {e}")
        return

    audio_bytes = await download_audio_content(f"https://api.telegram.org/file/bot{message.bot.token}/{file_info.file_path}")
    if not audio_bytes:
        await status_msg.edit_text("❌ Не удалось скачать аудиофайл для обработки.")
        return

    if not YANDEX_STT_CONFIGURED:
        await status_msg.edit_text("❌ Сервис распознавания речи временно недоступен.")
        return

    raw_text_stt = await recognize_speech_yandex(audio_bytes)

    if not raw_text_stt or not raw_text_stt.strip():
        await status_msg.edit_text("❌ К сожалению, не удалось распознать речь.")
        return

    await increment_stt_recognition_count(user_tg.id)

    if len(raw_text_stt.strip()) < MIN_STT_TEXT_CHARS or len(raw_text_stt.strip().split()) < MIN_STT_TEXT_WORDS:
        await status_msg.edit_text(f"❌ Распознанный текст слишком короткий: {hcode(raw_text_stt)}")
        return

    await status_msg.edit_text(
        f"🗣️ Распознано: {hcode(raw_text_stt)}\n\n"
        "✨ Анализирую и сохраняю заметку..."
    )

    success, user_message, new_note, needs_tz_prompt = await note_creator.process_and_save_note(
        bot=message.bot,
        telegram_id=user_tg.id,
        text_to_process=raw_text_stt,
        audio_file_id=voice.file_id,
        message_date=message.date
    )

    if success:
        await db.log_user_action(
            user_tg.id,
            'create_note_voice_auto',
            metadata={'note_id': new_note['note_id']}
        )
        # --- ИЗМЕНЕНИЕ: Проверяем категорию новой заметки ---
        is_shopping_list = new_note.get('category') == 'Покупки'
        keyboard = get_undo_creation_keyboard(new_note['note_id'], is_shopping_list=is_shopping_list)
        # ---------------------------------------------------

        await status_msg.edit_text(user_message, parse_mode="HTML", reply_markup=keyboard)
    else:
        await status_msg.edit_text(user_message, parse_mode="HTML")