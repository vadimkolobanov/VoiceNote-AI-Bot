import pytest
from datetime import date

from src.services.scheduler import get_age_string


TODAY = date(2025, 6, 15)


@pytest.mark.parametrize(
    "age, expected",
    [
        # --- "год" (1, 21, 31, 101 -- ends in 1 but NOT 11) ---
        (1, "(1 год)"),
        (21, "(21 год)"),
        (31, "(31 год)"),
        (101, "(101 год)"),

        # --- "года" (2-4, 22-24, 32-34, 42 -- ends in 2-4 but NOT 12-14) ---
        (2, "(2 года)"),
        (3, "(3 года)"),
        (4, "(4 года)"),
        (22, "(22 года)"),
        (42, "(42 года)"),

        # --- "лет" (5-20, 25-30, 100, 111 -- everything else) ---
        (5, "(5 лет)"),
        (10, "(10 лет)"),
        (11, "(11 лет)"),
        (12, "(12 лет)"),
        (13, "(13 лет)"),
        (14, "(14 лет)"),
        (25, "(25 лет)"),
        (100, "(100 лет)"),
        (111, "(111 лет)"),

        # --- Edge cases ---
        (0, "(до года)"),
    ],
    ids=[
        "age_1_god",
        "age_21_god",
        "age_31_god",
        "age_101_god",
        "age_2_goda",
        "age_3_goda",
        "age_4_goda",
        "age_22_goda",
        "age_42_goda",
        "age_5_let",
        "age_10_let",
        "age_11_let_teen",
        "age_12_let_teen",
        "age_13_let_teen",
        "age_14_let_teen",
        "age_25_let",
        "age_100_let",
        "age_111_let_teen_hundred",
        "age_0_baby",
    ],
)
def test_get_age_string(age: int, expected: str):
    year = TODAY.year - age
    assert get_age_string(year, TODAY) == expected


def test_negative_age_returns_empty_string():
    """Birth year in the future should return an empty string."""
    future_year = TODAY.year + 1
    assert get_age_string(future_year, TODAY) == ""
