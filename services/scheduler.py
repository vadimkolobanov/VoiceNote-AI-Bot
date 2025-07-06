# services/scheduler.py
import logging
import asyncio
import re
from datetime import datetime, time, timedelta, date
import pytz
from dateutil.rrule import rrulestr

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

import database_setup as db
from inline_keyboards import get_reminder_notification_keyboard
from services.tz_utils import format_datetime_for_user

logger = logging.getLogger(__name__)

jobstores = {'default': MemoryJobStore()}
executors = {'default': AsyncIOExecutor()}
scheduler = AsyncIOScheduler(jobstores=jobstores, executors=executors, timezone=pytz.utc)


async def reschedule_recurring_note(bot: Bot, note: dict):
    rule_str = note.get('recurrence_rule')
    last_due_date = note.get('due_date')
    telegram_id = note.get('telegram_id')

    if not rule_str or not last_due_date or not telegram_id:
        return

    user_profile = await db.get_user_profile(telegram_id)
    if not user_profile or not user_profile.get('is_vip'):
        logger.info(f"Повторение для заметки #{note['note_id']} остановлено, т.к. пользователь {telegram_id} не VIP.")
        await db.set_note_recurrence_rule(note['note_id'], telegram_id, rule=None)
        return

    try:
        if last_due_date.tzinfo is None:
            last_due_date = pytz.utc.localize(last_due_date)

        rule = rrulestr(rule_str, dtstart=last_due_date)
        next_occurrence = rule.after(last_due_date)

        if next_occurrence:
            logger.info(
                f"Пересоздание задачи #{note['note_id']}. Старая дата: {last_due_date}, Новая дата: {next_occurrence}")

            await db.update_note_due_date(note['note_id'], next_occurrence)

            note_data_for_scheduler = note.copy()
            note_data_for_scheduler.update({
                'due_date': next_occurrence,
                'default_reminder_time': user_profile.get('default_reminder_time'),
                'timezone': user_profile.get('timezone'),
                'pre_reminder_minutes': user_profile.get('pre_reminder_minutes'),
                'is_vip': user_profile.get('is_vip', False)
            })

            add_reminder_to_scheduler(bot, note_data_for_scheduler)
        else:
            logger.info(f"Повторяющаяся задача #{note['note_id']} завершила свой цикл.")

    except Exception as e:
        logger.error(f"Ошибка при пересоздании повторяющейся задачи #{note['note_id']}: {e}", exc_info=True)


async def send_reminder_notification(bot: Bot, telegram_id: int, note_id: int, note_text: str, due_date: datetime,
                                     is_pre_reminder: bool):
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

        if not is_pre_reminder:
            if note and note.get('recurrence_rule'):
                await reschedule_recurring_note(bot, note)

    except (TelegramBadRequest, TelegramForbiddenError) as e:
        if "chat not found" in e.message or "bot was blocked by the user" in e.message:
            logger.warning(f"Не удалось отправить напоминание пользователю {telegram_id}. Чат не найден или бот заблокирован. Ошибка: {e}")
            # Здесь можно добавить логику по деактивации пользователя в БД
        else:
            logger.error(f"Ошибка Telegram API при отправке напоминания {note_id} пользователю {telegram_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Не удалось отправить напоминание по заметке #{note_id} пользователю {telegram_id}: {e}", exc_info=True)


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
        asyncio.create_task(db.update_note_due_date(note_id, final_due_date_utc))
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
    notes_with_reminders = await db.get_notes_with_reminders()
    count = 0
    for note in notes_with_reminders:
        add_reminder_to_scheduler(bot, note)
        count += 1
    logger.info(f"Загружено и обработано {count} заметок с напоминаниями.")


def clean_llm_response(text: str) -> str:
    cleaned_text = re.sub(r'^```(html|)\s*|\s*```$', '', text.strip(), flags=re.MULTILINE)
    if cleaned_text.startswith('"') and cleaned_text.endswith('"'):
        cleaned_text = cleaned_text[1:-1]
    return cleaned_text.strip()


