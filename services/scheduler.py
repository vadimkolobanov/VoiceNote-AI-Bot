# services/scheduler.py
import logging
import asyncio
from datetime import datetime, time, timedelta
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


async def send_reminder_notification(bot: Bot, telegram_id: int, note_id: int, note_text: str, due_date: datetime,
                                     is_pre_reminder: bool):
    """
    Асинхронная функция для отправки напоминания.
    Принимает флаг is_pre_reminder для формирования разного текста и клавиатуры.
    """
    logger.info(
        f"Отправка {'предварительного ' if is_pre_reminder else 'основного'}напоминания по заметке #{note_id} пользователю {telegram_id}")

    try:
        user_profile = await db.get_user_profile(telegram_id)
        note = await db.get_note_by_id(note_id, telegram_id)

        if not note or note.get('is_completed') or note.get('is_archived'):
            logger.info(f"Напоминание для заметки #{note_id} отменено: заметка неактивна.")
            remove_reminder_from_scheduler(note_id)
            return

        user_timezone = user_profile.get('timezone', 'UTC') if user_profile else 'UTC'
        actual_due_date = note.get('due_date', due_date)
        formatted_due_date = format_datetime_for_user(actual_due_date, user_timezone)

        from aiogram.utils.markdown import hbold, hcode, hitalic

        if is_pre_reminder:
            header = f"🔔 {hbold('Предварительное напоминание')}"
        else:
            header = f"‼️ {hbold('НАПОМИНАНИЕ')}"

        text = (
            f"{header}\n\n"
            f"Заметка: #{hcode(str(note_id))}\n"
            f"Срок: {hitalic(formatted_due_date)}\n\n"
            f"📝 {hbold('Текст заметки:')}\n"
            f"{hcode(note_text)}"
        )
        keyboard = get_reminder_notification_keyboard(note_id, is_pre_reminder=is_pre_reminder)
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Не удалось отправить напоминание по заметке #{note_id} пользователю {telegram_id}: {e}",
                     exc_info=True)


def add_reminder_to_scheduler(bot: Bot, note: dict):
    """
    Добавляет задачи в планировщик с учетом VIP-статуса пользователя.
    """
    note_id = note.get('note_id')
    due_date_utc = note.get('due_date')
    is_vip = note.get('is_vip', False)

    if not note_id or not due_date_utc:
        return

    remove_reminder_from_scheduler(note_id)

    if due_date_utc.tzinfo is None:
        due_date_utc = pytz.utc.localize(due_date_utc)

    is_time_ambiguous = (due_date_utc.time() == time(0, 0, 0))

    # Применяем настройки времени по умолчанию только для VIP, если время не указано явно
    if is_time_ambiguous and is_vip:
        user_reminder_time = note.get('default_reminder_time', time(9, 0))
        user_timezone_str = note.get('timezone', 'UTC')
        try:
            user_tz = pytz.timezone(user_timezone_str)
        except pytz.UnknownTimeZoneError:
            user_tz = pytz.utc

        local_due_date = datetime.combine(due_date_utc.date(), user_reminder_time)
        aware_local_due_date = user_tz.localize(local_due_date)
        final_due_date_utc = aware_local_due_date.astimezone(pytz.utc)

        asyncio.create_task(db.update_note_due_date(note_id, final_due_date_utc))

    elif is_time_ambiguous and not is_vip:
        # Для Free-пользователей напоминание не ставится, если указана только дата
        logger.info(f"Напоминание для заметки #{note_id} (Free User) не будет установлено: время не указано явно.")
        return  # Полностью выходим из функции
    else:
        # Если время указано явно, напоминание ставится для всех
        final_due_date_utc = due_date_utc

    now_utc = datetime.now(pytz.utc)

    # Планируем ОСНОВНОЕ напоминание (если дата в будущем)
    if final_due_date_utc > now_utc:
        job_id_main = f"note_reminder_{note_id}_main"
        scheduler.add_job(
            send_reminder_notification,
            trigger='date',
            run_date=final_due_date_utc,
            id=job_id_main,
            kwargs={
                'bot': bot, 'telegram_id': note['telegram_id'], 'note_id': note_id,
                'note_text': note['corrected_text'], 'due_date': final_due_date_utc,
                'is_pre_reminder': False
            },
            replace_existing=True
        )
        logger.info(f"Основное напоминание для заметки #{note_id} запланировано на {final_due_date_utc.isoformat()}")

    # Планируем ПРЕДВАРИТЕЛЬНОЕ напоминание (только для VIP)
    if is_vip:
        pre_reminder_minutes = note.get('pre_reminder_minutes', 0)
        if pre_reminder_minutes > 0:
            pre_reminder_time_utc = final_due_date_utc - timedelta(minutes=pre_reminder_minutes)
            if pre_reminder_time_utc > now_utc:
                job_id_pre = f"note_reminder_{note_id}_pre_{pre_reminder_minutes}"
                scheduler.add_job(
                    send_reminder_notification,
                    trigger='date',
                    run_date=pre_reminder_time_utc,
                    id=job_id_pre,
                    kwargs={
                        'bot': bot, 'telegram_id': note['telegram_id'], 'note_id': note_id,
                        'note_text': note['corrected_text'], 'due_date': final_due_date_utc,
                        'is_pre_reminder': True
                    },
                    replace_existing=True
                )
                logger.info(
                    f"Пред-напоминание для заметки #{note_id} запланировано на {pre_reminder_time_utc.isoformat()} (за {pre_reminder_minutes} мин.)")


def remove_reminder_from_scheduler(note_id: int):
    if not note_id: return

    prefix = f"note_reminder_{note_id}"
    jobs_removed_count = 0
    for job in scheduler.get_jobs()[:]:
        if job.id.startswith(prefix):
            try:
                job.remove()
                jobs_removed_count += 1
            except Exception as e:
                logger.warning(f"Ошибка при удалении задачи {job.id}: {e}")

    if jobs_removed_count > 0:
        logger.info(f"Удалено {jobs_removed_count} напоминаний для заметки #{note_id} из планировщика.")


async def load_reminders_on_startup(bot: Bot):
    logger.info("Загрузка предстоящих напоминаний из базы данных...")
    # --- ИЗМЕНЕНИЕ ---
    # Нам нужно передавать VIP-статус и сюда
    notes_with_reminders = await db.get_notes_with_reminders()

    # Получаем VIP-статусы всех пользователей одним запросом для оптимизации
    user_ids = {note['telegram_id'] for note in notes_with_reminders}
    vip_statuses = {}
    if user_ids:
        # Этого можно не делать если у нас get_notes_with_reminders будет возвращать is_vip
        # но предположим что нет, и мы делаем так
        # TODO: Добавить is_vip в get_notes_with_reminders в будущем
        for user_id in user_ids:
            profile = await db.get_user_profile(user_id)
            if profile:
                vip_statuses[user_id] = profile.get('is_vip', False)

    count = 0
    for note in notes_with_reminders:
        note['is_vip'] = vip_statuses.get(note['telegram_id'], False)
        add_reminder_to_scheduler(bot, note)
        count += 1
    logger.info(f"Загружено и обработано {count} заметок с напоминаниями.")