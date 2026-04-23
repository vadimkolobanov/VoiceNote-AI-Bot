# src/services/scheduler.py
#
# M0 stub: старый многомодульный scheduler удалён (weather/gamification/habits-reminders
# привязаны к legacy-моделям notes/habits/birthdays).
# В M2 здесь появится новый scheduler поверх schema `moments` + `scheduled_jobs` (§4.8).
# Сейчас оставлены только публичные имена, которые импортирует src/main.py.
import logging

import pytz
from aiogram import Bot
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

jobstores = {"default": MemoryJobStore()}
executors = {"default": AsyncIOExecutor()}
scheduler = AsyncIOScheduler(jobstores=jobstores, executors=executors, timezone=pytz.utc)


async def load_reminders_on_startup(bot: Bot) -> None:
    """Noop до M2. Планировщик напоминаний перестраивается на модель `moments`."""
    logger.info("scheduler.load_reminders_on_startup: noop (M0 stub, реализация в M2)")


async def setup_daily_jobs(bot: Bot) -> None:
    """Noop до M2. Дайджест/habit_check перестраиваются на модель `moments`."""
    logger.info("scheduler.setup_daily_jobs: noop (M0 stub, реализация в M2)")