async def generate_and_send_daily_digest(bot: Bot, user: dict):
    telegram_id = user['telegram_id']
    user_timezone = user['timezone']
    user_name = user['first_name']

    logger.info(f"Подготовка утренней сводки для пользователя {telegram_id} (ТЗ: {user_timezone})")

    notes_today = await db.get_notes_for_today_digest(telegram_id, user_timezone)
    birthdays_soon = await db.get_birthdays_for_upcoming_digest(telegram_id)

    notes_text_parts = []
    if notes_today:
        for note in notes_today:
            time_str = note['due_date'].astimezone(pytz.timezone(user_timezone)).strftime('%H:%M')
            notes_text_parts.append(f"- {time_str}: {note['corrected_text']}")
        notes_for_prompt = "\n".join(notes_text_parts)
    else:
        notes_for_prompt = "На сегодня задач нет."

    bday_text_parts = []
    if birthdays_soon:
        for bday in birthdays_soon:
            date_str = f"{bday['birth_day']:02}.{bday['birth_month']:02}"
            bday_text_parts.append(f"- {date_str}: {bday['person_name']}")
        bdays_for_prompt = "\n".join(bday_text_parts)
    else:
        bdays_for_prompt = "Нет дней рождений в ближайшую неделю."

    prompt = f"""
Ты — дружелюбный и мотивирующий AI-ассистент. Твоя задача — составить короткое, бодрое и информативное утреннее сообщение для пользователя по имени {user_name}.
Сообщение должно быть в формате HTML для Telegram.

Вот данные для сводки:

**Задачи на сегодня:**
{notes_for_prompt}

**Дни рождения на неделе:**
{bdays_for_prompt}

---
ИНСТРУКЦИИ ПО ФОРМИРОВАНИЮ ОТВЕТА:

1.  **Если есть задачи на сегодня:**
    - Поприветствуй пользователя.
    - Перечисли задачи в виде списка.
    - Если есть дни рождения, упомяни их с иконкой 🎂.
    - Закончи мотивирующей фразой, например: "Продуктивного дня! 💪".

2.  **Если задач на сегодня НЕТ:**
    - Поприветствуй пользователя и пожелай хорошего дня.
    - Мягко подтолкни его к планированию. Используй фразы вроде "Отличный день, чтобы всё спланировать! Просто отправь мне голосовое или текстовое сообщение с твоими планами."
    - Если при этом есть дни рождения, обязательно упомяни их.
    - Если дней рождений тоже нет, предложи пользователю добавить их, например: "Кстати, чтобы не забыть поздравить близких, ты можешь добавить их дни рождения в разделе 'Профиль' -> '🎂 Дни рождения'."

3.  Будь кратким, позитивным и используй HTML-теги `<b>` для выделения и `<i>` для акцентов. Не используй markdown НЕ ПИШИ Вот HTML-сообщение для Telegram: в ответе.

4. Формат сводки только такой "Доброе утро, Deco! ☀️

Сегодня у тебя нет запланированных задач — отличный день, чтобы всё спланировать! Просто отправь мне голосовое или текстовое сообщение с твоими планами.  

Кстати, чтобы не забыть поздравить близких, ты можешь добавить их дни рождения в разделе "Профиль" -> "🎂 Дни рождения".  

Хорошего дня! 🌟" ну или список задач. Никакого лишнего текста 
"""
    digest_text = ""
    try:
        from llm_processor import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME
        import aiohttp

        if not all([DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME]):
            logger.warning(f"Пропуск генерации дайджеста для {telegram_id}: не настроен LLM.")
            return

        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": DEEPSEEK_MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 512,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    response_data = await resp.json()
                    raw_digest_text = response_data['choices'][0]['message']['content']
                    digest_text = clean_llm_response(raw_digest_text)
                else:
                    error_body = await resp.text()
                    logger.error(f"LLM API Error for digest: {resp.status}, Body: {error_body}")
                    digest_text = f"☀️ Доброе утро, {user_name}!\n\nНе удалось сгенерировать AI-сводку. Вот ваши данные:\n\n<b>Задачи на сегодня:</b>\n{notes_for_prompt}\n\n<b>Дни рождения на неделе:</b>\n{bdays_for_prompt}"

    except Exception as e:
        logger.error(f"Ошибка при обращении к LLM для генерации сводки для {telegram_id}: {e}")
        digest_text = f"☀️ Доброе утро, {user_name}!\n\nНе удалось сгенерировать AI-сводку. Вот ваши данные:\n\n<b>Задачи на сегодня:</b>\n{notes_for_prompt}\n\n<b>Дни рождения на неделе:</b>\n{bdays_for_prompt}"

    try:
        await bot.send_message(telegram_id, digest_text, parse_mode="HTML")
        logger.info(f"Утренняя сводка успешно отправлена пользователю {telegram_id}.")
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        if "chat not found" in e.message or "bot was blocked by the user" in e.message:
            logger.warning(f"Не удалось отправить сводку пользователю {telegram_id}. Чат не найден или бот заблокирован. Ошибка: {e}")
        else:
            logger.error(f"Ошибка Telegram API при отправке сводки {telegram_id}: {e}", exc_info=True)
    except Exception as e:
        if "can't parse entities" in str(e):
            logger.error(f"Не удалось отправить сводку для {telegram_id} из-за ошибки парсинга HTML. Отправляю без форматирования. Ошибка: {e}")
            text_without_html = re.sub('<[^<]+?>', '', digest_text)
            try:
                await bot.send_message(telegram_id, text_without_html, parse_mode=None)
                logger.info(f"Утренняя сводка успешно отправлена (без форматирования) пользователю {telegram_id}.")
            except Exception as final_e:
                 logger.error(f"Не удалось отправить сводку для {telegram_id} даже без форматирования: {final_e}")
        else:
            logger.error(f"Не удалось отправить сводку для {telegram_id}: {e}")


