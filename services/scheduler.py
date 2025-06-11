# services/scheduler.py
import logging
from datetime import datetime, time
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
import pytz

import database_setup as db
from inline_keyboards import get_reminder_notification_keyboard
from services.tz_utils import format_datetime_for_user

logger = logging.getLogger(__name__)

# --- Scheduler Setup ---
jobstores = {
    'default': MemoryJobStore()
}
executors = {
    'default': AsyncIOExecutor()
}
scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    executors=executors,
    timezone=pytz.utc
)


async def send_reminder_notification(bot: Bot, telegram_id: int, note_id: int, note_text: str, due_date: datetime):
    """
    Асинхронная функция, которая будет вызываться планировщиком для отправки напоминания.
    """
    logger.info(f"Отправка напоминания по заметке #{note_id} пользователю {telegram_id}")
    try:
        user_profile = await db.get_user_profile(telegram_id)
        # Проверяем, не была ли заметка выполнена или удалена перед отправкой
        note = await db.get_note_by_id(note_id, telegram_id)
        if not note or note.get('is_completed') or note.get('is_archived'):
            logger.info(f"Напоминание для заметки #{note_id} отменено: заметка выполнена, архивирована или удалена.")
            return

        user_timezone = user_profile.get('timezone', 'UTC') if user_profile else 'UTC'
        formatted_due_date = format_datetime_for_user(due_date, user_timezone)

        from aiogram.utils.markdown import hbold, hcode, hitalic
        text = (
            f"🔔 {hbold('Напоминание')}\n\n"
            f"Заметка: #{hcode(str(note_id))}\n"
            f"Срок: {hitalic(formatted_due_date)}\n\n"
            f"📝 {hbold('Текст заметки:')}\n"
            f"{hcode(note_text)}"
        )
        keyboard = get_reminder_notification_keyboard(note_id)
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Не удалось отправить напоминание по заметке #{note_id} пользователю {telegram_id}: {e}",
                     exc_info=True)


def add_reminder_to_scheduler(bot: Bot, note: dict):
    """
    Добавляет задачу-напоминание в планировщик.
    Если у due_date время 00:00:00, сдвигает его на время из настроек пользователя.
    """
    job_id = f"note_reminder_{note['note_id']}"
    due_date_utc = note.get('due_date')

    if not due_date_utc:
        return

    # Убеждаемся, что дата "aware"
    if due_date_utc.tzinfo is None:
        due_date_utc = pytz.utc.localize(due_date_utc)

    # --- НОВАЯ ЛОГИКА с учетом настроек пользователя ---
    if due_date_utc.time() == time(0, 0, 0):
        user_reminder_time = note.get('default_reminder_time', time(9, 0))  # время из БД или 9:00 по умолчанию
        user_timezone_str = note.get('timezone', 'UTC')  # часовой пояс из БД или UTC

        try:
            user_tz = pytz.timezone(user_timezone_str)
        except pytz.UnknownTimeZoneError:
            logger.warning(
                f"Неизвестный часовой пояс '{user_timezone_str}' у пользователя {note['telegram_id']}. Используется UTC.")
            user_tz = pytz.utc

        # Создаем "наивную" дату с нужным временем в часовом поясе пользователя
        local_due_date = datetime.combine(due_date_utc.date(), user_reminder_time)
        # Делаем ее "aware" (присваиваем ей часовой пояс пользователя)
        aware_local_due_date = user_tz.localize(local_due_date)
        # Конвертируем в UTC для планировщика
        final_due_date_utc = aware_local_due_date.astimezone(pytz.utc)

        logger.info(
            f"Для заметки #{note['note_id']} время не было указано. "
            f"Устанавливаем напоминание на {user_reminder_time.strftime('%H:%M')} по времени пользователя ({user_timezone_str}). "
            f"Итоговое время в UTC: {final_due_date_utc.isoformat()}"
        )
    else:
        # Если время было указано в заметке, используем его как есть
        final_due_date_utc = due_date_utc

    if final_due_date_utc < datetime.now(pytz.utc):
        logger.info(f"Напоминание для заметки #{note['note_id']} не запланировано (дата в прошлом).")
        return

    job_kwargs = {
        'bot': bot,
        'telegram_id': note['telegram_id'],
        'note_id': note['note_id'],
        'note_text': note['corrected_text'],
        'due_date': final_due_date_utc
    }

    if scheduler.get_job(job_id):
        try:
            scheduler.reschedule_job(job_id, trigger='date', run_date=final_due_date_utc)
            logger.info(
                f"Напоминание для заметки #{note['note_id']} перепланировано на {final_due_date_utc.isoformat()}")
        except Exception as e:
            logger.error(f"Ошибка при перепланировании задачи #{job_id}: {e}")
    else:
        scheduler.add_job(
            send_reminder_notification,
            trigger='date',
            run_date=final_due_date_utc,
            id=job_id,
            kwargs=job_kwargs,
            replace_existing=True
        )
        logger.info(f"Напоминание для заметки #{note['note_id']} запланировано на {final_due_date_utc.isoformat()}")


def remove_reminder_from_scheduler(note_id: int):
    """Удаляет задачу-напоминание из планировщика."""
    job_id = f"note_reminder_{note_id}"
    if scheduler.get_job(job_id):
        try:
            scheduler.remove_job(job_id)
            logger.info(f"Напоминание для заметки #{note_id} удалено из планировщика.")
        except Exception as e:
            logger.error(f"Ошибка при удалении напоминания для заметки #{note_id}: {e}")


async def load_reminders_on_startup(bot: Bot):
    """Загружает все актуальные напоминания из БД при старте бота."""
    logger.info("Загрузка предстоящих напоминаний из базы данных...")
    notes_with_reminders = await db.get_notes_with_reminders()
    count = 0
    for note in notes_with_reminders:
        add_reminder_to_scheduler(bot, note)
        count += 1
    logger.info(f"Загружено {count} напоминаний в планировщик.")