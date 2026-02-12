# src/bot/modules/onboarding/handlers.py
import logging
from datetime import datetime
import pytz

from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hitalic

from ....database import user_repo, note_repo
from ...common_utils.callbacks import OnboardingAction
from ...common_utils.states import OnboardingStates
from ....services import llm
from .keyboards import (
    get_welcome_keyboard,
    get_next_step_keyboard,
    get_timezone_keyboard,
    get_vip_choice_keyboard,
    get_final_keyboard,
)

logger = logging.getLogger(__name__)
router = Router()


async def _show_main_menu(message: types.Message, state: FSMContext):
    """Чистое отображение главного меню после обучения."""
    from ..common.handlers import get_main_menu_keyboard

    await state.clear()

    # --- ИЗМЕНЕНИЕ: Используем get_or_create_user для 100% гарантии наличия профиля ---
    user_profile = await user_repo.get_or_create_user(message.from_user)
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    # Добавляем проверку на случай, если даже создание пользователя по какой-то причине не удалось
    if not user_profile:
        logger.error(
            f"Не удалось получить или создать профиль для пользователя {message.from_user.id} в _show_main_menu")
        await message.answer(
            "Произошла ошибка при загрузке вашего профиля. Пожалуйста, попробуйте нажать /start еще раз.")
        return

    is_vip = user_profile.get('is_vip', False)
    active_shopping_list = await note_repo.get_active_shopping_list(message.from_user.id)
    has_active_list = active_shopping_list is not None

    text = (
        f"🏠 {hbold('Главное меню')}\n\n"
        f"Отлично, теперь вы готовы к работе! Отправьте мне любую мысль, голосовое или текстовое сообщение, "
        f"и я превращу его в умную заметку."
    )
    keyboard = get_main_menu_keyboard(is_vip=is_vip, has_active_list=has_active_list)

    try:
        await message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await message.answer(text, reply_markup=keyboard)


async def _mark_onboarding_complete(user_id: int, state: FSMContext, bot: Bot, message: types.Message):
    """Отмечает обучение как пройденное и показывает главное меню."""
    await user_repo.set_onboarding_status(user_id, True)
    await _show_main_menu(message, state)


# Пропуск онбординга удален - создание первой заметки теперь обязательное


async def start_onboarding(message: types.Message, state: FSMContext):
    """Начинает процесс обучения для нового пользователя."""
    logger.info(f"Starting onboarding for user {message.from_user.id}")
    await state.set_state(OnboardingStates.step_1_welcome)
    text = (
        f"👋 Привет, {hbold(message.from_user.first_name)}! Я — {hbold('VoiceNote AI')}.\n\n"
        f"Я превращаю ваши мысли в умные заметки с напоминаниями.\n\n"
        f"Давайте создадим вашу первую заметку прямо сейчас! Это займет 30 секунд."
    )
    await message.answer(text, reply_markup=get_welcome_keyboard())


@router.callback_query(OnboardingStates.step_1_welcome, OnboardingAction.filter(F.action == "next_step"))
async def onboarding_step_2_handler(callback: types.CallbackQuery, state: FSMContext):
    """Шаг 2: Создание заметки (ОБЯЗАТЕЛЬНЫЙ)."""
    await state.set_state(OnboardingStates.step_2_create_note)
    text = (
        f"1️⃣ {hbold('Создайте вашу первую заметку!')} (Шаг 1/3)\n\n"
        f"Просто отправьте мне {hbold('текст')} или {hbold('голосовое сообщение')}, и я превращу его в умную заметку.\n\n"
        f"💡 {hbold('Примеры:')}\n"
        f"• {hitalic('«Позвонить маме завтра в 10»')}\n"
        f"• {hitalic('«Купить молоко и хлеб»')}\n"
        f"• {hitalic('«Встреча с командой в пятницу в 15:00»')}\n\n"
        f"👉 {hbold('Отправьте мне любую мысль прямо сейчас!')}"
    )
    await callback.message.edit_text(text, reply_markup=None)
    await callback.answer()