async def check_and_send_digests(bot: Bot):
    logger.info("Запущена ежечасная проверка для отправки утренних сводок.")
    users_to_notify = await db.get_vip_users_for_digest()
    if not users_to_notify:
        logger.info("Нет пользователей для отправки сводки в этот час.")
        return
    logger.info(f"Найдено {len(users_to_notify)} пользователей для отправки сводки.")
    tasks = [generate_and_send_daily_digest(bot, user) for user in users_to_notify]
    await asyncio.gather(*tasks)


def get_age_string(year: int, today: date) -> str:
    age = today.year - year
    if age <= 0: return ""
    if age % 10 == 1 and age % 100 != 11:
        return f"({age} год)"
    if 2 <= age % 10 <= 4 and (age % 100 < 10 or age % 100 >= 20):
        return f"({age} года)"
    return f"({age} лет)"


async def send_birthday_reminders(bot: Bot):
    logger.info("Запущена ежедневная проверка дней рождений...")
    all_birthdays = await db.get_all_birthdays_for_reminders()
    today_utc = datetime.now(pytz.utc)
    tasks = []
    for bday in all_birthdays:
        if bday['birth_day'] == today_utc.day and bday['birth_month'] == today_utc.month:
            user_id = bday['user_telegram_id']
            person_name = bday['person_name']
            age_info = ""
            if bday['birth_year']:
                age_info = " " + get_age_string(bday['birth_year'], today_utc.date())
            text = f"🎂 Напоминание! Сегодня важный день у <b>{person_name}</b>{age_info}!"
            tasks.append(bot.send_message(chat_id=user_id, text=text, parse_mode="HTML"))
            logger.info(f"Подготовлено напоминание о дне рождения '{person_name}' для пользователя {user_id}")
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                try:
                    chat_id = tasks[i].__self__.chat_id
                    logger.error(f"Не удалось отправить напоминание о дне рождения пользователю {chat_id}: {result}")
                except Exception:
                    logger.error(f"Не удалось отправить напоминание и получить chat_id: {result}")


async def setup_daily_jobs(bot: Bot):
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
    scheduler.add_job(
        check_and_send_digests,
        trigger='cron',
        hour='*',
        minute=1,
        kwargs={'bot': bot},
        id='hourly_digest_check',
        replace_existing=True
    )
    logger.info("Ежечасная задача проверки утренних сводок успешно запланирована.")