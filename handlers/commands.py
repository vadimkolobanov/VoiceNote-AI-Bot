# handlers/commands.py
from aiogram import Router, types
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.markdown import hbold, hlink, hcode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import DONATION_URL

from config import (
    MAX_NOTES_MVP, MAX_DAILY_STT_RECOGNITIONS_MVP, CREATOR_CONTACT,
    NEWS_CHANNEL_URL, CHAT_URL
)
from services.common import get_or_create_user
from inline_keyboards import get_main_menu_keyboard, SettingsAction
import database_setup as db

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()

    was_new_user = await db.get_user_profile(message.from_user.id) is None
    user_profile = await get_or_create_user(message.from_user)

    if was_new_user:
        await db.log_user_action(message.from_user.id, 'user_registered')

    user_timezone = user_profile.get('timezone', 'UTC')
    is_vip = user_profile.get('is_vip', False)
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

    start_text = (
        f"👋 Привет, {hbold(message.from_user.first_name)}!\n\n"
        f"Я — <b>VoiceNote AI</b>, ваш личный AI-ассистент.\n\n"
        f"Просто отправьте мне <b>голосовое</b> или <b>текстовое сообщение</b>, и я превращу его в умную заметку с напоминанием. "
        f"Всё происходит автоматически!\n\n"
        f"Используйте кнопки ниже для навигации или <b>сразу отправляйте сообщение!</b>"
        f"{timezone_warning}"
        f"{community_block}"
    )

    reply_markup = get_main_menu_keyboard(is_vip=is_vip)

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
    help_text = f"""
👋 Привет! Я <b>VoiceNote AI</b> – твой умный помощник для заметок.

Я использую технологию распознавания речи от Яндекса и продвинутый AI для анализа текста.

<b>Вот что я умею:</b>

🎤 <b>Создание заметок:</b>
   - Отправь мне <b>голосовое</b> или <b>любое текстовое сообщение</b>.
   - Я проанализирую его, автоматически сохраню как умную заметку и поставлю напоминание.
   - Если я ошиблась, вы сможете отменить создание заметки кнопкой под сообщением.
   - Лимиты на бесплатном тарифе: <b>{MAX_NOTES_MVP} активных заметок</b> и <b>{MAX_DAILY_STT_RECOGNITIONS_MVP} распознаваний голоса в день</b>.

🎂 <b>Дни рождения:</b>
   - Сохраняй дни рождения и годовщины, и я буду напоминать о них каждый год.

👤 <b>Профиль и Настройки:</b>
   - В "Профиле" ты найдешь свою статистику и сможешь перейти в "Настройки".
   - <b>Обязательно установи свой часовой пояс</b> для корректной работы всех напоминаний!

---
⭐ <b>Возможности VIP-статуса:</b>

✅ <b>Безлимиты:</b> Никаких ограничений на количество заметок и распознаваний.
🔁 <b>Повторяющиеся задачи:</b> "Напоминай каждый понедельник сдавать отчет".
☀️ <b>Утренняя сводка:</b> План на день с задачами и днями рождения каждое утро в 9:00.
🧠 <b>Умные напоминания:</b> Если в заметке только дата, бот сам поставит напоминание на удобное время.
🔔 <b>Предварительные напоминания:</b> Получай уведомления заранее (за час, за день).
⏰ <b>Отложить напоминание:</b> Не готов выполнить задачу? Нажми "Отложить" в уведомлении.
📥 <b>Импорт дат:</b> Загружай дни рождения из файла.
---

🤖 <b>Основные команды:</b>
   - /start - Запустить бота / Главное меню.
   - /help - Показать это сообщение.
   - /my_notes - Показать список моих заметок.

Предложения или ошибки? Сообщи моему создателю: {CREATOR_CONTACT}
"""
    await message.answer(help_text, parse_mode="HTML", disable_web_page_preview=True)


DONATE_TEXT = f"""
{hbold("❤️ Поддержать проект")}

Привет! Я — VoiceNote AI, и я существую благодаря труду одного независимого разработчика.

Если бот оказался для вас полезным и вы хотите помочь проекту развиваться, вы можете поддержать его любой комфортной суммой. Собранные средства пойдут на оплату серверов и API.

{hbold("Как сделать донат:")}
1. Нажмите на кнопку ниже, чтобы перейти на страницу доната (ЮMoney).
2. Выберите желаемую сумму.
3. Подтвердите платеж.

Ежемесячное содержание бота составляет около 1000 рублей без учета рекламы.

{hbold("Ваши взносы помогут:")}
- Разработке новых функций.
- Поддержке серверов и API.
- Поддержке бота в Telegram.
- Оплате более мощных ИИ
- В проектировании новых интеграций.

{hbold("Спасибо за поддержку!")}

Спасибо вам за поддержку!
"""


@router.callback_query(F.data == "show_donate_info")
async def show_donate_info_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    text = DONATE_TEXT.format(user_id=user_id)

    if not DONATION_URL:
        await callback.answer("К сожалению, функция поддержки временно недоступна.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="Перейти к поддержке (ЮMoney)", url=DONATION_URL)
    builder.button(text="🏠 Главное меню", callback_data="go_to_main_menu")

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
        disable_web_page_preview=True
    )
    await callback.answer()


@router.callback_query(F.data == "go_to_main_menu")
async def go_to_main_menu_handler(callback: types.CallbackQuery, state: FSMContext):
    """Универсальный обработчик для возврата в главное меню."""
    await state.clear()
    user_profile = await db.get_user_profile(callback.from_user.id)
    is_vip = user_profile.get('is_vip', False) if user_profile else False
    try:
        await callback.message.edit_text(
            "🏠 Вы в главном меню.",
            reply_markup=get_main_menu_keyboard(is_vip=is_vip)
        )
    except Exception:
        await callback.message.answer(
            "🏠 Вы в главном меню.",
            reply_markup=get_main_menu_keyboard(is_vip=is_vip)
        )
    await callback.answer()