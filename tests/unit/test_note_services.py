import pytest
from datetime import datetime, timedelta

import pytz

from src.bot.modules.notes.services import _calculate_due_date_from_components


MOSCOW_TZ = pytz.timezone("Europe/Moscow")
NYC_TZ = pytz.timezone("America/New_York")


# ---------------------------------------------------------------------------
# None / empty input
# ---------------------------------------------------------------------------

def test_none_input_returns_none():
    assert _calculate_due_date_from_components(None, MOSCOW_TZ) is None


def test_empty_dict_returns_none():
    assert _calculate_due_date_from_components({}, MOSCOW_TZ) is None


# ---------------------------------------------------------------------------
# Relative offsets
# ---------------------------------------------------------------------------

def test_relative_days_adds_one_day():
    result = _calculate_due_date_from_components({"relative_days": 1}, MOSCOW_TZ)
    assert result is not None
    expected_approx = datetime.now(pytz.utc) + timedelta(days=1)
    assert abs((result - expected_approx).total_seconds()) < 60


def test_relative_hours_adds_two_hours():
    result = _calculate_due_date_from_components({"relative_hours": 2}, MOSCOW_TZ)
    assert result is not None
    expected_approx = datetime.now(pytz.utc) + timedelta(hours=2)
    assert abs((result - expected_approx).total_seconds()) < 60


def test_relative_minutes_adds_thirty():
    result = _calculate_due_date_from_components({"relative_minutes": 30}, MOSCOW_TZ)
    assert result is not None
    expected_approx = datetime.now(pytz.utc) + timedelta(minutes=30)
    assert abs((result - expected_approx).total_seconds()) < 60


# ---------------------------------------------------------------------------
# Absolute set_hour / set_minute
# ---------------------------------------------------------------------------

def test_set_hour_and_minute():
    """Setting hour=15 minute=30 should produce that time in user tz, converted to UTC."""
    result = _calculate_due_date_from_components(
        {"set_hour": 15, "set_minute": 30}, MOSCOW_TZ
    )
    assert result is not None
    # Convert result back to Moscow to verify the time components
    result_moscow = result.astimezone(MOSCOW_TZ)
    assert result_moscow.hour == 15
    assert result_moscow.minute == 30


def test_set_day_and_month():
    """Setting day=25 month=12 should produce Dec 25 in user tz."""
    result = _calculate_due_date_from_components(
        {"set_day": 25, "set_month": 12, "set_hour": 12, "set_minute": 0}, MOSCOW_TZ
    )
    assert result is not None
    result_moscow = result.astimezone(MOSCOW_TZ)
    assert result_moscow.month == 12
    assert result_moscow.day == 25


# ---------------------------------------------------------------------------
# Relative + absolute combined
# ---------------------------------------------------------------------------

def test_relative_day_plus_set_hour():
    """relative_days=1 + set_hour=10 should be tomorrow at 10:00 user tz."""
    result = _calculate_due_date_from_components(
        {"relative_days": 1, "set_hour": 10, "set_minute": 0}, MOSCOW_TZ
    )
    assert result is not None
    result_moscow = result.astimezone(MOSCOW_TZ)
    tomorrow_moscow = datetime.now(MOSCOW_TZ) + timedelta(days=1)
    assert result_moscow.date() == tomorrow_moscow.date()
    assert result_moscow.hour == 10
    assert result_moscow.minute == 0


# ---------------------------------------------------------------------------
# is_today_explicit flag
# ---------------------------------------------------------------------------

def test_is_today_explicit_allows_past_time():
    """With is_today_explicit=True, time in the past should NOT be bumped to tomorrow."""
    result = _calculate_due_date_from_components(
        {"is_today_explicit": True, "set_hour": 0, "set_minute": 0}, MOSCOW_TZ
    )
    assert result is not None
    result_moscow = result.astimezone(MOSCOW_TZ)
    # Should be today's date, even though 00:00 is in the past
    today_moscow = datetime.now(MOSCOW_TZ).date()
    assert result_moscow.date() == today_moscow


# ---------------------------------------------------------------------------
# Conflict resolution: set_hour wins over relative_hours
# ---------------------------------------------------------------------------

def test_conflict_set_hour_wins_over_relative_hours():
    """When both relative_hours and set_hour are present, set_hour wins."""
    result = _calculate_due_date_from_components(
        {"relative_hours": 3, "set_hour": 15, "set_minute": 0}, MOSCOW_TZ
    )
    assert result is not None
    result_moscow = result.astimezone(MOSCOW_TZ)
    assert result_moscow.hour == 15
    assert result_moscow.minute == 0


def test_conflict_set_minute_wins_over_relative_minutes():
    """When both relative_minutes and set_minute are present, set_minute wins."""
    result = _calculate_due_date_from_components(
        {"relative_minutes": 45, "set_minute": 30, "set_hour": 12}, MOSCOW_TZ
    )
    assert result is not None
    result_moscow = result.astimezone(MOSCOW_TZ)
    assert result_moscow.minute == 30


# ---------------------------------------------------------------------------
# Result is always UTC
# ---------------------------------------------------------------------------

def test_result_is_utc():
    """The returned datetime must always be in UTC."""
    result = _calculate_due_date_from_components({"relative_days": 1}, MOSCOW_TZ)
    assert result is not None
    assert result.tzinfo is not None
    assert result.tzinfo == pytz.utc


# ---------------------------------------------------------------------------
# Different timezones produce different UTC results
# ---------------------------------------------------------------------------

def test_different_timezone_different_utc():
    """Same set_hour in Moscow vs New York should yield different UTC values."""
    components = {"relative_days": 1, "set_hour": 12, "set_minute": 0}
    result_moscow = _calculate_due_date_from_components(components, MOSCOW_TZ)
    result_nyc = _calculate_due_date_from_components(components, NYC_TZ)
    assert result_moscow is not None
    assert result_nyc is not None
    # Moscow is UTC+3, New York is UTC-5 (or UTC-4 in DST).
    # The UTC representations must differ.
    assert result_moscow != result_nyc


# ---------------------------------------------------------------------------
# Edge case: None values in dict fields treated as 0 / absent
# ---------------------------------------------------------------------------

def test_none_values_in_components_treated_as_zero():
    """Fields explicitly set to None should be treated like missing (0 offset)."""
    result = _calculate_due_date_from_components(
        {"relative_days": None, "relative_hours": None, "set_hour": 14, "set_minute": 0},
        MOSCOW_TZ,
    )
    assert result is not None
    result_moscow = result.astimezone(MOSCOW_TZ)
    assert result_moscow.hour == 14
    assert result_moscow.minute == 0
