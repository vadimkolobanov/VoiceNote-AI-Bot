# handlers/info.py
import logging
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hitalic, hcode
# --- ИЗМЕНЕНИЕ: Добавляем нужный импорт ---
from aiogram.utils.keyboard import InlineKeyboardBuilder

from inline_keyboards import get_info_keyboard, InfoAction, get_main_menu_keyboard
from config import CREATOR_CONTACT, DONATION_URL

logger = logging.getLogger(__name__)
router = Router()

# Тексты вынесены для удобства редактирования
HOW_TO_USE_TEXT = f"""
{hbold("❓ Как пользоваться ботом")}

1️⃣ {hbold("Отправьте голосовое сообщение")}
Просто запишите и отправьте мне голосовое. Я автоматически:
- Распознаю речь.
- Исправлю текст и извлеку из него детали (задачи, даты, места).
- Предложу сохранить заметку.

2️⃣ {hbold("Управляйте заметками")}
- Нажмите {hitalic("📝 Мои заметки")}, чтобы увидеть список активных задач.
- Задачи с ближайшим сроком выполнения всегда наверху.
- Нажмите на любую заметку, чтобы {hbold("просмотреть, отредактировать, изменить категорию, прослушать аудио или удалить")} ее.
- Выполненные задачи попадают в {hitalic("🗄️ Архив")}.

3️⃣ {hbold("Настройте под себя")}
- В разделе {hitalic("👤 Профиль → ⚙️ Настройки")} вы можете:
  - Установить свой {hbold("часовой пояс")} для корректного отображения времени.
  - Настроить {hbold("время напоминаний по умолчанию")} (⭐ VIP-функция).
  - Выбрать, за сколько времени получать {hbold("предварительные напоминания")} (⭐ VIP-функция).
"""

VIP_FEATURES_TEXT = f"""
{hbold("⭐ Возможности VIP-статуса")}

VIP-статус открывает полный потенциал вашего ИИ-помощника:

✅ {hbold("Безлимитные заметки и распознавания")}
Снимаются все ограничения на количество активных заметок и ежедневных распознаваний речи.

🧠 {hbold("Умные напоминания по умолчанию")}
Если вы сказали "завтра" или "в пятницу", не уточнив время, бот поставит напоминание на то время, которое вы указали в настройках (например, 09:00).
{hitalic("У Free-пользователей в этом случае напоминание не создается.")}

🔔 {hbold("Предварительные напоминания")}
Настройте получение напоминаний заранее (например, за час до дедлайна), чтобы подготовиться к событию.

⏰ {hbold("Отложенные напоминания (Snooze)")}
Не готовы выполнить задачу прямо сейчас? Нажмите кнопку "Отложить" в уведомлении, и я напомню вам позже.

---
Чтобы получить тестовый VIP-статус, перейдите в {hitalic("⚙️ Настройки")} и выберите любой пункт с пометкой ⭐ VIP.
"""

INFO_MAIN_TEXT = f"""
{hbold("ℹ️ Информация и Помощь")}

Здесь собрана полезная информация о боте.

- {hbold("Как пользоваться?")} — краткая инструкция по основным функциям.
- {hbold("VIP-возможности")} — подробное описание преимуществ VIP-статуса.

Для предложений или сообщений об ошибках, пожалуйста, свяжитесь с создателем: {CREATOR_CONTACT}
"""

DONATE_TEXT = f"""
{hbold("❤️ Поддержать проект")}

Привет! Я — VoiceNote AI, и я существую благодаря труду одного независимого разработчика.

Если бот оказался для вас полезным и вы хотите помочь проекту развиваться, вы можете поддержать его любой комфортной суммой. Собранные средства пойдут на оплату серверов и API.

{hbold("Как сделать донат:")}
1. Нажмите на кнопку ниже, чтобы перейти на страницу доната (ЮMoney).
2. {hbold("ОЧЕНЬ ВАЖНО:")} Отправьте ваш Telegram ID, чтобы я мог вас поблагодарить и выдать VIP-статус.

Ваш Telegram ID: {hcode('{user_id}')} (нажмите, чтобы скопировать)

Спасибо вам за поддержку!
"""


@router.callback_query(InfoAction.filter(F.action == "main"))
async def show_info_main(callback: types.CallbackQuery):
    await callback.message.edit_text(INFO_MAIN_TEXT, parse_mode="HTML", reply_markup=get_info_keyboard(),
                                     disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(InfoAction.filter(F.action == "how_to_use"))
async def show_how_to_use(callback: types.CallbackQuery):
    await callback.message.edit_text(HOW_TO_USE_TEXT, parse_mode="HTML", reply_markup=get_info_keyboard())
    await callback.answer()


@router.callback_query(InfoAction.filter(F.action == "vip_features"))
async def show_vip_features(callback: types.CallbackQuery):
    await callback.message.edit_text(VIP_FEATURES_TEXT, parse_mode="HTML", reply_markup=get_info_keyboard())
    await callback.answer()


@router.callback_query(InfoAction.filter(F.action == "donate"))
async def show_donate_info(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    text = DONATE_TEXT.format(user_id=user_id)

    if not DONATION_URL:
        await callback.answer("К сожалению, функция поддержки временно недоступна.", show_alert=True)
        return

    # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
    # Убираем types. и используем импортированный InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="Перейти к поддержке (ЮMoney)", url=DONATION_URL)
    builder.button(text="⬅️ Назад", callback_data=InfoAction(action="main").pack())

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup(),
                                     disable_web_page_preview=True)
    await callback.answer()


# Хендлер для кнопки "🏠 Главное меню" из этого раздела
@router.callback_query(F.data == "go_to_main_menu")
async def back_to_main_menu_from_info(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🏠 Вы в главном меню.", reply_markup=get_main_menu_keyboard())
    await callback.answer()