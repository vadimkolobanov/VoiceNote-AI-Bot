# src/services/gamification_service.py
import logging
from dataclasses import dataclass
from enum import Enum

from ..database import user_repo, note_repo, birthday_repo

logger = logging.getLogger(__name__)

XP_REWARDS = {
    'create_note_text': 1,
    'create_note_voice': 3,
    'note_completed': 2,
    'add_birthday_manual': 10,
    'import_birthdays_file': 50,
    'note_shared': 20,
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
]

ACHIEVEMENTS_BY_CODE = {a.code: a for a in ACHIEVEMENTS_LIST}


async def check_and_grant_achievements(bot, user_id: int, silent: bool = False):
    user_achievements = await user_repo.get_user_achievements_codes(user_id)

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
    user_profile = await user_repo.get_user_profile(user_id)
    if user_profile.get('is_vip') and AchievCode.VIP_CLUB.value not in user_achievements:
        await user_repo.grant_achievement(bot, user_id, AchievCode.VIP_CLUB.value, silent=silent)