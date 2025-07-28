# src/bot/modules/notes/handlers/creation.py
import asyncio
import logging
from datetime import date, datetime

from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hcode, hbold
from aiogram.exceptions import TelegramBadRequest

from .....core import config
from .....database import user_repo, note_repo
from .....services import stt, llm
from .....services.gamification_service import XP_REWARDS, check_and_grant_achievements
from .....services.tz_utils import format_datetime_for_user
from ..keyboards import get_undo_creation_keyboard
from ..services import process_and_save_note
from ....common_utils.states import NotesSearchStates
from aiogram.filters import StateFilter

logger = logging.getLogger(__name__)
router = Router()

MIN_TEXT_LENGTH_FOR_NOTE = 10
MIN_WORDS_FOR_NOTE = 2
GARBAGE_WORDS = {'привет', 'спс', 'спасибо', 'ок', 'ok', 'хорошо', 'ага', 'угу', 'hi', 'hello', 'thanks'}
BOREDOM_TRIGGERS = {'мне скучно', 'скучно', 'скукота', 'чем заняться'}


async def _check_and_update_stt_limit(telegram_id: int) -> tuple[bool, int]:
    """Проверяет и обновляет дневной лимит STT для пользователя."""
    user_profile = await user_repo.get_user_profile(telegram_id)
    if not user_profile:
        return False, 0

    if user_profile.get('is_vip', False):
        return True, 999

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


async def _check_for_proactive_suggestions(bot: Bot, user_id: int, new_note: dict):
    """
    Проверяет, нужно ли дать пользователю проактивный совет после создания заметки.
    """
    due_date = new_note.get('due_date')
    if not due_date:
        return

    conflicting_notes = await note_repo.find_conflicting_notes(user_id, due_date, new_note['note_id'])
    if not conflicting_notes:
        return

    user_profile = await user_repo.get_user_profile(user_id)
    user_timezone = user_profile.get('timezone', 'UTC')

    real_conflicts = []
    for existing_note in conflicting_notes:
        new_note_text = new_note.get('corrected_text', new_note.get('summary_text', ''))
        existing_note_text = existing_note.get('corrected_text', existing_note.get('summary_text', ''))

        if await llm.are_tasks_conflicting(new_note_text, existing_note_text):
            real_conflicts.append(existing_note)

    if real_conflicts:
        conflict_texts = []
        for note in real_conflicts:
            formatted_time = format_datetime_for_user(note['due_date'], user_timezone)
            conflict_texts.append(f"• {hcode(note['summary_text'])} на {hbold(formatted_time)}")

        conflict_list_str = "\n".join(conflict_texts)

        suggestion_text = (
            f"💡 {hbold('Обратите внимание!')}\n\n"
            f"Я сохранил вашу задачу, но заметил, что она может конфликтовать с другими вашими планами:\n"
            f"{conflict_list_str}\n\n"
            f"Возможно, стоит перепроверить расписание?"
        )

        await asyncio.sleep(1)
        await bot.send_message(user_id, suggestion_text, parse_mode="HTML")

