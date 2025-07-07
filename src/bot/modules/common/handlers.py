# src/bot/modules/common/handlers.py
import logging
from aiogram import F, Bot, Router, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hlink, hcode, hitalic

from ....core import config
from ....database import user_repo, note_repo
from ....services.scheduler import add_reminder_to_scheduler
from ..common_utils.callbacks import InfoAction, SettingsAction
from ..notes.handlers import list_view, shopping_list  # Импортируем хендлеры из модуля notes
from .keyboards import get_main_menu_keyboard, get_info_keyboard, get_donation_keyboard

logger = logging.getLogger(__name__)
router = Router()

# --- Текстовые константы ---

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

🤝 {hbold("Совместный доступ к заметкам")}
Делитесь задачами и списками покупок с семьей или коллегами.

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

Для предложений или сообщений об ошибках, пожалуйста, свяжитесь с создателем: {config.CREATOR_CONTACT}
"""

DONATE_TEXT = f"""
{hbold("❤️ Поддержать проект")}

Привет! Я — VoiceNote AI, и я существую благодаря труду одного независимого разработчика.

Если бот оказался для вас полезным и вы хотите помочь проекту развиваться, вы можете поддержать его любой комфортной суммой. Собранные средства пойдут на оплату серверов и API.

Ваши взносы помогут:
- Разработке новых функций.
- Поддержке серверов и API.
- Оплате более мощных ИИ.

