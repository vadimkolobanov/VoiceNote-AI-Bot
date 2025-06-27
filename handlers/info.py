# handlers/info.py
import logging
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hitalic, hcode
from aiogram.utils.keyboard import InlineKeyboardBuilder

from inline_keyboards import get_info_keyboard, InfoAction, get_main_menu_keyboard
from config import CREATOR_CONTACT, DONATION_URL

logger = logging.getLogger(__name__)
router = Router()

HOW_TO_USE_TEXT = f"""
{hbold("❓ Как пользоваться ботом")}

1️⃣ {hbold("Отправьте мне что угодно")}
Просто запишите и отправьте голосовое, или напишите (а также перешлите) текстовое сообщение. Я автоматически:
- Распознаю речь (если это аудио).
- Проанализирую текст и извлеку из него детали (задачи, даты, места).
- {hbold("Мгновенно сохраню заметку")} и поставлю напоминание.
- Предложу кнопку {hbold("Отменить")} под сообщением, если вы передумаете.

2️⃣ {hbold("Управляйте заметками")}
- Нажмите {hitalic("📝 Мои заметки")}, чтобы увидеть список активных задач.
- Задачи с ближайшим сроком выполнения всегда наверху.
- Нажмите на любую заметку, чтобы {hbold("просмотреть, отредактировать, изменить категорию, прослушать аудио или удалить")} ее.
- Выполненные задачи попадают в {hitalic("🗄️ Архив")}.

3️⃣ {hbold("Добавляйте важные даты")}
- В разделе {hitalic("👤 Профиль → 🎂 Дни рождения")} можно сохранять дни рождения и годовщины. Бот будет напоминать о них каждый год.

4️⃣ {hbold("Настройте под себя")}
- В разделе {hitalic("👤 Профиль → ⚙️ Настройки")} обязательно установите свой {hbold("часовой пояс")}.
- {hbold("⭐ VIP-пользователи")} могут настроить время напоминаний по умолчанию, предварительные уведомления и утренние сводки.
"""

VIP_FEATURES_TEXT = f"""
{hbold("⭐ Возможности VIP-статуса")}

VIP-статус открывает полный потенциал вашего AI-помощника и превращает его в настоящего проактивного ассистента.

🔁 {hbold("Повторяющиеся задачи")}
Автоматизируйте рутину! Создавайте задачи, которые будут повторяться ежедневно, еженедельно или ежемесячно.
{hitalic("Пример: «Каждый понедельник в 10 совещание»")}

☀️ {hbold("Утренняя сводка")}
Начинайте день с ясным планом. Каждое утро в 9:00 бот будет присылать вам персональный дайджест с задачами на сегодня и ближайшими днями рождения.

✅ {hbold("Безлимитные заметки и распознавания")}
Снимаются все ограничения на количество активных заметок и ежедневных распознаваний речи.

🧠 {hbold("Умные напоминания по умолчанию")}
Если вы сказали "завтра", не уточнив время, бот поставит напоминание на то время, которое вы указали в настройках.

🔔 {hbold("Предварительные напоминания")}
Настройте получение напоминаний заранее (например, за час до дедлайна).

⏰ {hbold("Отложенные напоминания (Snooze)")}
Не готовы выполнить задачу прямо сейчас? Нажмите кнопку "Отложить" в уведомлении.

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