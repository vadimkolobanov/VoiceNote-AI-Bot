# src/services/scheduler.py
import logging
import asyncio
import re
from datetime import datetime, time, timedelta, date
import pytz
from dateutil.rrule import rrulestr, rrule, WEEKLY, DAILY

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from aiogram.utils.markdown import hbold, hcode, hitalic
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from ..database import note_repo, birthday_repo, user_repo, habit_repo, reminder_repo
from ..bot.common_utils.callbacks import NoteAction
from .tz_utils import format_datetime_for_user
from . import push_service, weather_service, llm
from ..core.config import WEATHER_SERVICE_ENABLED, DIGEST_UPCOMING_DAYS, DIGEST_OVERDUE_LIMIT
# AchievCode импортируется лениво внутри функции, чтобы избежать циклического импорта
from ..bot.modules.habits.keyboards import get_habit_tracking_keyboard

logger = logging.getLogger(__name__)

jobstores = {'default': MemoryJobStore()}
executors = {'default': AsyncIOExecutor()}
scheduler = AsyncIOScheduler(jobstores=jobstores, executors=executors, timezone=pytz.utc)


def add_reminder_to_scheduler(bot: Bot, note: dict):
    note_id = note.get('note_id')
    due_date_utc = note.get('due_date')
    is_vip = note.get('is_vip', False)

    if not note_id or not due_date_utc:
        return

    remove_reminder_from_scheduler(note_id)

    if due_date_utc.tzinfo is None:
        due_date_utc = pytz.utc.localize(due_date_utc)

    is_time_ambiguous = (due_date_utc.time() == time(0, 0, 0))
    final_due_date_utc = due_date_utc

    if is_time_ambiguous:
        default_time = note.get('default_reminder_time', time(9, 0)) if is_vip else time(12, 0)
        user_timezone_str = note.get('timezone', 'UTC')
        try:
            user_tz = pytz.timezone(user_timezone_str)
        except pytz.UnknownTimeZoneError:
            user_tz = pytz.utc

        local_due_date = datetime.combine(due_date_utc.date(), default_time)
        aware_local_due_date = user_tz.localize(local_due_date)
        final_due_date_utc = aware_local_due_date.astimezone(pytz.utc)

        asyncio.create_task(note_repo.update_note_due_date(note_id, final_due_date_utc))
        log_msg_time = f"{default_time.strftime('%H:%M')} (Free-user default)" if not is_vip else f"{default_time.strftime('%H:%M')} (VIP-user setting)"
        logger.info(f"Для заметки #{note_id} установлено время напоминания на {log_msg_time}")

    now_utc = datetime.now(pytz.utc)

    if final_due_date_utc > now_utc:
        job_id_main = f"note_reminder_{note_id}_main"
        scheduler.add_job(
            send_reminder_notification,
            trigger='date',
            run_date=final_due_date_utc,
            id=job_id_main,
            kwargs={
                'bot': bot, 'telegram_id': note['telegram_id'], 'note_id': note_id,
                'note_text': note.get('summary_text', note['corrected_text']),
                'due_date': final_due_date_utc,
                'is_pre_reminder': False
            },
            replace_existing=True
        )
        logger.info(f"Основное напоминание для заметки #{note_id} запланировано на {final_due_date_utc.isoformat()}")

        # Phase 3a: синхронизируем unified reminders read-model
        asyncio.create_task(reminder_repo.upsert_note_reminder(
            user_id=note['telegram_id'],
            note_id=note_id,
            title=note.get('summary_text') or note.get('corrected_text', '')[:250],
            due_date=final_due_date_utc,
            recurrence_rule=note.get('recurrence_rule'),
            pre_reminder_minutes=note.get('pre_reminder_minutes', 0) if is_vip else 0,
            is_completed=note.get('is_completed', False),
            is_archived=note.get('is_archived', False),
        ))

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
                        'note_text': note.get('summary_text', note['corrected_text']),
                        'due_date': final_due_date_utc,
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
        # Phase 3a: чистим единую таблицу reminders
        asyncio.create_task(reminder_repo.delete_note_reminder(note_id))


