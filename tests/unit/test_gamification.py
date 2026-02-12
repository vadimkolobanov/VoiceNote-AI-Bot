import pytest
from datetime import time
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.gamification_service import (
    XP_REWARDS,
    AchievCode,
    ACHIEVEMENTS_LIST,
    ACHIEVEMENTS_BY_CODE,
    check_and_grant_achievements,
    Achievement,
)


# ---------------------------------------------------------------------------
# Data-structure tests (no mocks needed)
# ---------------------------------------------------------------------------

EXPECTED_XP_KEYS = {
    "create_note_text",
    "create_note_voice",
    "note_completed",
    "add_birthday_manual",
    "import_birthdays_file",
    "note_shared",
    "snooze_note",
}


class TestXPRewards:
    def test_xp_rewards_has_all_expected_keys(self):
        assert set(XP_REWARDS.keys()) == EXPECTED_XP_KEYS

    def test_all_xp_values_are_positive_integers(self):
        for key, value in XP_REWARDS.items():
            assert isinstance(value, int), f"XP_REWARDS['{key}'] is not an int"
            assert value > 0, f"XP_REWARDS['{key}'] must be positive, got {value}"


class TestAchievementsData:
    def test_achievements_list_has_expected_length(self):
        assert len(ACHIEVEMENTS_LIST) == 18

    def test_all_achievement_codes_are_unique(self):
        codes = [a.code for a in ACHIEVEMENTS_LIST]
        assert len(codes) == len(set(codes)), "Duplicate achievement codes found"

    def test_all_achievcode_enum_values_have_corresponding_achievement(self):
        achievement_codes = {a.code for a in ACHIEVEMENTS_LIST}
        for member in AchievCode:
            assert member.value in achievement_codes, (
                f"AchievCode.{member.name} ({member.value}) has no matching Achievement"
            )

    def test_achievements_by_code_matches_list(self):
        assert len(ACHIEVEMENTS_BY_CODE) == len(ACHIEVEMENTS_LIST)
        for achievement in ACHIEVEMENTS_LIST:
            assert achievement.code in ACHIEVEMENTS_BY_CODE
            assert ACHIEVEMENTS_BY_CODE[achievement.code] is achievement

    def test_all_achievements_have_positive_xp_reward(self):
        for a in ACHIEVEMENTS_LIST:
            assert a.xp_reward > 0, (
                f"Achievement '{a.code}' has non-positive xp_reward: {a.xp_reward}"
            )

    def test_all_achievements_are_achievement_instances(self):
        for a in ACHIEVEMENTS_LIST:
            assert isinstance(a, Achievement)

    def test_achievcode_enum_count_matches_achievements_list(self):
        assert len(AchievCode) == len(ACHIEVEMENTS_LIST)


# ---------------------------------------------------------------------------
# check_and_grant_achievements tests (async, with mocks)
# ---------------------------------------------------------------------------

# Патчим database repos, которые check_and_grant_achievements импортирует лениво
_DB_PREFIX = "src.database"


def _default_profile(**overrides):
    """Return a minimal user-profile dict with sensible defaults."""
    profile = {
        "is_vip": False,
        "city_name": None,
        "daily_digest_time": time(9, 0),
        "timezone": "Europe/Moscow",
        "has_completed_onboarding": True,
        "viewed_guides": [],
    }
    profile.update(overrides)
    return profile


@pytest.fixture
def mock_repos():
    """Patch all repository calls used by check_and_grant_achievements."""
    m_get_achiev = AsyncMock(return_value=set())
    m_get_profile = AsyncMock(return_value=_default_profile())
    m_count_notes = AsyncMock(return_value=(0, 0))
    m_count_completed = AsyncMock(return_value=0)
    m_shared = AsyncMock(return_value=False)
    m_count_bdays = AsyncMock(return_value=0)
    m_count_recurring = AsyncMock(return_value=0)
    m_grant = AsyncMock()

    mock_user = MagicMock()
    mock_user.get_user_achievements_codes = m_get_achiev
    mock_user.get_user_profile = m_get_profile
    mock_user.grant_achievement = m_grant

    mock_note = MagicMock()
    mock_note.count_total_and_voice_notes = m_count_notes
    mock_note.count_completed_notes = m_count_completed
    mock_note.did_user_share_note = m_shared
    mock_note.count_recurring_notes = m_count_recurring

    mock_bday = MagicMock()
    mock_bday.count_birthdays_for_user = m_count_bdays

    with (
        patch(f"{_DB_PREFIX}.user_repo", mock_user),
        patch(f"{_DB_PREFIX}.note_repo", mock_note),
        patch(f"{_DB_PREFIX}.birthday_repo", mock_bday),
    ):
        yield {
            "get_achievements_codes": m_get_achiev,
            "get_user_profile": m_get_profile,
            "count_total_and_voice_notes": m_count_notes,
            "count_completed_notes": m_count_completed,
            "did_user_share_note": m_shared,
            "count_birthdays_for_user": m_count_bdays,
            "count_recurring_notes": m_count_recurring,
            "grant_achievement": m_grant,
        }


