# handlers/commands.py
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.markdown import hbold, hlink

from config import (
    MAX_NOTES_MVP, MAX_DAILY_STT_RECOGNITIONS_MVP, CREATOR_CONTACT,
    NEWS_CHANNEL_URL, CHAT_URL
)
from services.common import get_or_create_user
from inline_keyboards import get_main_menu_keyboard, SettingsAction

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start с улучшенным приветствием."""
    await state.clear()
    user_profile = await get_or_create_user(message.from_user)

    user_timezone = user_profile.get('timezone', 'UTC')
    timezone_warning = ""
    if user_timezone == 'UTC':
        timezone_warning = (
            f"\n\n<b>⚠️ Настройте часовой пояс!</b>\n"
            f"Чтобы напоминания приходили вовремя, пожалуйста, "
            f"укажите ваш часовой пояс в настройках."
        )

    community_links = []
    if NEWS_CHANNEL_URL:
        community_links.append(hlink("📢 Новостной канал", NEWS_CHANNEL_URL))
    if CHAT_URL:
        community_links.append(hlink("💬 Чат для обсуждений", CHAT_URL))

    community_block = ""
    if community_links:
        community_block = "\n\n" + " | ".join(community_links)

    # --- ИЗМЕНЕНИЕ В ТЕКСТЕ ---
    start_text = (
        f"👋 Привет, {hbold(message.from_user.first_name)}!\n\n"
        f"Я — <b>VoiceNote AI</b>, ваш личный помощник для создания умных заметок.\n\n"
        f"Просто <b>отправьте мне голосовое</b> или <b>перешлите текстовое сообщение</b>, и я сделаю всю магию за вас!\n\n"
        f"<b>Как это работает?</b>\n"
        f"1️⃣ <b>Запишите или перешлите идею:</b> <i>«Напомни завтра купить молоко и позвонить маме в семь вечера»</i>\n"
        f"2️⃣ <b>Отправьте мне:</b> Я распознаю речь (для аудио) и проанализирую текст.\n"
        f"3️⃣ <b>Получите результат:</b>\n"
        f"<code>"
        f"📝 Задача: Купить молоко, позвонить маме\n"
        f"🗓️ Срок: 13.06.2025 19:00</code>\n"
        f"<i>(И бот автоматически поставит напоминание!)</i>\n\n"
        f"Используйте кнопки ниже для навигации или <b>сразу отправляйте сообщение!</b>"
        f"{timezone_warning}"
        f"{community_block}"
    )

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
        parse_mode="HTML",
        disable_web_page_preview=True
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help."""
    # --- ИЗМЕНЕНИЕ В ТЕКСТЕ ---
    help_text = f"""
👋 Привет! Я <b>VoiceNote AI</b> – твой умный помощник для заметок.

Я использую технологию распознавания речи от Яндекса (<i>Yandex SpeechKit</i>) и продвинутый AI (<i>DeepSeek</i>) для анализа текста.

<b>Вот что я умею:</b>

🎤 <b>Создание заметок:</b>
   - Отправь мне <b>голосовое сообщение</b>.
   - Или <b>перешли любое текстовое сообщение</b> из другого чата.
   - Я проанализирую текст, извлеку важные детали и предложу сохранить заметку.
   - Лимиты на бесплатном тарифе: <b>{MAX_NOTES_MVP} активных заметок</b> и <b>{MAX_DAILY_STT_RECOGNITIONS_MVP} распознаваний голоса в день</b>.

📝 <b>Мои заметки:</b>
   - Нажми кнопку "📝 Мои заметки" в главном меню (или команда /my_notes).
   - Ты увидишь список своих заметок с возможностью навигации по страницам.

👤 <b>Профиль и Настройки:</b>
   - Кнопка "👤 Профиль" в главном меню покажет основную информацию о тебе.
   - Через профиль ты можешь перейти в "⚙️ Настройки", чтобы установить свой <b>часовой пояс</b> и управлять <b>VIP-функциями</b>.
   - <b>Обязательно установите свой часовой пояс для корректной работы напоминаний!</b>

🤖 <b>Основные команды:</b>
   - /start - Запустить бота / Главное меню.
   - /help - Показать это сообщение.
   - /my_notes - Показать список моих заметок.

---
Предложения или ошибки? Сообщи моему создателю: {CREATOR_CONTACT}
"""
    await message.answer(help_text, parse_mode="HTML", disable_web_page_preview=True)