# src/bot/modules/notes/handlers/shopping_list.py
import logging
import asyncio
from datetime import datetime, time, timedelta
import pytz

from aiogram import F, Router, types, Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.utils.markdown import hbold

from .....database import note_repo, user_repo
from .....services import scheduler
from ....common_utils.callbacks import ShoppingListAction, ShoppingListReminder, NoteAction
from ..keyboards import get_shopping_list_keyboard, get_shopping_reminder_options_keyboard

logger = logging.getLogger(__name__)
router = Router()


def get_shopping_list_text_and_keyboard(note: dict, participants_map: dict):
    """Вспомогательная функция для генерации текста и клавиатуры списка покупок."""
    items = note.get("llm_analysis_json", {}).get("items", [])
    is_archived = note.get('is_archived', False)
    note_id = note['note_id']

    checked_count = sum(1 for item in items if item.get('checked'))
    total_count = len(items)

    owner_id = note.get('owner_id')
    owner_name = participants_map.get(owner_id, "Неизвестно")
    header = f"🛒 {hbold('Список покупок')} (владелец: {owner_name})"

    text = f"{header}\n\nВыбрано: {checked_count} из {total_count}"

    keyboard = get_shopping_list_keyboard(note_id, items, is_archived, participants_map)

    return text, keyboard


async def render_shopping_list(event: types.Message | types.CallbackQuery, note_id: int, user_id: int):
    """Отображает или обновляет сообщение со списком покупок."""
    note = await note_repo.get_note_by_id(note_id, user_id)
    if not note:
        error_text = "Не удалось найти этот список покупок."
        if isinstance(event, types.CallbackQuery):
            await event.answer(error_text, show_alert=True)
            try:
                await event.message.delete()
            except Exception:
                pass
        else:
            await event.answer(error_text)
        return

    participants = await note_repo.get_shared_note_participants(note_id)
    participants_map = {p['telegram_id']: p.get('first_name', str(p['telegram_id'])) for p in participants}

    text, keyboard = get_shopping_list_text_and_keyboard(note, participants_map)

    message = event.message if isinstance(event, types.CallbackQuery) else event
    try:
        if isinstance(event, types.CallbackQuery):
            await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            new_message = await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            await note_repo.store_shared_message_id(note_id, user_id, new_message.message_id)
    except Exception:
        # Если не удалось отредактировать, отправляем новое сообщение
        new_message = await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await note_repo.store_shared_message_id(note_id, user_id, new_message.message_id)


async def _background_sync_for_others(bot: Bot, note_id: int, initiator_id: int):
    """Фоновая задача для синхронизации списка у всех, КРОМЕ инициатора."""
    await asyncio.sleep(0.5) # Небольшая задержка, чтобы дать БД время обновиться

    note = await note_repo.get_note_by_id(note_id, 0) # 0 для админского доступа
    if not note:
        return

    participants = await note_repo.get_shared_note_participants(note_id)
    participants_map = {p['telegram_id']: p.get('first_name', str(p['telegram_id'])) for p in participants}
    stored_messages = await note_repo.get_shared_message_ids(note_id)
    message_map = {msg['user_id']: msg['message_id'] for msg in stored_messages}

    text, keyboard = get_shopping_list_text_and_keyboard(note, participants_map)

    for user in participants:
        user_id = user['telegram_id']
        if user_id == initiator_id:
            continue # Пропускаем того, кто нажал кнопку

        message_id = message_map.get(user_id)
        if message_id:
            try:
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except TelegramForbiddenError:
                logger.warning(f"Не удалось обновить список для {user_id} (заблокировал бота). Удаляем запись.")
                await note_repo.delete_shared_message_id(note_id, user_id)
            except TelegramBadRequest as e:
                if "message to edit not found" in str(e).lower():
                    logger.warning(f"Сообщение для {user_id} не найдено. Удаляем запись из БД.")
                    await note_repo.delete_shared_message_id(note_id, user_id)
                else:
                    logger.error(f"Ошибка обновления списка для {user_id}: {e}")
            except Exception as e:
                logger.error(f"Неожиданная ошибка обновления списка для {user_id}: {e}")


