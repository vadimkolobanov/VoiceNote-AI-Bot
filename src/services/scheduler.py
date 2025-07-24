# src/services/scheduler.py
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
from aiogram.utils.markdown import hbold, hcode, hitalic
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from ..database import note_repo, birthday_repo, user_repo
from ..bot.common_utils.callbacks import NoteAction
from .tz_utils import format_datetime_for_user
from . import push_service, weather_service
from ..core.config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME, WEATHER_SERVICE_ENABLED

logger = logging.getLogger(__name__)

jobstores = {'default': MemoryJobStore()}
executors = {'default': AsyncIOExecutor()}
scheduler = AsyncIOScheduler(jobstores=jobstores, executors=executors, timezone=pytz.utc)


def add_reminder_to_scheduler(bot: Bot, note: dict):
    """
    Добавляет или обновляет напоминания для заметки в планировщик.
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
    """Удаляет все задачи (основные и предварительные) для указанной заметки."""
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


async def send_reminder_notification(bot: Bot, telegram_id: int, note_id: int, note_text: str, due_date: datetime,
                                     is_pre_reminder: bool):
    """Отправляет сообщение с напоминанием о заметке."""
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

        header = f"🔔 Предварительное напоминание" if is_pre_reminder else f"❗️ НАПОМИНАНИЕ"

        text = (
            f"{header}\n\n"
            f"Заметка: #{hcode(str(note_id))}\n"
            f"Срок: {hitalic(formatted_due_date)}\n\n"
            f"📝 {hbold('Текст заметки:')}\n"
            f"{hcode(note_text)}"
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
    """Отправляет пользователю напоминание о списке покупок."""
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
    """Пересчитывает дату следующего повторения для задачи и добавляет ее в планировщик."""
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

            note_data_for_scheduler = {**note, **user_profile, 'due_date': next_occurrence}
            add_reminder_to_scheduler(bot, note_data_for_scheduler)
        else:
            logger.info(f"Повторяющаяся задача #{note['note_id']} завершила свой цикл.")

    except Exception as e:
        logger.error(f"Ошибка при пересоздании повторяющейся задачи #{note['note_id']}: {e}", exc_info=True)


def clean_llm_response(text: str) -> str:
    """
    Утилита для очистки ответа LLM от markdown-блоков, вступительных фраз
    и невалидных для Telegram HTML-тегов.
    """
    text = text.strip()
    cleaned_text = re.sub(r'^```(html|json|)\s*|\s*```$', '', text, flags=re.MULTILINE)
    cleaned_text = re.sub(r'^(вот|конечно,?\s*вот|готовое\s*сообщение|html-сообщение\s*для\s*telegram).*?:?\s*', '',
                          cleaned_text, flags=re.IGNORECASE | re.DOTALL).strip()
    cleaned_text = cleaned_text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    if cleaned_text.startswith('"') and cleaned_text.endswith('"'):
        cleaned_text = cleaned_text[1:-1]

    lines = cleaned_text.splitlines()
    if lines and "telegram" in lines[0].lower() and ":" in lines[0]:
        cleaned_text = "\n".join(lines[1:]).strip()

    return cleaned_text


async def generate_and_send_daily_digest(bot: Bot, user: dict):
    """Генерирует и отправляет утреннюю сводку для одного пользователя."""
    telegram_id = user['telegram_id']
    user_timezone = user['timezone']
    user_name = user['first_name']
    city = user.get('city_name')

    logger.info(f"Подготовка утренней сводки для пользователя {telegram_id} (ТЗ: {user_timezone})")

    weather_forecast = "Прогноз погоды недоступен."
    if city and WEATHER_SERVICE_ENABLED:
        weather_forecast = await weather_service.get_weather_for_city(city) or "Не удалось получить прогноз."

    notes_today = await note_repo.get_notes_for_today_digest(telegram_id, user_timezone)
    birthdays_soon = await birthday_repo.get_birthdays_for_upcoming_digest(telegram_id)

    notes_for_prompt = "На сегодня задач нет."
    if notes_today:
        notes_text_parts = []
        for note in notes_today:
            time_str = note['due_date'].astimezone(pytz.timezone(user_timezone)).strftime('%H:%M')
            notes_text_parts.append(f"- {time_str}: {note['corrected_text']}")
        notes_for_prompt = "\n".join(notes_text_parts)

    bdays_for_prompt = "Нет дней рождений в ближайшую неделю."
    if birthdays_soon:
        bday_text_parts = []
        for bday in birthdays_soon:
            date_str = f"{bday['birth_day']:02}.{bday['birth_month']:02}"
            bday_text_parts.append(f"- {date_str}: {bday['person_name']}")
        bdays_for_prompt = "\n".join(bday_text_parts)

    prompt = f"""
Ты — дружелюбный и мотивирующий AI-ассистент. Твоя задача — составить короткое, бодрое и информативное утреннее сообщение для пользователя по имени {user_name}.
Сообщение должно быть в формате HTML для Telegram.

Вот данные для сводки:

**Прогноз погоды:**
{weather_forecast}

