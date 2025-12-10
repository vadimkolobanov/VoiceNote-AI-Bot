# src/bot/modules/common/handlers.py
import logging
from aiogram import F, Bot, Router, types
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hlink, hcode, hitalic

from ...common_utils.callbacks import SettingsAction, InfoAction
from ...common_utils.states import OnboardingStates
from ....core import config
from ....database import user_repo, note_repo, chat_topic_repo
from ....services.scheduler import add_reminder_to_scheduler
from ....services.gamification_service import check_and_grant_achievements

from ..notes.handlers import list_view, shopping_list
from .keyboards import get_main_menu_keyboard, get_help_keyboard, get_donation_keyboard, get_guides_keyboard, \
    get_back_to_guides_keyboard

import secrets
import string
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = Router()

# --- Текстовые константы для гайдов ---

GUIDE_HABIT_TRACKER = f"""
{hbold("Как работает трекер привычек?")}

Это ваш личный тренер, который помогает внедрять полезные ритуалы в вашу жизнь.

1️⃣ {hbold("Создание привычек через интервью")}
- Зайдите в меню {hbold("💪 Мои привычки")} из главного меню.
- Нажмите {hbold("🚀 Сформировать первые привычки")}.
- {hbold("Просто напишите боту")}, что вы хотите делать. ИИ сам поймет частоту и время.
- {hitalic("Пример: «Хочу каждый день в 8 утра делать зарядку, по будням гулять с собакой, а по выходным читать книгу»")}

2️⃣ {hbold("Подтверждение")}
Бот покажет вам распознанный список для подтверждения. Если все верно — просто нажмите кнопку, и он начнет отслеживание.

3️⃣ {hbold("Ежедневный трекинг")}
- В указанное время бот пришлет напоминание.
- Под сообщением будут кнопки {hbold("✅ Выполнено")} и {hbold("❌ Пропустить")}. Ваша задача — просто нажать на одну из них.

4️⃣ {hbold("Статистика")}
Каждое воскресенье бот будет присылать вам красивый отчет с вашим прогрессом за неделю, чтобы вы видели свои успехи!
"""

GUIDE_MAIN_TEXT = f"""
📖 {hbold("Как пользоваться ботом")}

Здесь собраны подробные инструкции по всем функциям. Выберите интересующий вас раздел, чтобы узнать больше.
"""

GUIDE_CREATE_NOTE = f"""
{hbold("Как создать обычную заметку?")}

Это основная функция бота! Просто {hbold("отправьте или перешлите")} ему любое сообщение.

✍️ {hbold("Текстовое сообщение")}
Напишите, что нужно запомнить. Бот проанализирует текст, выделит главное и, если найдет дату и время, автоматически поставит напоминание.
{hitalic("Пример: «Не забыть позвонить маме завтра в 12:30»")}

🗣️ {hbold("Голосовое сообщение")}
Запишите аудио, и бот автоматически расшифрует его, превратив в полноценную текстовую заметку с напоминанием. Это идеальный способ делать записи на ходу.

После создания заметки под ней появится кнопка {hbold("Отменить")}, если вы передумали. Вы также можете {hbold("просмотреть, отредактировать")} или {hbold("удалить")} любую заметку через меню {hbold("📝 Мои заметки")}.
"""

GUIDE_ADD_BIRTHDAY = f"""
{hbold("Как записать день рождения?")}

Бот может ежегодно напоминать о днях рождения, годовщинах и других важных датах.

1.  Зайдите в {hbold("👤 Профиль")} из главного меню.
2.  Нажмите кнопку {hbold("🎂 Дни рождения")}.
3.  Выберите {hbold("➕ Добавить вручную")}.
4.  Следуйте инструкциям: сначала введите имя человека, затем его дату рождения.

Дату можно вводить в формате {hcode("ДД.ММ.ГГГГ")} (например, {hcode("25.12.1980")}) или просто {hcode("ДД.ММ")} ({hcode("25.12")}), если год не важен.
"""