@router.message(OnboardingStates.step_2_create_note, F.text)
@router.message(OnboardingStates.step_2_create_note, F.voice)
async def onboarding_step_2_process_note(message: types.Message, state: FSMContext, bot: Bot):
    """Обрабатывает создание первой заметки в онбординге - ОБЯЗАТЕЛЬНЫЙ шаг."""
    from ..notes.handlers.creation import _background_note_processor
    
    # Проверяем, что это действительно заметка (не мусор)
    text_to_process = None
    voice_file_id = None
    
    if message.voice:
        voice_file_id = message.voice.file_id
        status_msg = await message.answer("✔️ Принято! Распознаю речь...")
    elif message.text:
        text_to_process = message.text.strip()
        if len(text_to_process) < 10 or len(text_to_process.split()) < 2:
            await message.answer("❌ Пожалуйста, отправьте более подробное сообщение. Например: «Позвонить маме завтра в 10»")
            return
        status_msg = await message.answer("✔️ Принято! Обрабатываю...")
    else:
        return
    
    # Обрабатываем заметку (await — ждём полного завершения, НЕ фоновая задача)
    try:
        await _background_note_processor(
            bot=bot,
            user_id=message.from_user.id,
            status_message_id=status_msg.message_id,
            chat_id=message.chat.id,
            text_to_process=text_to_process,
            voice_file_id=voice_file_id,
            original_message_date=message.date,
            silent_achievements=True
        )
    except Exception as e:
        logger.error(f"Ошибка создания первой заметки в онбординге для user {message.from_user.id}: {e}", exc_info=True)
        await message.answer(
            "😔 Не удалось создать заметку. Попробуйте ещё раз — отправьте текст или голосовое сообщение."
        )
        # Остаёмся на шаге step_2, чтобы пользователь мог повторить попытку
        return

    # Заметка успешно создана — переходим к выбору часового пояса
    await state.set_state(OnboardingStates.step_3_timezone)

    text = (
        f"✅ {hbold('Отлично! Ваша первая заметка создана!')}\n\n"
        f"2️⃣ {hbold('Часовой пояс')} (Шаг 2/3)\n\n"
        f"Чтобы напоминания приходили вовремя, "
        f"мне нужно знать ваш {hbold('часовой пояс')}. Это самая важная настройка!\n\n"
        f"Пожалуйста, выберите ваш город из списка:"
    )
    await message.answer(text, reply_markup=get_timezone_keyboard())


@router.callback_query(OnboardingStates.step_3_timezone, OnboardingAction.filter(F.action == "set_tz"))
async def onboarding_step_3_final_handler(callback: types.CallbackQuery, callback_data: OnboardingAction, state: FSMContext, bot: Bot):
    """Шаг 3: Завершение онбординга."""
    await user_repo.set_user_timezone(callback.from_user.id, callback_data.tz_name)
    await state.set_state(OnboardingStates.step_4_final)

    text = (
        f"🕒 Часовой пояс {hbold(callback_data.tz_name)} установлен!\n\n"
        f"3️⃣ {hbold('Готово!')} (Шаг 3/3)\n\n"
        f"🎉 {hbold('Поздравляю! Вы готовы к работе!')}\n\n"
        f"Теперь просто отправляйте мне любые мысли, и я превращу их в умные заметки.\n\n"
        f"💡 {hbold('Полезные функции:')}\n"
        f"• Списки покупок: напишите «купить молоко, хлеб»\n"
        f"• Повторяющиеся задачи: «пить витамины каждый день в 9»\n"
        f"• Дни рождения: добавьте в меню «👤 Профиль»\n\n"
        f"🚀 {hbold('Совет:')} После создания 3-5 заметок я предложу вам VIP-функции!"
    )
    await callback.message.edit_text(text, reply_markup=get_final_keyboard())
    await callback.answer("Часовой пояс установлен!")


@router.callback_query(OnboardingStates.step_4_final, OnboardingAction.filter(F.action == "finish"))
async def finish_onboarding_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Завершает обучение."""
    logger.info(f"User {callback.from_user.id} finished onboarding.")
    await _mark_onboarding_complete(callback.from_user.id, state, bot, callback.message)
    await callback.answer("Добро пожаловать! Начните создавать заметки прямо сейчас!")