# src/bot/modules/notes/handlers/creation.py
import logging
from datetime import date

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hcode

from .....core import config
from .....database import user_repo
from .....services import stt
from ..keyboards import get_undo_creation_keyboard
from ..services import process_and_save_note

logger = logging.getLogger(__name__)
router = Router()

MIN_TEXT_LENGTH_FOR_NOTE = 10
MIN_WORDS_FOR_NOTE = 2
GARBAGE_WORDS = {'привет', 'спс', 'спасибо', 'ок', 'ok', 'хорошо', 'ага', 'угу', 'hi', 'hello', 'thanks'}


async def _check_and_update_stt_limit(telegram_id: int) -> tuple[bool, int]:
    """Проверяет и обновляет дневной лимит STT для пользователя."""
    user_profile = await user_repo.get_user_profile(telegram_id)
    if not user_profile:
        return False, 0

    if user_profile.get('is_vip', False):
        return True, 999  # Условное большое число для VIP

    today = date.today()
    last_reset = user_profile.get('last_stt_reset_date')
    count = user_profile.get('daily_stt_recognitions_count', 0)

    if last_reset != today:
        count = 0
        await user_repo.update_user_stt_counters(telegram_id, 0, today)

    can_recognize = count < config.MAX_DAILY_STT_RECOGNITIONS_MVP
    remaining = config.MAX_DAILY_STT_RECOGNITIONS_MVP - count
    return can_recognize, max(0, remaining)


async def _increment_stt_count(telegram_id: int):
    """Увеличивает счетчик STT, если пользователь не VIP."""
    user_profile = await user_repo.get_user_profile(telegram_id)
    if not user_profile or user_profile.get('is_vip', False):
        return

    today = date.today()
    count = user_profile.get('daily_stt_recognitions_count', 0)
    last_reset = user_profile.get('last_stt_reset_date')

    new_count = 1 if last_reset != today else count + 1
    await user_repo.update_user_stt_counters(telegram_id, new_count, today)


async def _autosave_and_reply(message: types.Message, text_to_process: str, status_msg: types.Message,
                              audio_file_id: str = None):
    """Общая функция для вызова сервиса и отправки ответа."""
    success, user_message, new_note, _ = await process_and_save_note(
        bot=message.bot,
        telegram_id=message.from_user.id,
        text_to_process=text_to_process,
        audio_file_id=audio_file_id,
        message_date=message.date
    )

    if not success:
        await status_msg.edit_text(user_message)
        return

    await user_repo.log_user_action(
        message.from_user.id,
        'create_note_voice_auto' if audio_file_id else 'create_note_text_auto',
        metadata={'note_id': new_note['note_id']}
    )

    is_shopping_list = new_note.get('category') == 'Покупки'
    keyboard = get_undo_creation_keyboard(new_note['note_id'], is_shopping_list)
    await status_msg.edit_text(user_message, reply_markup=keyboard)


@router.message(F.voice)
async def handle_voice_message(message: types.Message, state: FSMContext):
    """Обрабатывает голосовые сообщения."""
    await state.clear()

    can_recognize, _ = await _check_and_update_stt_limit(message.from_user.id)
    if not can_recognize:
        await message.reply(
            f"Вы достигли дневного лимита на распознавание ({config.MAX_DAILY_STT_RECOGNITIONS_MVP}). VIP-статус снимает это ограничение.")
        return

    if message.voice.duration < config.MIN_VOICE_DURATION_SEC or message.voice.duration > config.MAX_VOICE_DURATION_SEC:
        await message.reply(
            f"🎤 Голосовое сообщение должно быть от {config.MIN_VOICE_DURATION_SEC} до {config.MAX_VOICE_DURATION_SEC} секунд.")
        return

    status_msg = await message.reply("✔️ Запись получена. Распознаю речь...")

    file_info = await message.bot.get_file(message.voice.file_id)
    audio_bytes = await stt.download_audio_content(
        f"https://api.telegram.org/file/bot{message.bot.token}/{file_info.file_path}")
    if not audio_bytes:
        await status_msg.edit_text("❌ Не удалось скачать аудиофайл.")
        return

    recognized_text = await stt.recognize_speech_yandex(audio_bytes)
    if not recognized_text or not recognized_text.strip():
        await status_msg.edit_text("❌ К сожалению, не удалось распознать речь.")
        return

    await _increment_stt_count(message.from_user.id)

    if len(recognized_text.strip()) < config.MIN_STT_TEXT_CHARS or len(
            recognized_text.strip().split()) < config.MIN_STT_TEXT_WORDS:
        await status_msg.edit_text(f"❌ Распознанный текст слишком короткий: {hcode(recognized_text)}")
        return

    await status_msg.edit_text(f"🗣️ Распознано: {hcode(recognized_text)}\n\n✨ Анализирую и сохраняю...")
    await _autosave_and_reply(message, recognized_text, status_msg, audio_file_id=message.voice.file_id)


@router.message(F.text, ~F.text.startswith('/'))
async def handle_text_message(message: types.Message, state: FSMContext):
    """Обрабатывает текстовые сообщения (обычные и пересланные)."""
    await state.clear()
    text = message.text.strip()

    if (not message.forward_date and
            (len(text) < MIN_TEXT_LENGTH_FOR_NOTE or
             len(text.split()) < MIN_WORDS_FOR_NOTE or
             text.lower() in GARBAGE_WORDS)):
        logger.info(f"Ignoring short/garbage text from {message.from_user.id}: '{text}'")
        return

    status_msg = await message.reply("✔️ Сообщение принято. Обрабатываю...")
    await _autosave_and_reply(message, text, status_msg)