GUIDE_SHOPPING_LIST = f"""
{hbold("Как создать и вести список покупок?")}

Это совместная функция, идеально подходящая для семьи.

1️⃣ {hbold("Создание списка")}
Отправьте боту сообщение, содержащее ключевые слова: {hbold("«купить», «список покупок», «добавить»")} и перечислите товары.
{hitalic("Пример: «Купить молоко, хлеб и яйца»")}
Бот создаст {hbold("единый активный список покупок")}. Все последующие товары, которые вы будете отправлять с этими же ключевыми словами, будут автоматически добавляться в него.

2️⃣ {hbold("Ведение списка")}
- Отмечайте купленные товары, просто нажимая на них в списке.
- Если список общий, все участники увидят изменения в реальном времени.
- В списке вы будете видеть, {hbold("кто из участников добавил")} тот или иной товар.

3️⃣ {hbold("Завершение")}
Когда все покупки сделаны, нажмите {hbold("🛒 Завершить и архивировать")}. Список переместится в архив, и при следующем запросе "купить" будет создан новый.
"""

GUIDE_SHARE_NOTE_AND_LIST = f"""
{hbold("Как поделиться списком или заметкой?")}

Любой заметкой или списком покупок можно поделиться с другим пользователем бота, чтобы просматривать и редактировать их совместно.

1.  Откройте нужную заметку (или список покупок), нажав на нее в меню {hbold("📝 Мои заметки")}.
2.  В меню действий под заметкой нажмите кнопку {hbold("🤝 Поделиться")}.
3.  Бот сгенерирует вашу {hbold("уникальную ссылку-приглашение")}.
4.  Отправьте эту ссылку человеку, с которым хотите поделиться.

Как только он перейдет по ссылке, то получит полный доступ к заметке или списку и будет видеть все изменения. Это идеально подходит для ведения общего списка покупок с семьей или планирования отпуска.
"""

GUIDE_SET_TIMEZONE = f"""
{hbold("Как настроить часовой пояс?")}

Это {hbold("важнейшая настройка")} для корректной работы всех напоминаний. Без неё уведомления могут приходить в неудобное время.

1.  Нажмите {hbold("⚙️ Настройки")} в главном меню или в профиле.
2.  Выберите пункт {hbold("🕒 Часовой пояс")}.
3.  Выберите ваш город из предложенных вариантов для быстрой настройки.
4.  Если вашего города нет, нажмите {hbold("⌨️ Ввести вручную")} и отправьте название в формате {hcode("Континент/Город")} (например, {hcode("Europe/Moscow")}).

После этого все напоминания будут приходить точно в срок по вашему местному времени.
"""

GUIDE_DAILY_DIGEST = f"""
{hbold("Что такое утренняя сводка? (⭐ VIP)")}

Утренняя сводка — это эксклюзивная функция для VIP-пользователей, которая помогает начать день продуктивно.

Каждое утро в 9:00 по вашему местному времени бот будет присылать вам персональное сообщение, в котором собраны:
- Все ваши {hbold("задачи и напоминания на сегодня")}.
- Ближайшие {hbold("дни рождения")} на неделе.

Это удобный способ получить быстрый обзор предстоящих дел, не заходя в списки.

{hbold("Как включить/выключить?")}
1.  Перейдите в {hbold("⚙️ Настройки")}.
2.  Нажмите кнопку {hbold("☀️ Включить/Выключить утреннюю сводку")}.
"""