@pytest.mark.asyncio
async def test_first_note_grants_first_note_achievement(mock_repos):
    mock_repos["count_total_and_voice_notes"].return_value = (1, 0)
    bot = MagicMock()

    await check_and_grant_achievements(bot, user_id=123)

    mock_repos["grant_achievement"].assert_any_call(
        bot, 123, AchievCode.FIRST_NOTE.value, silent=False
    )


@pytest.mark.asyncio
async def test_ten_notes_grants_note_scribe_1(mock_repos):
    mock_repos["count_total_and_voice_notes"].return_value = (10, 0)
    bot = MagicMock()

    await check_and_grant_achievements(bot, user_id=42)

    granted_codes = {
        call.args[2] for call in mock_repos["grant_achievement"].call_args_list
    }
    assert AchievCode.FIRST_NOTE.value in granted_codes
    assert AchievCode.NOTE_SCRIBE_1.value in granted_codes


@pytest.mark.asyncio
async def test_vip_user_grants_vip_club(mock_repos):
    mock_repos["get_user_profile"].return_value = _default_profile(is_vip=True)
    mock_repos["count_total_and_voice_notes"].return_value = (0, 0)
    bot = MagicMock()

    await check_and_grant_achievements(bot, user_id=7)

    granted_codes = {
        call.args[2] for call in mock_repos["grant_achievement"].call_args_list
    }
    assert AchievCode.VIP_CLUB.value in granted_codes


@pytest.mark.asyncio
async def test_already_has_achievement_does_not_regranted(mock_repos):
    mock_repos["count_total_and_voice_notes"].return_value = (1, 0)
    mock_repos["get_achievements_codes"].return_value = {AchievCode.FIRST_NOTE.value}
    bot = MagicMock()

    await check_and_grant_achievements(bot, user_id=99)

    granted_codes = {
        call.args[2] for call in mock_repos["grant_achievement"].call_args_list
    }
    assert AchievCode.FIRST_NOTE.value not in granted_codes


@pytest.mark.asyncio
async def test_user_with_city_grants_urbanist(mock_repos):
    mock_repos["get_user_profile"].return_value = _default_profile(city_name="Moscow")
    bot = MagicMock()

    await check_and_grant_achievements(bot, user_id=55)

    granted_codes = {
        call.args[2] for call in mock_repos["grant_achievement"].call_args_list
    }
    assert AchievCode.URBANIST.value in granted_codes


@pytest.mark.asyncio
async def test_zero_notes_empty_profile_grants_nothing(mock_repos):
    bot = MagicMock()

    await check_and_grant_achievements(bot, user_id=1)

    mock_repos["grant_achievement"].assert_not_called()


@pytest.mark.asyncio
async def test_no_profile_returns_early(mock_repos):
    mock_repos["get_user_profile"].return_value = None
    bot = MagicMock()

    await check_and_grant_achievements(bot, user_id=404)

    mock_repos["grant_achievement"].assert_not_called()
    mock_repos["count_total_and_voice_notes"].assert_not_called()


@pytest.mark.asyncio
async def test_shared_note_grants_social_connector(mock_repos):
    mock_repos["did_user_share_note"].return_value = True
    bot = MagicMock()

    await check_and_grant_achievements(bot, user_id=88)

    granted_codes = {
        call.args[2] for call in mock_repos["grant_achievement"].call_args_list
    }
    assert AchievCode.SOCIAL_CONNECTOR.value in granted_codes


@pytest.mark.asyncio
async def test_five_birthdays_grants_party_planner_1(mock_repos):
    mock_repos["count_birthdays_for_user"].return_value = 5
    bot = MagicMock()

    await check_and_grant_achievements(bot, user_id=33)

    granted_codes = {
        call.args[2] for call in mock_repos["grant_achievement"].call_args_list
    }
    assert AchievCode.PARTY_PLANNER_1.value in granted_codes


@pytest.mark.asyncio
async def test_five_recurring_notes_grants_routine_master(mock_repos):
    mock_repos["count_recurring_notes"].return_value = 5
    bot = MagicMock()

    await check_and_grant_achievements(bot, user_id=77)

    granted_codes = {
        call.args[2] for call in mock_repos["grant_achievement"].call_args_list
    }
    assert AchievCode.ROUTINE_MASTER.value in granted_codes


@pytest.mark.asyncio
async def test_changed_digest_time_grants_time_lord(mock_repos):
    mock_repos["get_user_profile"].return_value = _default_profile(
        daily_digest_time=time(8, 0),
        is_vip=True,
    )
    bot = MagicMock()

    await check_and_grant_achievements(bot, user_id=66)

    granted_codes = {
        call.args[2] for call in mock_repos["grant_achievement"].call_args_list
    }
    assert AchievCode.TIME_LORD.value in granted_codes