@router.callback_query(ShoppingListAction.filter(F.action.in_({"show", "toggle", "archive"})))
async def shopping_list_actions_handler(callback: types.CallbackQuery, callback_data: ShoppingListAction, bot: Bot):
    note_id = callback_data.note_id
    user_id = callback.from_user.id
    action = callback_data.action

    note = await note_repo.get_note_by_id(note_id, user_id)
    if not note:
        await callback.answer("Список не найден.", show_alert=True)
        return

    if action == "show":
        await render_shopping_list(callback, note_id, user_id)
        await note_repo.store_shared_message_id(note_id, user_id, callback.message.message_id)
        await callback.answer()
        return

    if action == "toggle":
        item_index = callback_data.item_index
        items = note.get("llm_analysis_json", {}).get("items", [])
        if not (0 <= item_index < len(items)):
            await callback.answer("Элемент не найден.", show_alert=True)
            return

        # Обновляем данные в БД
        items[item_index]['checked'] = not items[item_index].get('checked', False)
        note["llm_analysis_json"]["items"] = items
        await note_repo.update_note_llm_json(note_id, note["llm_analysis_json"])

        # Оптимистичное обновление: сначала для себя, потом для всех в фоне
        participants = await note_repo.get_shared_note_participants(note_id)
        participants_map = {p['telegram_id']: p.get('first_name', str(p['telegram_id'])) for p in participants}

        text, keyboard = get_shopping_list_text_and_keyboard(note, participants_map)

        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer("Отмечено!")
        except Exception as e:
            logger.warning(f"Не удалось обновить сообщение для инициатора {user_id}: {e}")
            await callback.answer("Отмечено!", show_alert=True) # Все равно даем обратную связь

        # Запускаем фоновую синхронизацию для остальных
        asyncio.create_task(_background_sync_for_others(bot, note_id, user_id))
        return

    if action == "archive":
        await note_repo.set_note_archived_status(note_id, True)
        await callback.answer("Список завершен и отправлен в архив.", show_alert=True)
        await callback.message.delete()
        return


@router.callback_query(ShoppingListReminder.filter(F.action == "show_options"))
async def show_reminder_options_handler(callback: types.CallbackQuery, callback_data: ShoppingListReminder):
    keyboard = get_shopping_reminder_options_keyboard(callback_data.note_id)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(ShoppingListReminder.filter(F.action == "set"))
async def set_shopping_list_reminder_handler(callback: types.CallbackQuery, callback_data: ShoppingListReminder,
                                             bot: Bot):
    note_id = callback_data.note_id
    value = callback_data.value
    user_id = callback.from_user.id

    user_profile = await user_repo.get_user_profile(user_id)
    user_tz_str = user_profile.get('timezone', 'UTC')
    try:
        user_tz = pytz.timezone(user_tz_str)
    except pytz.UnknownTimeZoneError:
        user_tz = pytz.utc

    now_user_tz = datetime.now(user_tz)
    run_date_user_tz = None

    if value == "in_1h":
        run_date_user_tz = now_user_tz + timedelta(hours=1)
    elif value == "in_3h":
        run_date_user_tz = now_user_tz + timedelta(hours=3)
    elif value == "today_18":
        run_date_user_tz = now_user_tz.replace(hour=18, minute=0, second=0, microsecond=0)
        if now_user_tz.time() >= time(18, 0):
            run_date_user_tz += timedelta(days=1)
    elif value == "today_20":
        run_date_user_tz = now_user_tz.replace(hour=20, minute=0, second=0, microsecond=0)
        if now_user_tz.time() >= time(20, 0):
            run_date_user_tz += timedelta(days=1)
    elif value == "tomorrow_09":
        run_date_user_tz = (now_user_tz + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    elif value == "saturday_12":
        days_ahead = (5 - now_user_tz.weekday() + 7) % 7
        if days_ahead == 0 and now_user_tz.time() >= time(12, 0):
            days_ahead = 7
        target_date = now_user_tz + timedelta(days=days_ahead)
        run_date_user_tz = target_date.replace(hour=12, minute=0, second=0, microsecond=0)

    if run_date_user_tz:
        run_date_utc = run_date_user_tz.astimezone(pytz.utc)

        scheduler.scheduler.add_job(
            scheduler.send_shopping_list_ping,
            trigger='date',
            run_date=run_date_utc,
            id=f"shop_list_ping_{note_id}_{user_id}",
            kwargs={'bot': bot, 'user_id': user_id, 'note_id': note_id},
            replace_existing=True
        )

        alert_text = f"Отлично, напомню вам {run_date_user_tz.strftime('%d.%m в %H:%M')}!"
        await callback.answer(alert_text, show_alert=True)

    await render_shopping_list(callback, note_id, user_id)