HELP_MAIN_TEXT = f"""
{hbold("❓ Помощь")}

Здесь собрана полезная информация о боте.

- {hbold("Как пользоваться?")} — подробные инструкции по всем функциям.
- {hbold("Сообщить о проблеме")} — если что-то пошло не так или у вас есть предложение.

Для быстрой связи с создателем: {config.CREATOR_CONTACT}
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

async def _send_initial_welcome(message: types.Message, state: FSMContext, bot: Bot):
    """Отправляет приветствие СТАРЫМ пользователям или при диплинке."""
    await state.clear()

    user_profile = await user_repo.get_or_create_user(message.from_user)
    is_vip = user_profile.get('is_vip', False)

    active_shopping_list = await note_repo.get_active_shopping_list(message.from_user.id)
    has_active_list = active_shopping_list is not None

    timezone_warning = ""
    if not user_profile.get('has_completed_onboarding') and user_profile.get('timezone', 'UTC') == 'UTC':
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

    reply_markup = get_main_menu_keyboard(is_vip=is_vip, has_active_list=has_active_list)

    if timezone_warning:
        tz_button = types.InlineKeyboardButton(
            text="🕒 Настроить часовой пояс",
            callback_data=SettingsAction(action="go_to_timezone").pack()
        )
        reply_markup.inline_keyboard.append([tz_button])

    await message.answer(start_text, reply_markup=reply_markup, disable_web_page_preview=True)


async def show_main_menu(message: types.Message, state: FSMContext, bot: Bot):
    """
    Чистое отображение главного меню. Вызывается из других модулей, например, после обучения.
    """
    await state.clear()
    user_profile = await user_repo.get_or_create_user(message.from_user)

    # Добавляем проверку на случай, если даже создание пользователя по какой-то причине не удалось
    if not user_profile:
        logger.error(
            f"Не удалось получить или создать профиль для пользователя {message.from_user.id} в show_main_menu")
        await message.answer(
            "Произошла ошибка при загрузке вашего профиля. Пожалуйста, попробуйте нажать /start еще раз.")
        return
    
    is_vip = user_profile.get('is_vip', False)
    active_shopping_list = await note_repo.get_active_shopping_list(message.from_user.id)
    has_active_list = active_shopping_list is not None
    
    # Gamification виджеты
    user_level = user_profile.get('level', 1)
    user_xp = user_profile.get('xp', 0)
    from ....database.user_repo import get_xp_for_level
    xp_for_current_level = get_xp_for_level(user_level)
    xp_for_next_level = get_xp_for_level(user_level + 1)
    xp_progress = user_xp - xp_for_current_level
    xp_needed = xp_for_next_level - xp_for_current_level
    progress_percent = int((xp_progress / xp_needed * 100)) if xp_needed > 0 else 100
    
    # Подсчет заметок
    total_notes, voice_notes = await note_repo.count_total_and_voice_notes(message.from_user.id)
    
    # Проверка на предложение VIP (после 3-5 заметок)
    vip_suggestion = ""
    if not is_vip and 3 <= total_notes <= 5:
        vip_suggestion = f"\n\n🚀 {hbold('Совет:')} После создания еще {5 - total_notes} заметок я предложу вам VIP-функции!"
    
    # Виджет для пользователей без заметок
    no_notes_widget = ""
    if total_notes == 0:
        no_notes_widget = f"\n\n💡 {hbold('Начните прямо сейчас!')} Отправьте мне любую мысль, и я создам вашу первую заметку."

    text = (
        f"🏠 {hbold('Главное меню')}\n\n"
        f"📊 {hbold(f'Уровень {user_level}')} | {progress_percent}% до следующего\n"
        f"📝 Создано заметок: {total_notes}\n\n"
        f"💬 {hbold('Что я умею:')}\n"
        f"• Создавать заметки из текста или голоса\n"
        f"• Напоминать о важных делах\n"
        f"• Ведить списки покупок\n"
        f"• Отслеживать дни рождения{no_notes_widget}{vip_suggestion}\n\n"
        f"👉 {hitalic('Просто отправьте мне любое сообщение!')}"
    )
    keyboard = get_main_menu_keyboard(is_vip=is_vip, has_active_list=has_active_list)

    try:
        await message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await message.answer(text, reply_markup=keyboard)


@router.message(Command(commands=["start"]))
async def cmd_start(message: types.Message, state: FSMContext, bot: Bot, command: CommandObject):
    """Обрабатывает команду /start, включая диплинки и запуск обучения."""
    from ..onboarding.handlers import start_onboarding

    args = command.args
    user_profile = await user_repo.get_or_create_user(message.from_user)

    if args and args.startswith("share_"):
        token = args.split('_', 1)[1]
        token_data = await note_repo.get_share_token_data(token)

        if not token_data:
            await message.answer("❌ Эта пригласительная ссылка недействительна или уже была использована.")
            await _send_initial_welcome(message, state, bot)
            return

        note_id = token_data['note_id']
        owner_id = token_data['owner_id']

        if message.from_user.id == owner_id:
            await message.answer("ℹ️ Вы не можете использовать свою собственную пригласительную ссылку.")
            await _send_initial_welcome(message, state, bot)
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

        note = await note_repo.get_note_by_id(note_id, message.from_user.id)
        if note:
            await message.answer(f"🤝 Вы получили доступ к новой заметке!")
            if note.get('due_date'):
                note_data_for_scheduler = {**note, **recipient_profile}
                add_reminder_to_scheduler(bot, note_data_for_scheduler)
                logger.info(
                    f"Напоминание для общей заметки #{note_id} установлено для получателя {message.from_user.id}.")

            if note.get('category') == 'Покупки':
                await shopping_list.render_shopping_list(message, note_id, message.from_user.id)
            else:
                await list_view.view_note_detail_handler(message, state, note_id=note_id)
        else:
            await message.answer("❌ Произошла ошибка при получении доступа к заметке.")
            await _send_initial_welcome(message, state, bot)

    else:
        if not user_profile.get('has_completed_onboarding'):
            await start_onboarding(message, state)
        else:
            await show_main_menu(message, state, bot)


@router.message(Command(commands=["code"]))
async def cmd_code(message: types.Message):
    """Отправляет пользователю код для входа в веб-приложение."""
    user_id = message.from_user.id
    code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    expires_at = datetime.now() + timedelta(minutes=10)

    await user_repo.set_mobile_activation_code(user_id, code, expires_at)

    await message.answer(
        f"📱 Ваш код для входа в веб-приложение:\n\n"
        f"{hcode(code)}\n\n"
        f"Код действителен 10 минут."
    )


@router.message(Command(commands=["topic", "topics"]))
async def cmd_topic_settings(message: types.Message):
    """
    Настройка топиков для обработки сообщений ботом.
    Работает только в группах/супергруппах с топиками.
    """
    # Проверяем, что это группа или супергруппа
    if message.chat.type not in ('group', 'supergroup'):
        await message.reply(
            "ℹ️ Эта команда работает только в группах с топиками.\n\n"
            "В личных чатах бот обрабатывает все сообщения автоматически."
        )
        return
    
    chat_id = message.chat.id
    topic_id = getattr(message, 'message_thread_id', None)
    
    # Получаем текущие настройки
    settings = await chat_topic_repo.get_chat_topic_settings(chat_id)
    
    if not settings:
        text = (
            f"📋 {hbold('Настройки топиков')}\n\n"
            f"Сейчас бот не обрабатывает сообщения ни в одном топике.\n\n"
        )
    else:
        text = (
            f"📋 {hbold('Настройки топиков')}\n\n"
            f"{hbold('Активные топики:')}\n"
        )
        for setting in settings:
            function_type = setting['function_type']
            function_name = {
                'all': 'Все функции',
                'notes': 'Заметки',
                'shopping_list': 'Список покупок',
                'reminders': 'Напоминания'
            }.get(function_type, function_type)
            text += f"• Топик {hcode(str(setting['topic_id']))}: {function_name}\n"
        text += "\n"
    
    # Если команда вызвана из топика, показываем кнопки для управления
    if topic_id is not None:
        # Проверяем, настроен ли текущий топик
        is_configured = await chat_topic_repo.is_topic_allowed(chat_id, topic_id, 'all')
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        if is_configured:
            # Топик уже настроен - можно удалить
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text="❌ Отключить обработку в этом топике",
                    callback_data=f"topic_disable:{chat_id}:{topic_id}"
                )
            ])
            text += f"✅ Текущий топик {hcode(str(topic_id))} настроен для обработки."
        else:
            # Топик не настроен - можно добавить
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text="✅ Включить обработку в этом топике",
                    callback_data=f"topic_enable:{chat_id}:{topic_id}"
                )
            ])
            text += f"ℹ️ Текущий топик {hcode(str(topic_id))} не настроен. Бот не будет реагировать на сообщения здесь."
        
        text += "\n\n💡 Используйте кнопки ниже для управления."
    else:
        text += (
            f"💡 {hbold('Как настроить топик:')}\n"
            "1. Перейдите в нужный топик (например, «Список покупок»)\n"
            "2. В этом топике вызовите команду {hcode('/topic')}\n"
            "3. Нажмите кнопку «✅ Включить обработку в этом топике»\n\n"
            f"{hbold('После настройки:')}\n"
            "Бот будет обрабатывать текстовые и голосовые сообщения только в настроенных топиках.\n"
            "В обычном чате (без топиков) и в ненастроенных топиках бот молчит."
        )
        keyboard = None
    
    await message.reply(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("topic_enable:"))
async def enable_topic_handler(callback: types.CallbackQuery):
    """Включает обработку сообщений в топике."""
    try:
        _, chat_id_str, topic_id_str = callback.data.split(":")
        chat_id = int(chat_id_str)
        topic_id = int(topic_id_str)
        
        # Добавляем настройку для всех функций
        success = await chat_topic_repo.add_topic_setting(chat_id, topic_id, 'all')
        
        if success:
            await callback.answer("✅ Топик настроен! Бот теперь будет обрабатывать сообщения здесь.")
            # Обновляем сообщение
            await callback.message.edit_text(
                f"✅ Топик {hcode(str(topic_id))} настроен для обработки всех сообщений.\n\n"
                f"Бот будет реагировать на текстовые и голосовые сообщения в этом топике.",
                parse_mode="HTML"
            )
        else:
            await callback.answer("❌ Ошибка при настройке топика", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка при включении топика: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("topic_disable:"))
async def disable_topic_handler(callback: types.CallbackQuery):
    """Отключает обработку сообщений в топике."""
    try:
        _, chat_id_str, topic_id_str = callback.data.split(":")
        chat_id = int(chat_id_str)
        topic_id = int(topic_id_str)
        
        # Удаляем все настройки для топика
        success = await chat_topic_repo.remove_topic_setting(chat_id, topic_id)
        
        if success:
            await callback.answer("✅ Обработка в топике отключена.")
            # Обновляем сообщение
            await callback.message.edit_text(
                f"❌ Топик {hcode(str(topic_id))} отключен.\n\n"
                f"Бот больше не будет реагировать на сообщения в этом топике.",
                parse_mode="HTML"
            )
        else:
            await callback.answer("❌ Ошибка при отключении топика", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка при отключении топика: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "go_to_main_menu")
async def go_to_main_menu_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await show_main_menu(callback.message, state, bot)
    await callback.answer()


@router.callback_query(F.data == "dismiss_vip_offer")
async def dismiss_vip_offer_handler(callback: types.CallbackQuery):
    """Обрабатывает отклонение предложения VIP."""
    await callback.message.delete()
    await callback.answer("Хорошо, вы всегда можете получить VIP позже в настройках!")


@router.callback_query(InfoAction.filter(F.action == "main"))
async def show_help_main(callback: types.CallbackQuery):
    await callback.message.edit_text(HELP_MAIN_TEXT, reply_markup=get_help_keyboard(), disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(InfoAction.filter(F.action == "guides"))
async def show_guides_list(callback: types.CallbackQuery):
    await callback.message.edit_text(GUIDE_MAIN_TEXT, reply_markup=get_guides_keyboard())
    await callback.answer()


@router.callback_query(InfoAction.filter(F.action == "guide_topic"))
async def show_specific_guide(callback: types.CallbackQuery, callback_data: InfoAction):
    guides = {
        "create_note": GUIDE_CREATE_NOTE,
        "add_birthday": GUIDE_ADD_BIRTHDAY,
        "shopping_list": GUIDE_SHOPPING_LIST,
        "share_note": GUIDE_SHARE_NOTE_AND_LIST,
        "set_timezone": GUIDE_SET_TIMEZONE,
        "habit_tracker": GUIDE_HABIT_TRACKER,
        "daily_digest": GUIDE_DAILY_DIGEST,
    }
    guide_text = guides.get(callback_data.guide_topic, "Извините, этот гайд не найден.")

    if callback_data.guide_topic:
        await user_repo.mark_guide_as_viewed(callback.from_user.id, callback_data.guide_topic)
        await check_and_grant_achievements(callback.bot, callback.from_user.id)

    await callback.message.edit_text(guide_text, reply_markup=get_back_to_guides_keyboard())
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


class AnyState:
    pass


@router.message(Command(commands=["cancel", "start"]), StateFilter(AnyState))
async def cancel_handler(message: types.Message, state: FSMContext, bot: Bot):
    """
    Универсальный хендлер для отмены любого состояния FSM.
    Срабатывает на /cancel или /start в любом состоянии.
    """
    current_state = await state.get_state()
    if current_state is None:
        # Если состояния нет, просто покажем главное меню как обычно
        await show_main_menu(message, state, bot)
        return

    logger.info(f"Cancelling state {current_state} for {message.from_user.id}")
    await state.clear()
    await message.answer(
        "Действие отменено. Вы возвращены в главное меню.",
        reply_markup=types.ReplyKeyboardRemove() # Убирает обычную клавиатуру, если она была
    )
    await show_main_menu(message, state, bot)