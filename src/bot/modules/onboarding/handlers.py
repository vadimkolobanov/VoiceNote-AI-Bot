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


@router.callback_query(OnboardingAction.filter(F.action == "skip"))
async def skip_onboarding_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обрабатывает пропуск обучения."""
    logger.info(f"User {callback.from_user.id} skipped onboarding.")
    await callback.answer("Хорошо, вы всегда можете найти подсказки в разделе '❓ Помощь'.")
    await _mark_onboarding_complete(callback.from_user.id, state, bot, callback.message)


async def start_onboarding(message: types.Message, state: FSMContext):
    """Начинает процесс обучения для нового пользователя."""
    logger.info(f"Starting onboarding for user {message.from_user.id}")
    await state.set_state(OnboardingStates.step_1_welcome)
    text = (
        f"👋 Привет, {hbold(message.from_user.first_name)}! Я — {hbold('VoiceNote AI')}.\n\n"
        f"Давайте я быстро покажу, как всё работает. Это займет не больше минуты!"
    )
    await message.answer(text, reply_markup=get_welcome_keyboard())


@router.callback_query(OnboardingStates.step_1_welcome, OnboardingAction.filter(F.action == "next_step"))
async def onboarding_step_2_handler(callback: types.CallbackQuery, state: FSMContext):
    """Шаг 2: Создание заметки."""
    await state.set_state(OnboardingStates.step_2_create_note)
    text = (
        f"1️⃣ {hbold('Главная функция')} (Шаг 1/5)\n\n"
        f"Просто отправьте мне {hbold('текст')} или {hbold('голосовое сообщение')}, и я превращу его в умную заметку. "
        f"Если в тексте будет дата (например, {hitalic('«позвонить маме завтра в 10»')}), я автоматически поставлю напоминание.\n\n"
        f"👉 {hbold('Попробуйте!')} Отправьте мне любую мысль. Заметка не сохранится, это лишь демонстрация."
    )
    await callback.message.edit_text(text, reply_markup=get_next_step_keyboard("➡️ Пропустить этот шаг"))
    await callback.answer()


@router.message(OnboardingStates.step_2_create_note, F.text)
@router.callback_query(OnboardingStates.step_2_create_note, OnboardingAction.filter(F.action == "next_step"))
async def onboarding_step_3_handler(event: types.Message | types.CallbackQuery, state: FSMContext, bot: Bot):
    """Шаг 3: Демонстрация результата и переход к настройке часового пояса."""
    message = event if isinstance(event, types.Message) else event.message

    feedback_text = ""
    if isinstance(event, types.Message) and event.text:
        status_msg = await message.answer("🧠 Анализирую ваше сообщение...")

        current_time_iso = datetime.now(pytz.utc).isoformat()
        llm_result = await llm.extract_reminder_details(event.text, current_time_iso)

        if "error" in llm_result:
            feedback_text = f"✅ {hbold('Отлично!')}\n\n"
        else:
            summary = llm_result.get("summary_text", "Ваша заметка")
            corrected = llm_result.get("corrected_text", event.text)
            time_components = llm_result.get("time_components")

            reminder_part = ""
            if time_components and time_components.get("original_mention"):
                reminder_part = f"\n{hbold('🤖 Напоминание:')} будет установлено на {hitalic(time_components['original_mention'])}!"

            feedback_text = (
                f"✅ {hbold('Готово! Вот как бы я сохранил вашу заметку:')}\n\n"
                f"<b>{summary}</b>\n"
                f"<i>{corrected}</i>{reminder_part}\n\n"
            )
        await status_msg.delete()
    else:
        feedback_text = f"✅ {hbold('Отлично!')}\n\n"

    await state.set_state(OnboardingStates.step_3_timezone)
    text = (
        f"{feedback_text}"
        f"2️⃣ {hbold('Часовой пояс')} (Шаг 2/5)\n\n"
        f"Чтобы напоминания приходили вовремя, "
        f"мне нужно знать ваш {hbold('часовой пояс')}. Это самая важная настройка!\n\n"
        f"Пожалуйста, выберите ваш город из списка:"
    )

    if isinstance(event, types.CallbackQuery):
        await message.edit_text(text, reply_markup=get_timezone_keyboard())
        await event.answer()
    else:
        await message.answer(text, reply_markup=get_timezone_keyboard())


@router.callback_query(OnboardingStates.step_3_timezone, OnboardingAction.filter(F.action == "set_tz"))
async def onboarding_step_4_handler(callback: types.CallbackQuery, callback_data: OnboardingAction, state: FSMContext):
    """Шаг 4: Списки покупок и общие заметки."""
    await user_repo.set_user_timezone(callback.from_user.id, callback_data.tz_name)
    await state.set_state(OnboardingStates.step_4_advanced_notes)

    text = (
        f"🕒 Часовой пояс {hbold(callback_data.tz_name)} установлен!\n\n"
        f"3️⃣ {hbold('Списки покупок')} (Шаг 3/5)\n\n"
        f"🛒 Я умею создавать удобные списки покупок. Просто отправьте мне сообщение, начинающееся со слова {hbold('«купить»')}.\n"
        f"{hitalic('Пример: «Купить молоко, хлеб и 2 банана»')}\n\n"
        f"🤝 Любой заметкой или списком можно {hbold('поделиться')} с другим человеком. Для этого под заметкой есть специальная кнопка."
    )
    await callback.message.edit_text(text, reply_markup=get_next_step_keyboard())
    await callback.answer("Часовой пояс установлен!")


@router.callback_query(OnboardingStates.step_4_advanced_notes, OnboardingAction.filter(F.action == "next_step"))
async def onboarding_step_5_handler(callback: types.CallbackQuery, state: FSMContext):
    """Шаг 5: Дни рождения и повторяющиеся задачи."""
    await state.set_state(OnboardingStates.step_5_birthdays)
    text = (
        f"4️⃣ {hbold('Повторяющиеся задачи и даты')} (Шаг 4/5)\n\n"
        f"🔁 {hbold('Задачи')} \n"
        f"Создавайте регулярные напоминания, просто написав, как часто их повторять.\n"
        f"{hitalic('Пример: «Пить витамины каждый день в 9 утра»')}\n\n"
        f"🎂 {hbold('Дни рождения')}\n"
        f"Я могу напоминать о днях рождения каждый год. Добавить их можно в меню `👤 Профиль`."
    )
    await callback.message.edit_text(text, reply_markup=get_next_step_keyboard("Отлично, почти закончили!"))
    await callback.answer()


@router.callback_query(OnboardingStates.step_5_birthdays, OnboardingAction.filter(F.action == "next_step"))
async def onboarding_step_6_handler(callback: types.CallbackQuery, state: FSMContext):
    """Шаг 6: VIP-функции."""
    await state.set_state(OnboardingStates.step_6_vip)
    text = (
        f"5️⃣ {hbold('Для максимальной продуктивности (VIP)')} (Шаг 5/5)\n\n"
        f"В VIP-режиме вам также доступны:\n\n"
        f"☀️ {hbold('Утренние сводки')}\n"
        f"Каждое утро я могу присылать вам план на день: задачи, дни рождения и погода.\n\n"
        f"🔔 {hbold('Предварительные напоминания')}\n"
        f"Я напомню о важном событии не только в срок, но и заранее (например, за час).\n\n"
        f"Хотите попробовать {hbold('бесплатный VIP-доступ')} прямо сейчас?"
    )
    await callback.message.edit_text(text, reply_markup=get_vip_choice_keyboard())
    await callback.answer()


@router.callback_query(OnboardingStates.step_6_vip, OnboardingAction.filter(F.action == "get_vip"))
async def onboarding_get_vip_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выдачу VIP и переходит к финалу."""
    await user_repo.set_user_vip_status(callback.from_user.id, True)
    await state.set_state(OnboardingStates.step_7_final)
    text = (
        f"🎉 {hbold('Поздравляем! Вам присвоен VIP-статус!')}\n\n"
        f"Теперь вам доступны все функции. Вы можете настроить их в меню '⚙️ Настройки'."
    )
    await callback.message.edit_text(text, reply_markup=get_final_keyboard())
    await callback.answer("VIP-статус активирован!", show_alert=True)


@router.callback_query(OnboardingStates.step_6_vip, OnboardingAction.filter(F.action == "next_step"))
async def onboarding_final_step_handler(callback: types.CallbackQuery, state: FSMContext):
    """Шаг 7: Завершение без VIP."""
    await state.set_state(OnboardingStates.step_7_final)
    text = "Хорошо! Вы всегда сможете активировать VIP позже."
    await callback.message.edit_text(text, reply_markup=get_final_keyboard())
    await callback.answer()


@router.callback_query(OnboardingStates.step_7_final, OnboardingAction.filter(F.action == "finish"))
async def finish_onboarding_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Завершает обучение."""
    logger.info(f"User {callback.from_user.id} finished onboarding.")
    await _mark_onboarding_complete(callback.from_user.id, state, bot, callback.message)
    await callback.answer("Добро пожаловать!")