Спасибо вам за поддержку!
"""


# --- Хендлеры ---

async def _send_welcome_message(message: types.Message, state: FSMContext, bot: Bot):
    """Отправляет приветственное сообщение."""
    await state.clear()

    user_profile = await user_repo.get_or_create_user(message.from_user)
    is_vip = user_profile.get('is_vip', False)

    timezone_warning = ""
    if user_profile.get('timezone', 'UTC') == 'UTC':
        timezone_warning = (
            f"\n\n{hbold('⚠️ ВАЖНО: Настройте ваш часовой пояс!')}\n"
            f"Без этого напоминания могут приходить в неправильное время. "
            f"Это займет 10 секунд."
        )

    community_links = []
    if config.NEWS_CHANNEL_URL:
        community_links.append(hlink("📢 Новостной канал", config.NEWS_CHANNEL_URL))
    if config.CHAT_URL:
        community_links.append(hlink("💬 Чат для обсуждений", config.CHAT_URL))
    community_block = "\n\n" + " | ".join(community_links) if community_links else ""

    start_text = (
        f"👋 Привет, {hbold(message.from_user.first_name)}!\n\n"
        f"Я — <b>VoiceNote AI</b>, ваш личный AI-ассистент.\n\n"
        f"Просто отправьте мне <b>голосовое</b> или <b>текстовое сообщение</b>, и я превращу его в умную заметку с напоминанием."
        f"{timezone_warning}{community_block}"
    )

    reply_markup = get_main_menu_keyboard(is_vip=is_vip)
    # Если нужно настроить таймзону, добавляем быструю кнопку
    if timezone_warning:
        tz_button = types.InlineKeyboardButton(
            text="🕒 Настроить часовой пояс",
            callback_data=SettingsAction(action="go_to_timezone").pack()
        )
        # Добавляем кнопку в новый ряд
        reply_markup.inline_keyboard.append([tz_button])

    await message.answer(start_text, reply_markup=reply_markup, disable_web_page_preview=True)


@router.message(Command(commands=["start"]))
async def cmd_start(message: types.Message, state: FSMContext, bot: Bot, command: CommandObject):
    """Обрабатывает команду /start, включая диплинки для шаринга."""
    args = command.args
    if args and args.startswith("share_"):
        token = args.split('_', 1)[1]
        token_data = await note_repo.get_share_token_data(token)

        if not token_data:
            await message.answer("❌ Эта пригласительная ссылка недействительна или уже была использована.")
            await _send_welcome_message(message, state, bot)
            return

        note_id = token_data['note_id']
        owner_id = token_data['owner_id']

        if message.from_user.id == owner_id:
            await message.answer("ℹ️ Вы не можете использовать свою собственную пригласительную ссылку.")
            await _send_welcome_message(message, state, bot)
            return

        recipient_profile = await user_repo.get_or_create_user(message.from_user)
        success = await note_repo.share_note_with_user(note_id, owner_id, message.from_user.id)

        if not success:
            await message.answer("🤔 Похоже, у вас уже есть доступ к этой заметке.")
        else:
            await note_repo.mark_share_token_as_used(token)
            owner_profile = await user_repo.get_user_profile(owner_id)
            note = await note_repo.get_note_by_id(note_id, message.from_user.id)
            if owner_profile and note:
                try:
                    await bot.send_message(
                        owner_id,
                        f"✅ Пользователь {hbold(message.from_user.first_name)} принял ваше приглашение к заметке «{hitalic(note.get('summary_text'))}»."
                    )
                except Exception as e:
                    logger.warning(f"Не удалось уведомить владельца {owner_id} о принятии приглашения: {e}")

        # Показываем заметку новому пользователю
        note = await note_repo.get_note_by_id(note_id, message.from_user.id)
        if note:
            await message.answer(f"🤝 Вы получили доступ к новой заметке!")
            if note.get('due_date'):
                note_data_for_scheduler = {**note, **recipient_profile}
                add_reminder_to_scheduler(bot, note_data_for_scheduler)
                logger.info(
                    f"Напоминание для общей заметки #{note_id} установлено для получателя {message.from_user.id}.")

            # Передаем управление в соответствующий хендлер модуля notes
            if note.get('category') == 'Покупки':
                await shopping_list.render_shopping_list(note_id, message, message.from_user.id)
            else:
                await list_view.view_note_detail_handler(message, state, note_id=note_id)
        else:
            await message.answer("❌ Произошла ошибка при получении доступа к заметке.")
            await _send_welcome_message(message, state, bot)
    else:
        await _send_welcome_message(message, state, bot)


@router.callback_query(F.data == "go_to_main_menu")
async def go_to_main_menu_handler(callback: types.CallbackQuery, state: FSMContext):
    """Возвращает пользователя в главное меню из любого места."""
    await state.clear()
    user_profile = await user_repo.get_user_profile(callback.from_user.id)
    is_vip = user_profile.get('is_vip', False) if user_profile else False
    try:
        await callback.message.edit_text(
            "🏠 Вы в главном меню.",
            reply_markup=get_main_menu_keyboard(is_vip=is_vip)
        )
    except Exception:
        # Если отредактировать не удалось (например, сообщение без текста), отправляем новое
        await callback.message.answer(
            "🏠 Вы в главном меню.",
            reply_markup=get_main_menu_keyboard(is_vip=is_vip)
        )
    await callback.answer()


@router.callback_query(InfoAction.filter(F.action == "main"))
async def show_info_main(callback: types.CallbackQuery):
    await callback.message.edit_text(INFO_MAIN_TEXT, reply_markup=get_info_keyboard(), disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(InfoAction.filter(F.action == "how_to_use"))
async def show_how_to_use(callback: types.CallbackQuery):
    await callback.message.edit_text(HOW_TO_USE_TEXT, reply_markup=get_info_keyboard())
    await callback.answer()


@router.callback_query(InfoAction.filter(F.action == "vip_features"))
async def show_vip_features(callback: types.CallbackQuery):
    await callback.message.edit_text(VIP_FEATURES_TEXT, reply_markup=get_info_keyboard(), disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data == "show_donate_info")
async def show_donate_info_handler(callback: types.CallbackQuery):
    if not config.DONATION_URL:
        await callback.answer("К сожалению, функция поддержки временно недоступна.", show_alert=True)
        return
    await callback.message.edit_text(
        DONATE_TEXT,
        reply_markup=get_donation_keyboard(),
        disable_web_page_preview=True
    )
    await callback.answer()