async def send_reminder_notification(bot: Bot, telegram_id: int, note_id: int, note_text: str, due_date: datetime,
                                     is_pre_reminder: bool):
    from ..bot.modules.notes.keyboards import get_reminder_notification_keyboard

    logger.info(
        f"Отправка {'предварительного ' if is_pre_reminder else 'основного'} напоминания по заметке #{note_id} пользователю {telegram_id}")

    note = await note_repo.get_note_by_id(note_id, telegram_id)
    if not note or note.get('is_completed') or note.get('is_archived'):
        logger.info(f"Напоминание для заметки #{note_id} отменено: заметка неактивна.")
        remove_reminder_from_scheduler(note_id)
        return

    try:
        user_profile = await user_repo.get_user_profile(telegram_id)
        user_timezone = user_profile.get('timezone', 'UTC') if user_profile else 'UTC'
        actual_due_date = note.get('due_date', due_date)
        formatted_due_date = format_datetime_for_user(actual_due_date, user_timezone)

        if is_pre_reminder:
            # Вычисляем минуты до основного напоминания
            time_diff = actual_due_date - datetime.now(pytz.utc)
            pre_minutes = max(1, int(time_diff.total_seconds() / 60))
            header = f"🔔 {hbold('Напоминание заранее')}"
            text = (
                f"{header}\n\n"
                f"Через {pre_minutes} минут у вас:\n"
                f"📝 {hbold(note_text)}\n\n"
                f"⏰ {hitalic(formatted_due_date)}\n\n"
                f"💡 Подготовьтесь заранее!"
            )
        else:
            header = f"❗️ {hbold('Время выполнить задачу!')}"
            text = (
                f"{header}\n\n"
                f"📝 {hbold('Задача:')}\n"
                f"{hcode(note_text)}\n\n"
                f"⏰ {hbold('Срок:')} {hitalic(formatted_due_date)}\n\n"
                f"💪 {hitalic('Вы справитесь!')}"
            )
        keyboard = get_reminder_notification_keyboard(note_id, is_pre_reminder=is_pre_reminder)
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML", reply_markup=keyboard)
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.warning(f"Не удалось отправить TG-напоминание пользователю {telegram_id}. Ошибка: {e}")
    except Exception as e:
        logger.error(f"Не удалось отправить TG-напоминание по заметке #{note_id}: {e}", exc_info=True)

    push_title = "📌 Напоминание" if is_pre_reminder else "❗️ Напоминание"
    await push_service.send_push_to_user(
        telegram_id=telegram_id,
        title=push_title,
        body=note_text,
        data={"noteId": str(note_id)}
    )

    if not is_pre_reminder and note.get('recurrence_rule'):
        await reschedule_recurring_note(bot, note)


async def send_shopping_list_ping(bot: Bot, user_id: int, note_id: int):
    logger.info(f"Отправка 'пинга' о списке покупок #{note_id} пользователю {user_id}")
    try:
        note = await note_repo.get_note_by_id(note_id, user_id)
        if not note or note.get('is_archived'):
            logger.info(f"Пи-пинг о списке #{note_id} отменен, так как список заархивирован.")
            return

        text = "🔔 Напоминаю про ваш список покупок!"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Посмотреть список",
                                  callback_data=NoteAction(action="view", note_id=note_id).pack())]
        ])
        await bot.send_message(user_id, text, reply_markup=kb)
    except Exception as e:
        logger.error(f"Не удалось отправить 'пинг' о списке покупок #{note_id} пользователю {user_id}: {e}")


