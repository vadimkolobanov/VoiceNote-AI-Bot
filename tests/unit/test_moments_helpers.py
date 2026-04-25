"""Unit-тесты для helper-функций сервиса (PRODUCT_PLAN.md §6.2 v2).

Покрывают баги, которые поймал юзер 2026-04-25:
1. `_normalize_midnight_default` — 00:00 поднимается до 09:00 локально, если
   в тексте нет «полночь/ночью»
2. `_local_tomorrow_at` — корректное «завтра 09:00» в любой TZ
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from src.services.moments.service import (
    DEFAULT_HOUR_LOCAL,
    _local_tomorrow_at,
    _normalize_midnight_default,
)


class TestNormalizeMidnight:
    def test_midnight_local_lifts_to_default_hour(self) -> None:
        """Завтра 00:00 МСК → завтра 09:00 МСК."""
        msk = ZoneInfo("Europe/Moscow")
        midnight_local = datetime(2026, 4, 26, 0, 0, tzinfo=msk)
        midnight_utc = midnight_local.astimezone(timezone.utc)

        out = _normalize_midnight_default(midnight_utc, "Europe/Moscow", "купить подарок Диане")

        out_local = out.astimezone(msk)
        assert out_local.hour == DEFAULT_HOUR_LOCAL
        assert out_local.minute == 0
        assert out_local.year == 2026 and out_local.month == 4 and out_local.day == 26

    def test_explicit_hour_kept(self) -> None:
        """15:30 не трогаем."""
        msk = ZoneInfo("Europe/Moscow")
        afternoon = datetime(2026, 4, 26, 15, 30, tzinfo=msk).astimezone(timezone.utc)

        out = _normalize_midnight_default(afternoon, "Europe/Moscow", "созвон в 15:30")

        assert out == afternoon

    def test_explicit_midnight_word_kept(self) -> None:
        """«в полночь» → 00:00 НЕ заменяется."""
        msk = ZoneInfo("Europe/Moscow")
        midnight = datetime(2026, 4, 26, 0, 0, tzinfo=msk).astimezone(timezone.utc)

        out = _normalize_midnight_default(midnight, "Europe/Moscow", "встретимся в полночь")

        assert out == midnight

    def test_explicit_night_word_kept(self) -> None:
        """«ночью» — пользователь сам сказал, не трогаем."""
        msk = ZoneInfo("Europe/Moscow")
        midnight = datetime(2026, 4, 26, 0, 0, tzinfo=msk).astimezone(timezone.utc)

        out = _normalize_midnight_default(midnight, "Europe/Moscow", "выехать ночью")

        assert out == midnight

    def test_none_passes_through(self) -> None:
        assert _normalize_midnight_default(None, "Europe/Moscow", "что-то") is None

    def test_unknown_timezone_falls_back_to_moscow(self) -> None:
        """Кривой timezone не валит код, fallback на Europe/Moscow."""
        msk = ZoneInfo("Europe/Moscow")
        midnight = datetime(2026, 4, 26, 0, 0, tzinfo=msk).astimezone(timezone.utc)

        out = _normalize_midnight_default(midnight, "Mars/Olympus", "что-то завтра")

        out_local = out.astimezone(msk)
        assert out_local.hour == DEFAULT_HOUR_LOCAL


class TestLocalTomorrowAt:
    def test_returns_tomorrow_local_at_hour(self) -> None:
        out = _local_tomorrow_at("Europe/Moscow", hour=9)
        msk = ZoneInfo("Europe/Moscow")
        now_local = datetime.now(msk)
        # Просто проверяем что это завтра по календарю и нужный час.
        assert out.tzinfo is not None
        assert out.hour == 9
        assert out.minute == 0
        assert (out.date() - now_local.date()).days == 1

    def test_unknown_tz_falls_back(self) -> None:
        out = _local_tomorrow_at("Bogus/TZ", hour=9)
        assert out.hour == 9
