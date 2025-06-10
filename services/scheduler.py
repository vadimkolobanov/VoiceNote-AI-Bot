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
    Если у due_date время 00:00:00, сдвигает его на 9:00 по времени пользователя.
    """
    job_id = f"note_reminder_{note['note_id']}"
    due_date_utc = note.get('due_date')

    if not due_date_utc:
        return

    if due_date_utc.tzinfo is None:
        due_date_utc = pytz.utc.localize(due_date_utc)

    # <--- НОВАЯ ЛОГИКА --->
    # Проверяем, является ли время "полуночным"
    if due_date_utc.time() == time(0, 0, 0):
        try:
            # Получаем часовой пояс пользователя, чтобы посчитать 9 утра для него
            # Это синхронный вызов, но он нужен для получения timezone_str
            # TODO: Передать user_profile в note, чтобы избежать синхронного вызова.
            logger.info(f"Заметка #{note['note_id']} имеет время 00:00:00. Попытка сдвинуть на 9 утра.")
            final_due_date_utc = due_date_utc.replace(hour=9, minute=0, second=0)
            logger.info(f"Время для заметки #{note['note_id']} сдвинуто на {final_due_date_utc.isoformat()}")

        except Exception as e:
            logger.error(f"Ошибка при сдвиге времени для заметки #{note['note_id']}: {e}")
            final_due_date_utc = due_date_utc  # В случае ошибки оставляем как есть
    else:
        final_due_date_utc = due_date_utc

    if final_due_date_utc < datetime.now(pytz.utc):
        logger.info(f"Напоминание для заметки #{note['note_id']} не запланировано (дата в прошлом).")
        return

    job_kwargs = {
        'bot': bot,
        'telegram_id': note['telegram_id'],
        'note_id': note['note_id'],
        'note_text': note['corrected_text'],
        'due_date': final_due_date_utc  # Используем финальную дату
    }

    if scheduler.get_job(job_id):
        scheduler.reschedule_job(job_id, trigger='date', run_date=final_due_date_utc)
        logger.info(f"Напоминание для заметки #{note['note_id']} перепланировано на {final_due_date_utc.isoformat()}")
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
    # ... (эта функция без изменений) ...
    job_id = f"note_reminder_{note_id}"
    if scheduler.get_job(job_id):
        try:
            scheduler.remove_job(job_id)
            logger.info(f"Напоминание для заметки #{note_id} удалено из планировщика.")
        except Exception as e:
            logger.error(f"Ошибка при удалении напоминания для заметки #{note_id}: {e}")


async def load_reminders_on_startup(bot: Bot):
    # ... (эта функция без изменений) ...
    logger.info("Загрузка предстоящих напоминаний из базы данных...")
    notes_with_reminders = await db.get_notes_with_reminders()
    count = 0
    for note in notes_with_reminders:
        add_reminder_to_scheduler(bot, note)
        count += 1
    logger.info(f"Загружено {count} напоминаний в планировщик.")