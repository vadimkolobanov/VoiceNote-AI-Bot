# handlers/info.py
import logging
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hitalic

from inline_keyboards import get_info_keyboard, InfoAction, get_main_menu_keyboard
from config import CREATOR_CONTACT

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
Настройте получение напоминаний заранее (например, за 1 час или за сутки до срока), чтобы подготовиться к событию.

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


# Хендлер для кнопки "🏠 Главное меню" из этого раздела
@router.callback_query(F.data == "go_to_main_menu")
async def back_to_main_menu_from_info(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🏠 Вы в главном меню.", reply_markup=get_main_menu_keyboard())
    await callback.answer()