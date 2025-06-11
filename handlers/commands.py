# handlers/commands.py
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.markdown import hbold

from config import MAX_NOTES_MVP, MAX_DAILY_STT_RECOGNITIONS_MVP
from inline_keyboards import get_main_menu_keyboard, PageNavigation
from services.common import get_or_create_user

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start."""
    await state.clear()
    await get_or_create_user(message.from_user)

    # --- НОВЫЙ ТЕКСТ СТАРТОВОГО СООБЩЕНИЯ (ВАРИАНТ 2) ---
    start_text = (
        "🎙️ <b>Привет! Я — VoiceNote AI.</b>\n\n"
        "Я превращаю ваши голосовые мысли в идеально структурированные заметки. "
        "Больше не нужно ничего записывать вручную!\n\n"
        "<b>Как это работает?</b>\n"
        "Просто отправьте мне голосовое сообщение, и я мгновенно:\n\n"
        "1. 🔍 <b>Распознаю вашу речь</b> с высокой точностью).\n"
        "2. ✍️ <b>Улучшу текст:</b> исправлю ошибки, расставлю знаки препинания и "
        "отформатирую его с помощью AI).\n"
        "3. 🎯 <b>Извлеку главное:</b> найду в тексте задачи, даты, имена и "
        "создам умное напоминание, если потребуется.\n\n"
        "Готовы попробовать? <b>Запишите и отправьте мне голосовое сообщение прямо сейчас!</b> 👇"
    )

    await message.answer(
        start_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"  # Используем HTML для лучшего форматирования
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help."""
    creator_contact = "@useranybody"
    help_text = f"""
👋 Привет! Я **VoiceNote AI** – твой умный помощник для голосовых заметок.

Я использую технологию распознавания речи и продвинутый AI для анализа текста.

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
   - Каждую заметку можно **удалить**, **выполнить** или **просмотреть подробно**.

⚙️ **Настройки**
   - В Профиле ты можешь зайти в Настройки и указать свой часовой пояс и время для напоминаний по-умолчанию.

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