async def reschedule_recurring_note(bot: Bot, note: dict):
    rule_str = note.get('recurrence_rule')
    last_due_date = note.get('due_date')
    telegram_id = note.get('telegram_id')

    if not all([rule_str, last_due_date, telegram_id]):
        return

    user_profile = await user_repo.get_user_profile(telegram_id)
    if not user_profile or not user_profile.get('is_vip'):
        logger.info(f"Повторение для заметки #{note['note_id']} остановлено, т.к. пользователь {telegram_id} не VIP.")
        await note_repo.set_note_recurrence_rule(note['note_id'], telegram_id, rule=None)
        return

    try:
        if last_due_date.tzinfo is None:
            last_due_date = pytz.utc.localize(last_due_date)

        rule = rrulestr(rule_str, dtstart=last_due_date)
        next_occurrence = rule.after(last_due_date)

        if next_occurrence:
            logger.info(
                f"Пересоздание повторяющейся задачи #{note['note_id']}. Старая дата: {last_due_date}, Новая дата: {next_occurrence}")

            await note_repo.update_note_due_date(note['note_id'], next_occurrence)
            note['due_date'] = next_occurrence

            note_data_for_scheduler = {**note, **user_profile}
            add_reminder_to_scheduler(bot, note_data_for_scheduler)
        else:
            logger.info(f"Повторяющаяся задача #{note['note_id']} завершила свой цикл.")

    except Exception as e:
        logger.error(f"Ошибка при пересоздании повторяющейся задачи #{note['note_id']}: {e}", exc_info=True)


async def generate_and_send_daily_digest(bot: Bot, user: dict):
    telegram_id = user['telegram_id']
    user_timezone = user['timezone']
    user_name = user['first_name']
    city = user.get('city_name')
    user_tz_obj = pytz.timezone(user_timezone)

    logger.info(f"Подготовка утренней сводки для пользователя {telegram_id} (ТЗ: {user_timezone})")

    weather_forecast = "Прогноз погоды недоступен."
    if city and WEATHER_SERVICE_ENABLED:
        weather_forecast = await weather_service.get_weather_for_city(city) or "Не удалось получить прогноз."

    notes_today = await note_repo.get_notes_for_today_digest(telegram_id, user_timezone)
    notes_upcoming = await note_repo.get_notes_for_upcoming_digest(telegram_id, user_timezone, DIGEST_UPCOMING_DAYS)
    notes_overdue = await note_repo.get_overdue_notes_for_digest(telegram_id, DIGEST_OVERDUE_LIMIT)
    birthdays_soon = await birthday_repo.get_birthdays_for_upcoming_digest(telegram_id)

    notes_for_prompt = "На сегодня задач нет."
    if notes_today:
        notes_text_parts = []
        for note in notes_today:
            time_str = note['due_date'].astimezone(user_tz_obj).strftime('%H:%M')
            notes_text_parts.append(f"- {time_str}: {note['corrected_text']}")
        notes_for_prompt = "\n".join(notes_text_parts)

    upcoming_for_prompt = "Нет запланированных задач."
    if notes_upcoming:
        upcoming_text_parts = []
        for note in notes_upcoming:
            date_str = note['due_date'].astimezone(user_tz_obj).strftime('%d.%m (%a)')
            time_str = note['due_date'].astimezone(user_tz_obj).strftime('%H:%M')
            upcoming_text_parts.append(f"- {date_str} в {time_str}: {note['corrected_text']}")
        upcoming_for_prompt = "\n".join(upcoming_text_parts)

    overdue_for_prompt = "Нет пропущенных задач."
    if notes_overdue:
        overdue_text_parts = [f"- {note['corrected_text']}" for note in notes_overdue]
        overdue_for_prompt = "\n".join(overdue_text_parts)

    bdays_for_prompt = "Нет дней рождений в ближайшую неделю."
    if birthdays_soon:
        bday_text_parts = []
        for bday in birthdays_soon:
            date_str = f"{bday['birth_day']:02}.{bday['birth_month']:02}"
            bday_text_parts.append(f"- {date_str}: {bday['person_name']}")
        bdays_for_prompt = "\n".join(bday_text_parts)

    digest_text = ""
    try:
        llm_result = await llm.generate_digest_text(
            user_name=user_name,
            weather_forecast=weather_forecast,
            notes_for_prompt=notes_for_prompt,
            bdays_for_prompt=bdays_for_prompt,
            upcoming_for_prompt=upcoming_for_prompt,
            overdue_for_prompt=overdue_for_prompt
        )
        if "error" in llm_result:
            raise ValueError(llm_result["error"])
        digest_text = llm_result.get("content", "")

    except Exception as e:
        logger.error(f"Ошибка генерации AI-дайджеста для {telegram_id}: {e}. Отправка стандартного шаблона.")
        notes_html = "\n".join(notes_for_prompt.splitlines()) if notes_today else "<i>Задач нет. Время планировать!</i>"
        upcoming_html = "\n".join(upcoming_for_prompt.splitlines()) if notes_upcoming else ""
        overdue_html = "\n".join(overdue_for_prompt.splitlines()) if notes_overdue else ""
        bdays_html = "\n".join(
            bdays_for_prompt.splitlines()) if birthdays_soon else "<i>Нет ближайших дней рождений.</i>"
        weather_html = f"🌦️ {weather_forecast}\n\n" if city and WEATHER_SERVICE_ENABLED and "Не удалось" not in weather_forecast else ""

        digest_parts = [f"☀️ <b>Доброе утро, {user_name}!</b>", weather_html,
                        f"<b>Задачи на сегодня:</b>\n{notes_html}"]
        if upcoming_html:
            digest_parts.append(f"\n<b>Планы на неделю:</b>\n{upcoming_html}")
        if overdue_html:
            digest_parts.append(f"\n<b>Пропущенные задачи:</b>\n{overdue_html}")
        digest_parts.append(f"\n<b>Дни рождения на неделе:</b>\n{bdays_html}\n\n<i>Отличного дня!</i>")
        digest_text = "\n".join(filter(None, digest_parts))

    if not digest_text:
        logger.warning(f"Сгенерирован пустой дайджест для {telegram_id}, отправка отменена.")
        return

    try:
        await bot.send_message(telegram_id, digest_text, parse_mode="HTML")
        logger.info(f"Утренняя сводка успешно отправлена в Telegram пользователю {telegram_id}.")
    except Exception as e:
        logger.error(f"Ошибка отправки утренней сводки в Telegram пользователю {telegram_id}: {e}")

    push_body = re.sub('<[^<]+?>', '', digest_text)
    await push_service.send_push_to_user(
        telegram_id=telegram_id,
        title="☀️ Ваша утренняя сводка",
        body=push_body,
        data={"action": "show_digest"}
    )


