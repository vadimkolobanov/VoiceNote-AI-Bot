import pytest

from src.services.llm import UserIntent


# --- Direct enum values ---

def test_direct_value_create_note():
    assert UserIntent("создание_заметки") is UserIntent.CREATE_NOTE


def test_direct_value_shopping_list():
    assert UserIntent("список_покупок") is UserIntent.CREATE_SHOPPING_LIST


def test_direct_value_reminder():
    assert UserIntent("напоминание") is UserIntent.CREATE_REMINDER


def test_direct_value_unknown():
    assert UserIntent("неизвестно") is UserIntent.UNKNOWN


# --- Fuzzy matching via _missing_ ---

def test_fuzzy_note_partial():
    assert UserIntent("заметка") is UserIntent.CREATE_NOTE


def test_fuzzy_note_with_prefix():
    assert UserIntent("новая_заметка") is UserIntent.CREATE_NOTE


def test_fuzzy_shopping_partial():
    assert UserIntent("покупки") is UserIntent.CREATE_SHOPPING_LIST


def test_fuzzy_reminder_plural():
    assert UserIntent("напоминания") is UserIntent.CREATE_REMINDER


# --- Unknown value that doesn't match any pattern raises ValueError ---

def test_unknown_value_raises():
    with pytest.raises(ValueError):
        UserIntent("абракадабра")


def test_empty_string_raises():
    with pytest.raises(ValueError):
        UserIntent("")


# --- None and non-string values ---

def test_none_raises():
    with pytest.raises(ValueError):
        UserIntent(None)


def test_integer_raises():
    with pytest.raises(ValueError):
        UserIntent(12345)