**Задачи на сегодня:**
{notes_for_prompt}

**Дни рождения на неделе:**
{bdays_for_prompt}

---
ИНСТРУКЦИИ ПО ФОРМИРОВАНИЮ ОТВЕТА:

1.  Начни с погоды, если она доступна и не является ошибкой. Используй иконку 🌦️. Например: "🌦️ Погода {weather_forecast}".
2.  Далее, если есть задачи, перечисли их.
3.  Если есть дни рождения, упомяни их.
4.  Закончи мотивирующей фразой.
5.  Если задач нет, после погоды пожелай хорошего дня и мягко подтолкни к планированию.
6.  Будь кратким, позитивным и используй HTML-теги `<b>` и `<i>`. Не используй `<br>`. Используй `\n` для переноса строки. Не пиши ничего лишнего.
"""

    import aiohttp
    digest_text = ""
    try:
        if not all([DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL_NAME]):
            raise ValueError("LLM не настроен для генерации дайджеста")

        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": DEEPSEEK_MODEL_NAME, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3, "max_tokens": 512
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    response_data = await resp.json()
                    digest_text = clean_llm_response(response_data['choices'][0]['message']['content'])
                else:
                    raise Exception(f"LLM API Error: {resp.status}, Body: {await resp.text()}")
    except Exception as e:
        logger.error(f"Ошибка генерации AI-дайджеста для {telegram_id}: {e}. Отправка стандартного шаблона.")
        notes_html_list = notes_for_prompt.splitlines()
        notes_html = "\n".join(notes_html_list) if notes_today else "Задач нет."
        bdays_html_list = bdays_for_prompt.splitlines()
        bdays_html = "\n".join(bdays_html_list) if birthdays_soon else "Дней рождений нет."
        weather_html = f"🌦️ {weather_forecast}\n\n" if city and WEATHER_SERVICE_ENABLED and "Не удалось" not in weather_forecast else ""
        digest_text = f"☀️ Доброе утро, {user_name}!\n\n{weather_html}<b>Задачи на сегодня:</b>\n{notes_html}\n\n<b>Дни рождения на неделе:</b>\n{bdays_html}"

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
    """Проверяет, кому из пользователей нужно отправить утреннюю сводку, и запускает задачи."""
    logger.info("Запущена ежечасная проверка для отправки утренних сводок.")
    users_to_notify = await user_repo.get_vip_users_for_digest()
    if not users_to_notify:
        logger.info("Нет пользователей для отправки сводки в этот час.")
        return
    logger.info(f"Найдено {len(users_to_notify)} пользователей для отправки сводки.")
    tasks = [generate_and_send_daily_digest(bot, user) for user in users_to_notify]
    await asyncio.gather(*tasks)


def get_age_string(year: int, today: date) -> str:
    """Возвращает строку с возрастом и правильным окончанием (год/года/лет)."""
    age = today.year - year
    if age <= 0: return ""
    if age % 10 == 1 and age % 100 != 11:
        return f"({age} год)"
    if 2 <= age % 10 <= 4 and (age % 100 < 10 or age % 100 >= 20):
        return f"({age} года)"
    return f"({age} лет)"


async def send_birthday_reminders(bot: Bot):
    """Проверяет все дни рождения и отправляет напоминания тем, у кого сегодня праздник."""
    logger.info("Запущена ежедневная проверка дней рождений...")
    all_birthdays = await birthday_repo.get_all_birthdays_for_reminders()
    today_utc = datetime.now(pytz.utc)

    user_reminders = {}

    for bday in all_birthdays:
        if bday['birth_day'] == today_utc.day and bday['birth_month'] == today_utc.month:
            user_id = bday['user_telegram_id']
            person_name = bday['person_name']
            age_info = ""
            if bday['birth_year']:
                age_info = " " + get_age_string(bday['birth_year'], today_utc.date())

            text = f"Сегодня важный день у <b>{person_name}</b>{age_info}!"
            if user_id not in user_reminders:
                user_reminders[user_id] = []
            user_reminders[user_id].append(text)

    if not user_reminders:
        logger.info("На сегодня нет дней рождений для напоминания.")
        return

    for user_id, reminders in user_reminders.items():
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


async def load_reminders_on_startup(bot: Bot):
    """Загружает все активные напоминания из БД в планировщик при старте бота."""
    logger.info("Загрузка предстоящих напоминаний из базы данных...")
    notes_with_reminders = await note_repo.get_notes_with_reminders()
    count = 0
    for note in notes_with_reminders:
        add_reminder_to_scheduler(bot, note)
        count += 1
    logger.info(f"Загружено и обработано {count} заметок с напоминаниями.")


async def setup_daily_jobs(bot: Bot):
    """Добавляет в планировщик ежедневные и периодические задачи."""
    scheduler.add_job(
        send_birthday_reminders,
        trigger='cron',
        hour=0,
        minute=5,
        kwargs={'bot': bot},
        id='daily_birthday_check',
        replace_existing=True
    )
    logger.info("Ежедневная задача проверки дней рождений запланирована на 00:05 UTC.")

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