async def check_and_send_digests(bot: Bot):
    logger.info("Запущена ежечасная проверка для отправки утренних сводок.")
    users_to_notify = await user_repo.get_vip_users_for_digest()
    if not users_to_notify:
        logger.info("Нет пользователей для отправки сводки в этот час.")
        return
    logger.info(f"Найдено {len(users_to_notify)} пользователей для отправки сводки.")
    tasks = [generate_and_send_daily_digest(bot, user) for user in users_to_notify]
    await asyncio.gather(*tasks)


def get_age_string(year: int, today: date) -> str:
    age = today.year - year
    if age < 0: return ""
    if age == 0: return "(до года)"
    if age % 10 == 1 and age % 100 != 11:
        return f"({age} год)"
    if 2 <= age % 10 <= 4 and (age % 100 < 10 or age % 100 >= 20):
        return f"({age} года)"
    return f"({age} лет)"


async def send_birthday_reminders(bot: Bot):
    """
    Проверяет дни рождения для всех пользователей и отправляет напоминания в 9:00 по локальному времени каждого пользователя.
    Запускается каждый час, чтобы покрыть все часовые пояса.
    """
    logger.info("Запущена проверка дней рождений...")
    all_birthdays = await birthday_repo.get_all_birthdays_for_reminders()
    now_utc = datetime.now(pytz.utc)
    
    # Группируем дни рождения по пользователям
    birthdays_by_user = {}
    for bday in all_birthdays:
        user_id = bday['user_telegram_id']
        if user_id not in birthdays_by_user:
            birthdays_by_user[user_id] = []
        birthdays_by_user[user_id].append(bday)
    
    if not birthdays_by_user:
        logger.info("Нет дней рождений в базе данных.")
        return
    
    user_reminders = {}
    
    # Проверяем для каждого пользователя отдельно по его локальному времени
    for user_id, user_birthdays in birthdays_by_user.items():
        try:
            user_profile = await user_repo.get_user_profile(user_id)
            if not user_profile:
                continue
            
            user_timezone_str = user_profile.get('timezone', 'UTC')
            try:
                user_tz = pytz.timezone(user_timezone_str)
            except pytz.UnknownTimeZoneError:
                user_tz = pytz.utc
                logger.warning(f"Неизвестный часовой пояс '{user_timezone_str}' для пользователя {user_id}, используется UTC")
            
            # Получаем текущее время в часовом поясе пользователя
            user_local_time = now_utc.astimezone(user_tz)
            
            # Отправляем напоминания только в 9:00 по локальному времени пользователя
            if user_local_time.hour != 9 or user_local_time.minute != 0:
                continue
            
            # Проверяем, есть ли сегодня дни рождения по локальному времени пользователя
            today_day = user_local_time.day
            today_month = user_local_time.month
            
            for bday in user_birthdays:
                if bday['birth_day'] == today_day and bday['birth_month'] == today_month:
                    person_name = bday['person_name']
                    age_info = ""
                    if bday['birth_year']:
                        age_info = " " + get_age_string(bday['birth_year'], user_local_time.date())
                    
                    text = f"Сегодня важный день у <b>{person_name}</b>{age_info}!"
                    if user_id not in user_reminders:
                        user_reminders[user_id] = []
                    user_reminders[user_id].append(text)
        
        except Exception as e:
            logger.error(f"Ошибка при обработке дней рождений для пользователя {user_id}: {e}", exc_info=True)
            continue
    
    if not user_reminders:
        logger.info("На сегодня нет дней рождений для напоминания (или не подошло время отправки).")
        return
    
    # Отправляем напоминания
    for user_id, reminders in user_reminders.items():
        try:
            user_has_self_bday = await user_repo.has_self_birthday_record(user_id)
            if user_has_self_bday:
                user_achievements = await user_repo.get_user_achievements_codes(user_id)
                from ..services.gamification_service import AchievCode
                if AchievCode.HAPPY_BIRTHDAY.value not in user_achievements:
                    await user_repo.grant_achievement(bot, user_id, AchievCode.HAPPY_BIRTHDAY.value, silent=True)
                    reminders.append("\nP.S. С Днём Рождения! 🎉 Загляните в профиль, там для вас сюрприз 😉")
            
            full_tg_text = "🎂 Напоминание о днях рождения!\n\n" + "\n".join(reminders)
            push_body = reminders[0] if len(
                reminders) == 1 else f"Сегодня {len(reminders)} важных события! Посмотрите в приложении."
            push_body = re.sub('<[^<]+?>', '', push_body)
            
            try:
                await bot.send_message(chat_id=user_id, text=full_tg_text, parse_mode="HTML")
                logger.info(f"Напоминание о {len(reminders)} ДР отправлено в Telegram пользователю {user_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить напоминание о ДР в Telegram пользователю {user_id}: {e}")
            
            await push_service.send_push_to_user(
                telegram_id=user_id,
                title="🎂 Напоминание о дне рождения!",
                body=push_body,
                data={"action": "show_birthdays"}
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминаний о ДР пользователю {user_id}: {e}", exc_info=True)


async def send_habit_reminder(bot: Bot, habit: dict):
    user_id = habit['user_telegram_id']
    habit_id = habit['id']
    name = habit['name']

    logger.info(f"Отправка напоминания о привычке #{habit_id} ('{name}') пользователю {user_id}")

    try:
        text = f"💪 Время для вашей привычки!\n\n{hbold(name)}\n\nВыполнили сегодня?"
        keyboard = get_habit_tracking_keyboard(habit_id)
        await bot.send_message(user_id, text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Не удалось отправить напоминание о привычке #{habit_id}: {e}")


async def setup_habit_reminders(bot: Bot):
    """Устанавливает или обновляет все задачи-напоминания о привычках."""
    logger.info("Загрузка и настройка напоминаний о привычках...")
    all_habits = await habit_repo.get_all_active_habits_for_scheduler()

    for job in scheduler.get_jobs():
        if job.id.startswith("habit_reminder_"):
            job.remove()

    count = 0
    for habit in all_habits:
        try:
            user_profile = await user_repo.get_user_profile(habit['user_telegram_id'])
            user_tz = pytz.timezone(user_profile.get('timezone', 'UTC'))

            rule = rrulestr(habit['frequency_rule'])
            cron_kwargs = {"timezone": user_tz}

            if rule._byweekday is not None:
                cron_kwargs['day_of_week'] = ",".join([str(d) for d in rule._byweekday])
            if rule._bymonthday:
                cron_kwargs['day'] = ",".join([str(d) for d in rule._bymonthday])

            cron_kwargs['hour'] = habit['reminder_time'].hour
            cron_kwargs['minute'] = habit['reminder_time'].minute

            scheduler.add_job(
                send_habit_reminder,
                trigger='cron',
                id=f"habit_reminder_{habit['id']}",
                kwargs={'bot': bot, 'habit': habit},
                replace_existing=True,
                **cron_kwargs
            )
            count += 1

            # Phase 3a: sync reminders read-model
            asyncio.create_task(reminder_repo.upsert_habit_reminder(
                user_id=habit['user_telegram_id'],
                habit_id=habit['id'],
                name=habit['name'],
                frequency_rule=habit['frequency_rule'],
                is_active=habit.get('is_active', True),
                reminder_time=habit.get('reminder_time'),
            ))
        except Exception as e:
            logger.error(f"Ошибка при настройке напоминания для привычки #{habit['id']}: {e}")

    logger.info(f"Успешно настроено {count} напоминаний о привычках.")


async def send_weekly_habit_report_to_user(bot: Bot, user_id: int):
    """
    Формирует и отправляет отчет по привычкам для конкретного пользователя.
    """
    user_habits = await habit_repo.get_user_habits(user_id)
    if not user_habits:
        logger.info(f"У пользователя {user_id} нет привычек, пропускаем отчет.")
        return

    logger.info(f"Формирование отчета для пользователя {user_id}, привычек: {len(user_habits)}")

    today = datetime.now(pytz.utc).date()
    start_of_week = today - timedelta(days=6)

    report_parts = [f"📊 {hbold('Ваш отчет по привычкам за неделю!')}\n"]
    total_completed = 0
    total_possible = 0

    for habit in user_habits:
        stats_raw = await habit_repo.get_weekly_stats(habit['id'], start_of_week)
        stats_by_date = {s['track_date'].isoformat(): s['status'] for s in stats_raw}

        progress_bar = []
        completed_count = 0

        try:
            rule = rrulestr(habit['frequency_rule'])
        except Exception:
            continue

        # Определяем дни, когда привычка должна была выполняться на этой неделе
        days_of_week_in_rule = {d.weekday for d in rule._byweekday} if rule._byweekday else set(range(7))

        week_dates = []
        for i in range(7):
            current_day = start_of_week + timedelta(days=i)
            if current_day.weekday() in days_of_week_in_rule:
                week_dates.append(current_day)

        if not week_dates: continue

        for day_date in week_dates:
            day_str = day_date.isoformat()
            if stats_by_date.get(day_str) == 'completed':
                progress_bar.append("✅")
                completed_count += 1
            elif stats_by_date.get(day_str) == 'skipped':
                progress_bar.append("❌")
            else:
                progress_bar.append("➖")

        total_completed += completed_count
        total_possible += len(week_dates)

        progress_str = "".join(progress_bar)
        report_parts.append(f"• {hitalic(habit['name'])}: {completed_count}/{len(week_dates)}\n  {progress_str}")

    if total_possible > 0:
        overall_progress = int((total_completed / total_possible) * 100)
        report_parts.append(f"\nОбщий прогресс: {hbold(f'{overall_progress}%')}. Так держать!")

        try:
            await bot.send_message(user_id, "\n".join(report_parts), parse_mode="HTML")
            logger.info(f"Отчет по привычкам успешно отправлен пользователю {user_id}")
        except Exception as e:
            logger.warning(f"Не удалось отправить отчет по привычкам пользователю {user_id}: {e}")
    else:
        logger.info(f"У пользователя {user_id} нет возможных дней для отслеживания привычек на этой неделе.")


async def check_and_send_weekly_habit_reports(bot: Bot):
    """
    Проверяет для каких пользователей наступило воскресенье 18:00 по их часовому поясу
    и отправляет им отчеты по привычкам.
    """
    logger.info("Проверка необходимости отправки еженедельных отчетов по привычкам.")
    all_users_with_habits = await user_repo.get_all_users_with_habits()

    now_utc = datetime.now(pytz.utc)

    for user_id in all_users_with_habits:
        try:
            user_profile = await user_repo.get_user_profile(user_id)
            if not user_profile:
                continue

            user_tz_str = user_profile.get('timezone', 'UTC')
            user_tz = pytz.timezone(user_tz_str)
            user_time = now_utc.astimezone(user_tz)

            # Проверяем: воскресенье и час 18
            if user_time.weekday() == 6 and user_time.hour == 18:
                logger.info(f"Отправка еженедельного отчета пользователю {user_id} (TZ: {user_tz_str})")
                await send_weekly_habit_report_to_user(bot, user_id)
        except Exception as e:
            logger.error(f"Ошибка при проверке/отправке отчета пользователю {user_id}: {e}", exc_info=True)


async def load_reminders_on_startup(bot: Bot):
    logger.info("Загрузка предстоящих напоминаний из базы данных...")
    notes_with_reminders = await note_repo.get_notes_with_reminders()
    count = 0
    for note in notes_with_reminders:
        add_reminder_to_scheduler(bot, note)
        count += 1
    logger.info(f"Загружено и обработано {count} заметок с напоминаниями.")
    await setup_habit_reminders(bot)


async def send_reengagement_message(bot: Bot, user_id: int, days_since_registration: int, has_notes: bool):
    """Отправляет сообщение для возврата неактивного пользователя."""
    try:
        user_profile = await user_repo.get_user_profile(user_id)
        if not user_profile:
            return
        
        user_name = user_profile.get('first_name', 'друг')
        
        if not has_notes:
            # Пользователь не создал ни одной заметки
            if days_since_registration == 1:
                text = (
                    f"👋 Привет, {user_name}!\n\n"
                    f"Я заметил, что вы еще не создали свою первую заметку.\n\n"
                    f"💡 {hbold('Попробуйте прямо сейчас!')}\n"
                    f"Просто отправьте мне любую мысль, например:\n"
                    f"• {hitalic('«Позвонить маме завтра в 10»')}\n"
                    f"• {hitalic('«Купить молоко и хлеб»')}\n"
                    f"• {hitalic('«Встреча с командой в пятницу»')}\n\n"
                    f"Я превращу это в умную заметку с напоминанием! 🚀"
                )
            elif days_since_registration == 3:
                text = (
                    f"👋 {user_name}, я все еще здесь!\n\n"
                    f"Вы еще не попробовали создать заметку. Это займет всего 10 секунд!\n\n"
                    f"🎯 {hbold('Что я умею:')}\n"
                    f"• Создавать заметки из текста или голоса\n"
                    f"• Ставить автоматические напоминания\n"
                    f"• Ведить списки покупок\n"
                    f"• Напоминать о днях рождения\n\n"
                    f"Просто отправьте мне любое сообщение, и я покажу, как это работает! ✨"
                )
            else:
                return  # Не отправляем больше сообщений
        else:
            # Пользователь создал заметки, но неактивен
            if days_since_registration == 7:
                text = (
                    f"👋 Привет, {user_name}!\n\n"
                    f"Давно не виделись! У вас есть активные заметки, которые ждут вашего внимания.\n\n"
                    f"📝 Загляните в меню «📝 Мои заметки», чтобы посмотреть, что у вас запланировано.\n\n"
                    f"💡 {hbold('Совет:')} Создавайте новые заметки, и я буду напоминать о них вовремя!"
                )
            else:
                return
        
        await bot.send_message(user_id, text, parse_mode="HTML")
        logger.info(f"Re-engagement сообщение отправлено пользователю {user_id} (дней с регистрации: {days_since_registration})")
        
    except TelegramForbiddenError:
        logger.warning(f"Пользователь {user_id} заблокировал бота, пропускаем re-engagement.")
    except Exception as e:
        logger.error(f"Ошибка при отправке re-engagement сообщения пользователю {user_id}: {e}")


async def check_and_send_reengagement_messages(bot: Bot):
    """Проверяет неактивных пользователей и отправляет им сообщения для возврата."""
    logger.info("Проверка неактивных пользователей для re-engagement...")
    
    from ..database.connection import get_db_pool
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Пользователи без заметок: 1 и 3 дня после регистрации
        query_no_notes = """
            SELECT u.telegram_id, u.created_at, 
                   COUNT(n.note_id) as notes_count,
                   EXTRACT(DAY FROM (NOW() - u.created_at))::int as days_ago
            FROM users u
            LEFT JOIN notes n ON u.telegram_id = n.telegram_id
            WHERE u.has_completed_onboarding = TRUE
              AND EXTRACT(DAY FROM (NOW() - u.created_at))::int IN (1, 3)
            GROUP BY u.telegram_id, u.created_at
            HAVING COUNT(n.note_id) = 0
        """
        
        # Пользователи с заметками, но неактивные 7 дней
        query_inactive = """
            SELECT DISTINCT u.telegram_id, u.created_at,
                   COUNT(n.note_id) as notes_count,
                   EXTRACT(DAY FROM (NOW() - u.created_at))::int as days_ago
            FROM users u
            JOIN notes n ON u.telegram_id = n.telegram_id
            LEFT JOIN user_actions ua ON u.telegram_id = ua.user_telegram_id 
                AND ua.created_at > NOW() - INTERVAL '7 days'
            WHERE u.has_completed_onboarding = TRUE
              AND EXTRACT(DAY FROM (NOW() - u.created_at))::int = 7
              AND ua.id IS NULL
            GROUP BY u.telegram_id, u.created_at
            HAVING COUNT(n.note_id) > 0
        """
        
        # Проверяем пользователей без заметок
        records = await conn.fetch(query_no_notes)
        for record in records:
            user_id = record['telegram_id']
            days_ago = int(record['days_ago'])
            await send_reengagement_message(bot, user_id, days_ago, has_notes=False)
        
        # Проверяем неактивных пользователей с заметками
        records = await conn.fetch(query_inactive)
        for record in records:
            user_id = record['telegram_id']
            days_ago = int(record['days_ago'])
            await send_reengagement_message(bot, user_id, days_ago, has_notes=True)
    
    logger.info("Проверка re-engagement завершена.")


async def setup_daily_jobs(bot: Bot):
    # Проверяем дни рождения каждый час, чтобы отправлять напоминания в 9:00 по локальному времени каждого пользователя
    scheduler.add_job(
        send_birthday_reminders,
        trigger='cron',
        hour='*',
        minute=0,
        kwargs={'bot': bot},
        id='hourly_birthday_check',
        replace_existing=True
    )
    logger.info("Ежечасная задача проверки дней рождений запланирована (напоминания отправляются в 9:00 по локальному времени каждого пользователя).")

    scheduler.add_job(
        check_and_send_digests,
        trigger='cron',
        hour='*',
        minute=1,
        kwargs={'bot': bot},
        id='hourly_digest_check',
        replace_existing=True
    )
    logger.info("Ежечасная задача проверки утренних сводок запланирована.")

    scheduler.add_job(
        check_and_send_weekly_habit_reports,
        trigger='cron',
        hour='*',
        minute=0,
        kwargs={'bot': bot},
        id='hourly_habit_report_check',
        replace_existing=True
    )
    logger.info("Ежечасная задача проверки и отправки отчетов по привычкам запланирована.")
    
    # Re-engagement: проверяем каждый день в 10:00 UTC
    scheduler.add_job(
        check_and_send_reengagement_messages,
        trigger='cron',
        hour=10,
        minute=0,
        kwargs={'bot': bot},
        id='daily_reengagement_check',
        replace_existing=True
    )
    logger.info("Ежедневная задача re-engagement запланирована на 10:00 UTC.")