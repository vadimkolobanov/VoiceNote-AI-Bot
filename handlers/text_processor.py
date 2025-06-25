# handlers/text_processor.py
import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

import database_setup as db
from inline_keyboards import get_undo_creation_keyboard
from services import note_creator

logger = logging.getLogger(__name__)
router = Router()

MIN_TEXT_LENGTH_FOR_NOTE = 10
MIN_WORDS_FOR_NOTE = 2
GARBAGE_WORDS = {'привет', 'спс', 'спасибо', 'ок', 'ok', 'хорошо', 'ага', 'угу', 'hi', 'hello', 'thanks'}


async def process_text_and_autosave(message: types.Message, text: str, status_message: types.Message):
    """
    Общая функция для обработки текста, сохранения заметки и отправки ответа.
    """
    success, user_message, new_note = await note_creator.process_and_save_note(
        bot=message.bot,
        telegram_id=message.from_user.id,
        text_to_process=text,
        message_date=message.date
    )

    if success:
        await db.log_user_action(
            message.from_user.id,
            'create_note_text_auto',
            metadata={'note_id': new_note['note_id']}
        )
        keyboard = get_undo_creation_keyboard(new_note['note_id'])
        await status_message.edit_text(user_message, parse_mode="HTML", reply_markup=keyboard)
    else:
        await status_message.edit_text(user_message, parse_mode="HTML")


@router.message(F.forward_date, F.text)
async def handle_forwarded_text_message(message: types.Message, state: FSMContext):
    """
    Обрабатывает пересланные текстовые сообщения, анализирует их
    и автоматически сохраняет как заметку.
    """
    await state.clear()
    text_to_process = message.text
    if not text_to_process or not text_to_process.strip():
        return

    status_msg = await message.reply("✔️ Пересланное сообщение получено. Обрабатываю...")
    await process_text_and_autosave(message, text_to_process, status_msg)


@router.message(F.text, ~F.text.startswith('/'))
async def handle_regular_text_message(message: types.Message, state: FSMContext):
    """
    Обрабатывает обычные текстовые сообщения, фильтрует "мусор"
    и автоматически сохраняет как заметку.
    """
    await state.clear()
    text = message.text.strip()

    # Фильтр "мусорных" сообщений
    if len(text) < MIN_TEXT_LENGTH_FOR_NOTE or \
       len(text.split()) < MIN_WORDS_FOR_NOTE or \
       text.lower() in GARBAGE_WORDS:
        logger.info(f"Ignoring short/garbage text from {message.from_user.id}: '{text}'")
        return

    status_msg = await message.reply("✔️ Сообщение принято. Обрабатываю...")
    await process_text_and_autosave(message, text, status_msg)