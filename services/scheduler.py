# services/scheduler.py
import logging
import asyncio
from datetime import datetime, time, timedelta, date
import pytz

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

import database_setup as db
from inline_keyboards import get_reminder_notification_keyboard
from services.tz_utils import format_datetime_for_user

logger = logging.getLogger(__name__)

# --- Scheduler Setup ---
jobstores = {'default': MemoryJobStore()}
executors = {'default': AsyncIOExecutor()}
scheduler = AsyncIOScheduler(jobstores=jobstores, executors=executors, timezone=pytz.utc)


# --- Напоминания для Заметок ---

async def send_reminder_notification(bot: Bot, telegram_id: int, note_id: int, note_text: str, due_date: datetime,
                                     is_pre_reminder: bool):
    """Асинхронная функция для отправки напоминания по ЗАМЕТКЕ."""
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

        header = f"🔔 {hbold('Предварительное напоминание')}" if is_pre_reminder else f"‼️ {hbold('НАПОМИНАНИЕ')}"

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
    """Добавляет задачи в планировщик с учетом VIP-статуса пользователя."""
    note_id = note.get('note_id')
    due_date_utc = note.get('due_date')
    is_vip = note.get('is_vip', False)

    if not note_id or not due_date_utc:
        return

    remove_reminder_from_scheduler(note_id)

    if due_date_utc.tzinfo is None:
        due_date_utc = pytz.utc.localize(due_date_utc)

    is_time_ambiguous = (due_date_utc.time() == time(0, 0, 0))

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
        logger.info(f"Напоминание для заметки #{note_id} (Free User) не будет установлено: время не указано явно.")
        return
    else:
        final_due_date_utc = due_date_utc

    now_utc = datetime.now(pytz.utc)

    if final_due_date_utc > now_utc:
        job_id_main = f"note_reminder_{note_id}_main"
        scheduler.add_job(
            send_reminder_notification,
            trigger='date', run_date=final_due_date_utc, id=job_id_main,
            kwargs={
                'bot': bot, 'telegram_id': note['telegram_id'], 'note_id': note_id,
                'note_text': note['corrected_text'], 'due_date': final_due_date_utc,
                'is_pre_reminder': False
            },
            replace_existing=True
        )
        logger.info(f"Основное напоминание для заметки #{note_id} запланировано на {final_due_date_utc.isoformat()}")

    if is_vip:
        pre_reminder_minutes = note.get('pre_reminder_minutes', 0)
        if pre_reminder_minutes > 0:
            pre_reminder_time_utc = final_due_date_utc - timedelta(minutes=pre_reminder_minutes)
            if pre_reminder_time_utc > now_utc:
                job_id_pre = f"note_reminder_{note_id}_pre_{pre_reminder_minutes}"
                scheduler.add_job(
                    send_reminder_notification,
                    trigger='date', run_date=pre_reminder_time_utc, id=job_id_pre,
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
    notes_with_reminders = await db.get_notes_with_reminders()
    count = 0
    for note in notes_with_reminders:
        # VIP-статус уже включен в результат get_notes_with_reminders
        add_reminder_to_scheduler(bot, note)
        count += 1
    logger.info(f"Загружено и обработано {count} заметок с напоминаниями.")


# --- НОВЫЙ БЛОК: Напоминания о Днях Рождения ---

def get_age_string(year: int, today: date) -> str:
    """Формирует строку с возрастом, учитывая падежи."""
    age = today.year - year
    # Если день рождения в этом году еще не наступил
    if (today.month, today.day) < (1, 1):  # Это условие некорректно, дата рождения может быть любой.
        # Правильная проверка: сравнить (сегодняшний месяц, день) с (месяц, день рождения)
        # Но для простоты пока считаем, что возраст наступает в 00:00 дня рождения
        pass  # Просто для наглядности, сейчас логика верна

    if age <= 0: return ""  # Не показываем возраст для будущих дат

    if age % 10 == 1 and age % 100 != 11:
        return f"({age} год)"
    if 2 <= age % 10 <= 4 and (age % 100 < 10 or age % 100 >= 20):
        return f"({age} года)"
    return f"({age} лет)"


async def send_birthday_reminders(bot: Bot):
    """
    Ежедневная задача: проверяет все дни рождения и отправляет уведомления.
    """
    logger.info("Запущена ежедневная проверка дней рождений...")
    all_birthdays = await db.get_all_birthdays_for_reminders()
    today_utc = datetime.now(pytz.utc)

    tasks = []
    for bday in all_birthdays:
        # Проверяем, наступает ли день рождения сегодня
        if bday['birth_day'] == today_utc.day and bday['birth_month'] == today_utc.month:
            user_id = bday['user_telegram_id']
            person_name = bday['person_name']

            age_info = ""
            if bday['birth_year']:
                age_info = " " + get_age_string(bday['birth_year'], today_utc.date())

            text = f"🎂 Напоминание! Сегодня важный день у <b>{person_name}</b>{age_info}!"

            # Собираем задачи в список, чтобы выполнить их асинхронно
            tasks.append(
                bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
            )
            logger.info(f"Подготовлено напоминание о дне рождения '{person_name}' для пользователя {user_id}")

    if tasks:
        # Отправляем все подготовленные сообщения
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                bday = all_birthdays[i]
                logger.error(
                    f"Не удалось отправить напоминание о дне рождения '{bday['person_name']}' пользователю {bday['user_telegram_id']}: {result}")


async def setup_daily_jobs(bot: Bot):
    """Добавляет все ежедневные/повторяющиеся задачи в планировщик."""
    # Запускаем каждый день в 00:05 по UTC
    scheduler.add_job(
        send_birthday_reminders,
        trigger='cron',
        hour=0,
        minute=5,
        kwargs={'bot': bot},
        id='daily_birthday_check',
        replace_existing=True
    )
    logger.info("Ежедневная задача проверки дней рождений успешно запланирована.")