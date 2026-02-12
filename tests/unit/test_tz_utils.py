import pytest
from datetime import datetime

import pytz

from src.services.tz_utils import (
    guess_timezone_from_language,
    format_datetime_for_user,
    format_rrule_for_user,
    get_day_of_week_str,
)


# ---------------------------------------------------------------------------
# guess_timezone_from_language
# ---------------------------------------------------------------------------

def test_guess_timezone_ru():
    assert guess_timezone_from_language("ru") == "Europe/Moscow"


def test_guess_timezone_uk():
    assert guess_timezone_from_language("uk") == "Europe/Kiev"


def test_guess_timezone_be():
    assert guess_timezone_from_language("be") == "Europe/Minsk"


def test_guess_timezone_kk():
    assert guess_timezone_from_language("kk") == "Asia/Almaty"


def test_guess_timezone_prefix_ru_RU():
    """Language code with region suffix like 'ru-RU' should resolve via prefix."""
    assert guess_timezone_from_language("ru-RU") == "Europe/Moscow"


def test_guess_timezone_none():
    assert guess_timezone_from_language(None) == "UTC"


def test_guess_timezone_unknown():
    assert guess_timezone_from_language("xx") == "UTC"


# ---------------------------------------------------------------------------
# format_datetime_for_user
# ---------------------------------------------------------------------------

def test_format_datetime_utc_to_moscow():
    """UTC 12:00 should become 15:00 MSK (UTC+3)."""
    dt_utc = datetime(2025, 6, 15, 12, 0, 0, tzinfo=pytz.utc)
    result = format_datetime_for_user(dt_utc, "Europe/Moscow")
    assert result is not None
    # The formatted time must contain 15:00 and the date
    assert "15:00" in result
    assert "15.06.2025" in result


def test_format_datetime_naive_assumed_utc():
    """Naive datetime (no tzinfo) should be treated as UTC."""
    dt_naive = datetime(2025, 1, 10, 6, 0, 0)
    result = format_datetime_for_user(dt_naive, "Europe/Moscow")
    assert result is not None
    # UTC 06:00 -> MSK 09:00
    assert "09:00" in result


def test_format_datetime_none_returns_none():
    assert format_datetime_for_user(None, "Europe/Moscow") is None


def test_format_datetime_invalid_tz_falls_back_to_utc():
    """Invalid timezone string should fall back to UTC."""
    dt_utc = datetime(2025, 3, 20, 8, 30, 0, tzinfo=pytz.utc)
    result = format_datetime_for_user(dt_utc, "Invalid/Timezone")
    assert result is not None
    # Should show the original UTC time since it falls back
    assert "08:30" in result
    assert "UTC" in result


# ---------------------------------------------------------------------------
# format_rrule_for_user
# ---------------------------------------------------------------------------

def test_format_rrule_daily():
    assert format_rrule_for_user("RRULE:FREQ=DAILY") == "Каждый день"


def test_format_rrule_weekly_with_byday():
    result = format_rrule_for_user("RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR")
    assert result == "По дням: пн, ср, пт"


def test_format_rrule_monthly_with_bymonthday():
    result = format_rrule_for_user("RRULE:FREQ=MONTHLY;BYMONTHDAY=25")
    assert "Каждый месяц" in result
    assert "25" in result


def test_format_rrule_empty():
    assert format_rrule_for_user("") == "Никогда"


def test_format_rrule_invalid():
    """Invalid RRULE string should be returned as-is."""
    invalid = "NOT_A_VALID_RRULE"
    assert format_rrule_for_user(invalid) == invalid


def test_format_rrule_weekly_with_interval():
    """WEEKLY + INTERVAL + BYDAY — функция возвращает 'По дням: вт' (interval не обрабатывается)."""
    result = format_rrule_for_user("RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=TU")
    assert "вт" in result


# ---------------------------------------------------------------------------
# get_day_of_week_str
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "date, expected",
    [
        (datetime(2025, 6, 2), "понедельник"),   # Monday
        (datetime(2025, 6, 3), "вторник"),        # Tuesday
        (datetime(2025, 6, 4), "среда"),           # Wednesday
        (datetime(2025, 6, 5), "четверг"),         # Thursday
        (datetime(2025, 6, 6), "пятница"),         # Friday
        (datetime(2025, 6, 7), "суббота"),         # Saturday
        (datetime(2025, 6, 8), "воскресенье"),     # Sunday
    ],
)
def test_get_day_of_week_str(date, expected):
    assert get_day_of_week_str(date) == expected
