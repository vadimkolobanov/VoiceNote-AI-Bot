# src/bot/modules/habits/handlers.py
import logging
from datetime import datetime
import pytz

from aiogram import F, Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.markdown import hbold, hitalic

from ....database import habit_repo, user_repo
from ....services import llm
from ....bot.common_utils.states import HabitStates
from ....bot.common_utils.callbacks import HabitAction, HabitTrack
from .keyboards import get_habits_menu_keyboard, get_habit_confirmation_keyboard, get_manage_habits_keyboard

logger = logging.getLogger(__name__)
router = Router()


async def show_habits_menu(event: types.Message | types.CallbackQuery):
    """Отображает главное меню привычек."""
    message = event if isinstance(event, types.Message) else event.message
    user_id = event.from_user.id

    habits = await habit_repo.get_user_habits(user_id)

    if not habits:
        text = (
            f"💪 {hbold('Трекер привычек')}\n\n"
            "Здесь вы можете отслеживать свои ежедневные ритуалы и формировать полезные привычки.\n\n"
            "У вас пока нет ни одной. Давайте создадим?"
        )
    else:
        habits_list = []
        for h in habits:
            habits_list.append(f"• {hitalic(h['name'])}")
        habits_str = "\n".join(habits_list)
        text = (
            f"💪 {hbold('Ваши привычки')}\n\n"
            f"{habits_str}\n\n"
            "Я буду ежедневно напоминать вам о них и вести статистику."
        )

    keyboard = get_habits_menu_keyboard(has_habits=bool(habits))

    if isinstance(event, types.CallbackQuery):
        try:
            await message.edit_text(text, reply_markup=keyboard)
        except:
            await message.answer(text, reply_markup=keyboard)
        await event.answer()
    else:
        await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "habits_menu")
async def habits_menu_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_habits_menu(callback)


@router.callback_query(F.data == "add_new_habits")
async def add_new_habits_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(HabitStates.awaiting_description)
    text = (
        "📝 Расскажите мне в одном сообщении, какие привычки вы хотите сформировать.\n\n"
        f"{hitalic('Пример: «Хочу каждый день утром делать зарядку, по вечерам мыть посуду, а по выходным читать книгу»')}"
    )
    await callback.message.edit_text(text)
    await callback.answer()


@router.message(HabitStates.awaiting_description, F.text)
async def process_habits_description(message: types.Message, state: FSMContext):
    status_msg = await message.answer("🧠 Анализирую ваш текст... Пожалуйста, подождите.")

    user_profile = await user_repo.get_user_profile(message.from_user.id)
    user_tz = pytz.timezone(user_profile.get('timezone', 'UTC'))
    current_time_iso = datetime.now(user_tz).isoformat()

    llm_result = await llm.extract_habits_from_text(message.text, current_time_iso)

    if "error" in llm_result or not llm_result.get("habits"):
        await status_msg.edit_text(
            "❌ К сожалению, не удалось распознать привычки в вашем сообщении. Попробуйте перефразировать или быть конкретнее.")
        return

    habits_to_add = llm_result["habits"]
    await state.update_data(habits_to_add=habits_to_add)

    confirmation_parts = [
        "Отлично, я вас понял! Вот что у меня получилось. Всё верно?\n",
        hbold("Ваши будущие привычки:"),
    ]

    icon_map = {"зарядк": "🤸", "спорт": "🏃", "читать": "📖", "мыть": "🍽️", "гулять": "🐕", "вода": "💧", "медитир": "🧘"}

    for habit in habits_to_add:
        icon = "💡"
        for key, val in icon_map.items():
            if key in habit['name'].lower():
                icon = val
                break

        time_str = f"в {habit.get('reminder_time')}" if habit.get('reminder_time') else "(время не указано)"
        from ....services.tz_utils import format_rrule_for_user
        freq_str = format_rrule_for_user(habit['frequency_rule'])

        confirmation_parts.append(f"\n{icon} {hbold(habit['name'])}\n  - {hitalic(f'Когда: {freq_str}, {time_str}')}")

    await status_msg.edit_text(
        "\n".join(confirmation_parts),
        reply_markup=get_habit_confirmation_keyboard()
    )
    await state.set_state(HabitStates.awaiting_confirmation)


@router.callback_query(HabitStates.awaiting_confirmation, HabitAction.filter(F.action == "confirm_add"))
async def confirm_add_habits(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    from ....services.scheduler import setup_habit_reminders

    data = await state.get_data()
    habits_to_add = data.get("habits_to_add", [])

    if not habits_to_add:
        await callback.answer("Ошибка: не найдены привычки для добавления.", show_alert=True)
        return

    await callback.message.edit_text("✅ Сохраняю и настраиваю напоминания...")

    added_habits = await habit_repo.add_habits_bulk(callback.from_user.id, habits_to_add)

    if added_habits:
        await setup_habit_reminders(bot)

    await state.clear()
    await callback.answer("Привычки успешно добавлены!", show_alert=True)
    await show_habits_menu(callback)


@router.callback_query(HabitStates.awaiting_confirmation, HabitAction.filter(F.action == "cancel"))
async def cancel_add_habits(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Действие отменено.")
    await show_habits_menu(callback)


@router.callback_query(HabitTrack.filter())
async def track_habit_handler(callback: types.CallbackQuery, callback_data: HabitTrack):
    habit_id = callback_data.habit_id
    status = callback_data.status

    user_profile = await user_repo.get_user_profile(callback.from_user.id)
    user_tz = pytz.timezone(user_profile.get('timezone', 'UTC'))
    track_date = datetime.now(user_tz).date().isoformat()

    success = await habit_repo.track_habit(habit_id, callback.from_user.id, track_date, status)

    if success:
        status_text = "Отмечено как выполненное!" if status == "completed" else "Пропущено на сегодня."
        await callback.answer(status_text)
        try:
            await callback.message.edit_text(f"{callback.message.text}\n\n{hbold(status_text)}", reply_markup=None)
        except Exception:
            pass
    else:
        await callback.answer("Произошла ошибка.", show_alert=True)


@router.callback_query(F.data == "manage_habits")
async def manage_habits_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    habits = await habit_repo.get_user_habits(user_id)

    if not habits:
        await callback.answer("У вас нет привычек для управления.", show_alert=True)
        await show_habits_menu(callback)
        return

    text = "Выберите привычку, которую хотите удалить:"
    keyboard = get_manage_habits_keyboard(habits)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(HabitAction.filter(F.action == "delete"))
async def delete_habit_handler(callback: types.CallbackQuery, callback_data: HabitAction, bot: Bot):
    from ....services.scheduler import setup_habit_reminders

    habit_id = callback_data.habit_id
    user_id = callback.from_user.id

    success = await habit_repo.delete_habit(habit_id, user_id)

    if success:
        await callback.answer("Привычка успешно удалена.", show_alert=True)
        # Перезапускаем планировщик, чтобы удалить напоминания для этой привычки
        await setup_habit_reminders(bot)
        # Обновляем меню управления, передавая callback, чтобы message.edit_text сработал
        await manage_habits_handler(callback)
    else:
        await callback.answer("Не удалось удалить привычку.", show_alert=True)