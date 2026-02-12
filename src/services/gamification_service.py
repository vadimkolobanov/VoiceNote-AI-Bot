# src/services/gamification_service.py
import logging
from dataclasses import dataclass
from enum import Enum
from datetime import time

# database repos импортируются лениво внутри check_and_grant_achievements(),
# чтобы избежать циклических импортов

logger = logging.getLogger(__name__)

XP_REWARDS = {
    'create_note_text': 1,
    'create_note_voice': 3,
    'note_completed': 2,
    'add_birthday_manual': 10,
    'import_birthdays_file': 50,
    'note_shared': 20,
    'snooze_note': 1,  # Небольшая награда за каждое откладывание
}


@dataclass
class Achievement:
    code: str
    icon: str
    name: str
    description: str
    xp_reward: int
    is_secret: bool = False


class AchievCode(Enum):
    FIRST_NOTE = "FIRST_NOTE"
    NOTE_SCRIBE_1 = "NOTE_SCRIBE_1"
    NOTE_SCRIBE_2 = "NOTE_SCRIBE_2"
    NOTE_SCRIBE_3 = "NOTE_SCRIBE_3"
    VOICE_MASTER_1 = "VOICE_MASTER_1"
    VOICE_MASTER_2 = "VOICE_MASTER_2"
    COMMANDER = "COMMANDER"
    SOCIAL_CONNECTOR = "SOCIAL_CONNECTOR"
    PARTY_PLANNER_1 = "PARTY_PLANNER_1"
    PARTY_PLANNER_2 = "PARTY_PLANNER_2"
    VIP_CLUB = "VIP_CLUB"
    PROCRASTINATOR = "PROCRASTINATOR"  # "ещё пять минуточек"
    URBANIST = "URBANIST"  # "Мой адрес не дом и не улица"
    TIME_LORD = "TIME_LORD"  # "Я сам решаю, когда нужно"
    ROUTINE_MASTER = "ROUTINE_MASTER"  # "заполнил дневник"
    CERTIFIED_SPECIALIST = "CERTIFIED_SPECIALIST"  # "Дипломированный специалист"
    HAPPY_BIRTHDAY = "HAPPY_BIRTHDAY"  # "Я родился"
    HARDCORE_MODE = "HARDCORE_MODE"  # "Любитель хардкора"


ACHIEVEMENTS_LIST = [
    Achievement(AchievCode.FIRST_NOTE.value, "👶", "Первые шаги", "Создать первую заметку", 25),
    Achievement(AchievCode.NOTE_SCRIBE_1.value, "📝", "Писарь", "Создать 10 заметок", 50),
    Achievement(AchievCode.NOTE_SCRIBE_2.value, "✍️", "Летописец", "Создать 50 заметок", 100),
    Achievement(AchievCode.NOTE_SCRIBE_3.value, "📖", "Хранитель знаний", "Создать 250 заметок", 250),
    Achievement(AchievCode.VOICE_MASTER_1.value, "🎤", "Глас народа", "Создать 10 голосовых заметок", 75),
    Achievement(AchievCode.VOICE_MASTER_2.value, "🗣️", "Оратор", "Создать 50 голосовых заметок", 150),
    Achievement(AchievCode.COMMANDER.value, "✅", "Командир", "Выполнить 25 заметок", 100),
    Achievement(AchievCode.SOCIAL_CONNECTOR.value, "🤝", "Командный игрок", "Поделиться заметкой", 50),
    Achievement(AchievCode.PARTY_PLANNER_1.value, "🎂", "Душа компании", "Добавить 5 дней рождений", 50),
    Achievement(AchievCode.PARTY_PLANNER_2.value, "🎉", "Мастер вечеринок", "Добавить 25 дней рождений", 150),
    Achievement(AchievCode.VIP_CLUB.value, "👑", "VIP-персона", "Получить VIP-статус", 200),
    Achievement(AchievCode.PROCRASTINATOR.value, "😴", "Ещё пять минуточек", "Отложить одну и ту же заметку 3 раза", 30),
    Achievement(AchievCode.URBANIST.value, "🏙️", "Мой адрес не дом и не улица", "Установить город для прогноза погоды",
                20),
    Achievement(AchievCode.TIME_LORD.value, "⏳", "Повелитель времени", "Изменить время утренней сводки", 20),
    Achievement(AchievCode.ROUTINE_MASTER.value, "🔁", "Человек-привычка", "Иметь 5 активных повторяющихся заметок", 75),
    Achievement(AchievCode.CERTIFIED_SPECIALIST.value, "🎓", "Дипломированный специалист",
                "Прочитать все гайды по функциям бота", 100),
    Achievement(AchievCode.HAPPY_BIRTHDAY.value, "🥳", "Я родился!", "Получить от бота поздравление с днём рождения",
                150, is_secret=True),
    Achievement(AchievCode.HARDCORE_MODE.value, "🔥", "Любитель хардкора",
                "Создать 10 заметок без установленного часового пояса", 50, is_secret=True),
]