async def _background_note_processor(
        bot: Bot,
        user_id: int,
        status_message_id: int,
        chat_id: int,
        text_to_process: str | None = None,
        voice_file_id: str | None = None,
        original_message_date: datetime | None = None
):
    """
    Фоновый воркер для обработки и сохранения заметки.
    """
    try:
        if voice_file_id:
            await bot.edit_message_text(text="✔️ Запись получена. Распознаю речь...", chat_id=chat_id,
                                        message_id=status_message_id)
            file_info = await bot.get_file(voice_file_id)
            audio_bytes = await stt.download_audio_content(
                f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}")
            if not audio_bytes:
                await bot.edit_message_text(text="❌ Не удалось скачать аудиофайл.", chat_id=chat_id,
                                            message_id=status_message_id)
                return

            recognized_text = await stt.recognize_speech_yandex(audio_bytes)
            if not recognized_text or not recognized_text.strip():
                await bot.edit_message_text(text="❌ К сожалению, не удалось распознать речь.", chat_id=chat_id,
                                            message_id=status_message_id)
                return

            await _increment_stt_count(user_id)
            if len(recognized_text.strip()) < config.MIN_STT_TEXT_CHARS or len(
                    recognized_text.strip().split()) < config.MIN_STT_TEXT_WORDS:
                await bot.edit_message_text(text=f"❌ Распознанный текст слишком короткий: {hcode(recognized_text)}",
                                            chat_id=chat_id, message_id=status_message_id, parse_mode="HTML")
                return

            text_to_process = recognized_text
            await bot.edit_message_text(text=f"🗣️ Распознано: {hcode(text_to_process)}\n\n✨ Анализирую и сохраняю...",
                                        chat_id=chat_id, message_id=status_message_id, parse_mode="HTML")

        success, user_message, new_note, _ = await process_and_save_note(
            bot=bot,
            telegram_id=user_id,
            text_to_process=text_to_process,
            audio_file_id=voice_file_id,
            message_date=original_message_date
        )

        if not success:
            await bot.edit_message_text(text=user_message, chat_id=chat_id, message_id=status_message_id)
            return

        action_type = 'create_note_voice_auto' if voice_file_id else 'create_note_text_auto'
        xp_reward = XP_REWARDS['create_note_voice'] if voice_file_id else XP_REWARDS['create_note_text']

        await user_repo.log_user_action(user_id, action_type, metadata={'note_id': new_note['note_id']})
        await user_repo.add_xp_and_check_level_up(bot, user_id, xp_reward)
        await check_and_grant_achievements(bot, user_id)

        is_shopping_list = new_note.get('category') == 'Покупки'
        keyboard = get_undo_creation_keyboard(new_note['note_id'], is_shopping_list)
        await bot.edit_message_text(text=user_message, chat_id=chat_id, message_id=status_message_id,
                                    reply_markup=keyboard)

        await _check_for_proactive_suggestions(bot, user_id, new_note)

    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logger.debug(f"Сообщение {status_message_id} не было изменено. Пропуск.")
        else:
            logger.error(f"Ошибка Telegram API в фоновом обработчике: {e}", exc_info=True)
            try:
                await bot.edit_message_text(text="❌ Произошла ошибка при обработке.", chat_id=chat_id,
                                            message_id=status_message_id)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Критическая ошибка в фоновом обработчике заметки: {e}", exc_info=True)
        try:
            await bot.edit_message_text(text="❌ Произошла серьезная ошибка при обработке вашей заметки.",
                                        chat_id=chat_id, message_id=status_message_id)
        except Exception:
            pass


@router.message(F.voice)
async def handle_voice_message(message: types.Message, state: FSMContext):
    """
    Быстро отвечает на голосовое сообщение и запускает обработку в фоне.
    """
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

    status_msg = await message.reply("✔️ Принято! Начинаю обработку в фоне...")

    asyncio.create_task(_background_note_processor(
        bot=message.bot,
        user_id=message.from_user.id,
        status_message_id=status_msg.message_id,
        chat_id=message.chat.id,
        voice_file_id=message.voice.file_id,
        original_message_date=message.date
    ))


@router.message(~StateFilter(NotesSearchStates.waiting_for_query), F.text, ~F.text.startswith('/'))
async def handle_text_message(message: types.Message, state: FSMContext):
    """
    Обрабатывает текстовые сообщения: создает заметки или отвечает на "скуку".
    """
    await state.clear()
    text = message.text.strip()
    text_lower = text.lower()

    if text_lower in BOREDOM_TRIGGERS:
        status_msg = await message.reply("Хм, скучно, говоришь? Дай-ка подумать... 🤔")
        user_profile = await user_repo.get_user_profile(message.from_user.id)
        user_name = user_profile.get('first_name', 'друг')
        suggestion = await llm.get_fun_suggestion(user_name)
        await status_msg.edit_text(suggestion)
        return

    if (not message.forward_date and
            (len(text) < MIN_TEXT_LENGTH_FOR_NOTE or
             len(text.split()) < MIN_WORDS_FOR_NOTE or
             text_lower in GARBAGE_WORDS)):
        logger.info(f"Ignoring short/garbage text from {message.from_user.id}: '{text}'")
        return

    status_msg = await message.reply("✔️ Принято! Обрабатываю...")

    asyncio.create_task(_background_note_processor(
        bot=message.bot,
        user_id=message.from_user.id,
        status_message_id=status_msg.message_id,
        chat_id=message.chat.id,
        text_to_process=text,
        original_message_date=message.date
    ))