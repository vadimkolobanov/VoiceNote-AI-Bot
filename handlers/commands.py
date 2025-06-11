# handlers/commands.py
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.markdown import hbold, hitalic, hcode

from config import MAX_NOTES_MVP, MAX_DAILY_STT_RECOGNITIONS_MVP, CREATOR_CONTACT
from services.common import get_or_create_user
from inline_keyboards import get_main_menu_keyboard, SettingsAction

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start с улучшенным приветствием."""
    await state.clear()
    user_profile = await get_or_create_user(message.from_user)

    # --- Блок с часовым поясом (остается без изменений) ---
    user_timezone = user_profile.get('timezone', 'UTC')
    timezone_warning = ""
    if user_timezone == 'UTC':
        timezone_warning = (
            f"\n\n<b>⚠️ Настройте часовой пояс!</b>\n"
            f"Чтобы напоминания приходили вовремя, пожалуйста, "
            f"укажите ваш часовой пояс в настройках."
        )

    # --- НОВЫЙ, БОЛЕЕ ПОДРОБНЫЙ И ПОЛЕЗНЫЙ ТЕКСТ ---
    start_text = (
        f"👋 Привет, {hbold(message.from_user.first_name)}!\n\n"
        f"Я — <b>VoiceNote AI</b>, ваш личный помощник, который превращает голосовые сообщения в структурированные заметки.\n\n"
        f"Просто отправьте мне голосовое, и я сделаю всю магию за вас!\n\n"
        f"<b>Как это работает?</b>\n"
        f"1️⃣ <b>Запишите идею:</b> <i>«Напомни завтра купить молоко и позвонить маме в семь вечера»</i>\n"
        f"2️⃣ <b>Отправьте мне:</b> Я распознаю речь и проанализирую текст.\n"
        f"3️⃣ <b>Получите результат:</b>\n"
        f"<code>"
        f"📝 Задача: Купить молоко, позвонить маме\n"
        f"🗓️ Срок: 13.06.2025 19:00 </code>\n"
        f"<i>(И бот автоматически поставит напоминание заранее и в момент события! )</i>\n\n"
        f"Используйте кнопки ниже для навигации или <b>сразу отправляйте голосовое сообщение!</b>"
        f"{timezone_warning}"
    )

    # --- Логика клавиатуры (остается без изменений) ---
    reply_markup = get_main_menu_keyboard()
    if user_timezone == 'UTC':
        tz_button = types.InlineKeyboardButton(
            text="🕒 Настроить часовой пояс",
            callback_data=SettingsAction(action="go_to_timezone").pack()
        )
        reply_markup.inline_keyboard.append([tz_button])

    await message.answer(
        start_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help."""
    help_text = f"""
👋 Привет! Я <b>VoiceNote AI</b> – твой умный помощник для голосовых заметок.

Я использую технологию распознавания речи от Яндекса (<i>Yandex SpeechKit</i>) и продвинутый AI (<i>DeepSeek</i>) для анализа текста.

<b>Вот что я умею:</b>

🎤 <b>Создание заметок:</b>
   - Отправь мне голосовое сообщение.
   - Я распознаю твою речь, улучшу текст и извлеку важные детали.
   - Тебе будет предложено сохранить заметку.
   - В текущей версии действует лимит: <b>{MAX_NOTES_MVP} активных заметок</b>.
   - <b>{MAX_DAILY_STT_RECOGNITIONS_MVP} распознаваний голосовых в день</b>. 

📝 <b>Мои заметки:</b>
   - Нажми кнопку "📝 Мои заметки" в главном меню (или команда /my_notes).
   - Ты увидишь список своих заметок с возможностью навигации по страницам.
   - Каждую заметку можно <b>удалить</b> или <b>просмотреть подробно</b>.

👤 <b>Профиль и Настройки:</b>
   - Кнопка "👤 Профиль" в главном меню покажет основную информацию о тебе.
   - Через профиль ты можешь перейти в "⚙️ Настройки", чтобы установить свой <b>часовой пояс</b> и управлять <b>VIP-функциями</b>.
   - <b>Обязательно установите свой часовой пояс для корректной работы напоминаний!</b>

🤖 <b>Основные команды:</b>
   - /start - Запустить бота / Главное меню.
   - /help - Показать это сообщение.
   - /my_notes - Показать список моих заметок.

💡 <b>Советы:</b>
   - Говори четко и в относительно тихом месте.
   - Формулируй даты и задачи явно для лучшего анализа AI.

---
Предложения или ошибки? Сообщи моему создателю: {CREATOR_CONTACT}
"""
    await message.answer(help_text, parse_mode="HTML", disable_web_page_preview=True)