ACHIEVEMENTS_BY_CODE = {a.code: a for a in ACHIEVEMENTS_LIST}


async def check_and_grant_achievements(bot, user_id: int, silent: bool = False):
    from ..database import user_repo, note_repo, birthday_repo

    user_achievements = await user_repo.get_user_achievements_codes(user_id)
    user_profile = await user_repo.get_user_profile(user_id)  # Получаем профиль один раз

    if not user_profile:
        return  # На всякий случай, если профиль не найден

    # --- Note-related achievements ---
    total_notes, voice_notes = await note_repo.count_total_and_voice_notes(user_id)
    if total_notes >= 1 and AchievCode.FIRST_NOTE.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.FIRST_NOTE.value, silent=silent)
    if total_notes >= 10 and AchievCode.NOTE_SCRIBE_1.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.NOTE_SCRIBE_1.value, silent=silent)
    if total_notes >= 50 and AchievCode.NOTE_SCRIBE_2.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.NOTE_SCRIBE_2.value, silent=silent)
    if total_notes >= 250 and AchievCode.NOTE_SCRIBE_3.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.NOTE_SCRIBE_3.value, silent=silent)

    if voice_notes >= 10 and AchievCode.VOICE_MASTER_1.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.VOICE_MASTER_1.value, silent=silent)
    if voice_notes >= 50 and AchievCode.VOICE_MASTER_2.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.VOICE_MASTER_2.value, silent=silent)

    completed_notes = await note_repo.count_completed_notes(user_id)
    if completed_notes >= 25 and AchievCode.COMMANDER.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.COMMANDER.value, silent=silent)

    # Check for social connector achievement
    has_shared = await note_repo.did_user_share_note(user_id)
    if has_shared and AchievCode.SOCIAL_CONNECTOR.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.SOCIAL_CONNECTOR.value, silent=silent)

    # --- Birthday-related achievements ---
    birthdays_count = await birthday_repo.count_birthdays_for_user(user_id)
    if birthdays_count >= 5 and AchievCode.PARTY_PLANNER_1.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.PARTY_PLANNER_1.value, silent=silent)
    if birthdays_count >= 25 and AchievCode.PARTY_PLANNER_2.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.PARTY_PLANNER_2.value, silent=silent)

    # --- Other achievements ---
    if user_profile.get('is_vip') and AchievCode.VIP_CLUB.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.VIP_CLUB.value, silent=silent)

    # Проверки для новых ачивок
    if user_profile.get('city_name') and AchievCode.URBANIST.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.URBANIST.value, silent=silent)

    # Проверка на "Повелителя времени" (сравниваем с временем по умолчанию)
    digest_time = user_profile.get('daily_digest_time')
    if digest_time is not None and digest_time != time(9, 0) and AchievCode.TIME_LORD.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.TIME_LORD.value, silent=silent)

    # Проверка на "Человека-привычку"
    recurring_notes_count = await note_repo.count_recurring_notes(user_id)
    if recurring_notes_count >= 5 and AchievCode.ROUTINE_MASTER.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.ROUTINE_MASTER.value, silent=silent)

    # Проверка на "Дипломированного специалиста" (6 - это количество гайдов)
    if len(user_profile.get('viewed_guides',
                            [])) >= 6 and AchievCode.CERTIFIED_SPECIALIST.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.CERTIFIED_SPECIALIST.value, silent=silent)

    # Проверка на "Любителя хардкора" (только если пользователь явно оставил UTC, создав 10 заметок)
    # Не выдаем ачивку если пользователь просто не настроил часовой пояс
    user_timezone = user_profile.get('timezone', 'UTC')
    has_completed_onboarding = user_profile.get('has_completed_onboarding', False)
    if user_timezone == 'UTC' and has_completed_onboarding and total_notes >= 10 and AchievCode.HARDCORE_MODE.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.HARDCORE_MODE.value, silent=silent)