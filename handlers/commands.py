# handlers/commands.py
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.markdown import hbold  # Для MarkdownV2 в /start

# Импортируем константы и функции из других модулей
from config import MAX_NOTES_MVP, MAX_DAILY_STT_RECOGNITIONS_MVP
from inline_keyboards import get_main_menu_keyboard, \
    PageNavigation  # <--- ИЗМЕНЕНИЕ get_action_keyboard на get_main_menu_keyboard
from services.common import get_or_create_user

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start."""
    await state.clear()
    await get_or_create_user(message.from_user)

    # Используем MarkdownV2 для /start, если хотим более продвинутое форматирование
    start_text = (
        f"🎤 Привет\\! Я **VoiceNote AI**, твой помощник для создания умных голосовых заметок\\.\n\n"
        f"Просто отправь мне голосовое сообщение, и я:\n"
        f"1\\. Распознаю речь \\(Yandex SpeechKit\\)\\.\n"
        f"2\\. Улучшу текст и извлеку важные детали с помощью AI \\(DeepSeek\\)\\.\n"
        f"3\\. Предложу сохранить заметку\\.\n\n"
        f"Используй кнопки ниже для навигации или сразу отправляй голосовое\\!"
    )
    await message.answer(
        start_text,
        reply_markup=get_main_menu_keyboard(),  # <--- ИЗМЕНЕНИЕ
        parse_mode="MarkdownV2"
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help."""
    # Замените @useranybody на ваш реальный контакт или уберите/измените строку
    creator_contact = "@useranybody"  # Пример
    help_text = f"""
👋 Привет! Я **VoiceNote AI** – твой умный помощник для голосовых заметок.

Я использую технологию распознавания речи от Яндекса (Yandex SpeechKit) и продвинутый AI (DeepSeek) для анализа текста.

**Вот что я умею:**

🎤 **Создание заметок:**
   - Отправь мне голосовое сообщение.
   - Я распознаю твою речь, улучшу текст и извлеку важные детали.
   - Тебе будет предложено сохранить заметку.
   - В текущей версии действует лимит: **{MAX_NOTES_MVP} активных заметок**.
   - **{MAX_DAILY_STT_RECOGNITIONS_MVP} распознаваний голосовых в день**. 

📝 **Мои заметки:**
   - Нажми кнопку "📝 Мои заметки" в главном меню (или команда /my_notes).
   - Ты увидишь список своих заметок с возможностью навигации по страницам.
   - Каждую заметку можно **удалить** или **просмотреть подробно**.

👤 **Профиль:**
   - Кнопка "👤 Профиль" в главном меню покажет основную информацию о тебе.

🤖 **Основные команды:**
   - /start - Запустить бота / Главное меню.
   - /help - Показать это сообщение.
   - /my_notes - Показать список моих заметок.

💡 **Советы:**
   - Говори четко и в относительно тихом месте.
   - Формулируй даты и задачи явно для лучшего анализа AI.

---
Предложения или ошибки? Сообщи моему создателю: {creator_contact}
"""
    await message.answer(help_text, parse_mode="HTML", disable_web_page_preview=True)