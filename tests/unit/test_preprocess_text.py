import pytest

from src.bot.modules.notes.services import _preprocess_text


# ---------------------------------------------------------------------------
# Basic typo corrections
# ---------------------------------------------------------------------------

def test_napomni_typo_corrected():
    """'напомин' should be corrected to 'напомни'."""
    assert _preprocess_text("напомин мне позвонить") == "напомни мне позвонить"


def test_two_typos_corrected():
    """Two different typos in one text should both be corrected."""
    assert _preprocess_text("напомнить купит молоко") == "напомни купить молоко"


def test_kupiy_typo_corrected():
    """'купиь' should be corrected to 'купить'."""
    assert _preprocess_text("купиь хлеб") == "купить хлеб"


def test_napomniiy_typo_corrected():
    """'напомниь' should be corrected to 'напомни'."""
    assert _preprocess_text("напомниь о встрече") == "напомни о встрече"


# ---------------------------------------------------------------------------
# Case insensitivity
# ---------------------------------------------------------------------------

def test_case_insensitive_correction():
    """Correction should work regardless of letter case (re.IGNORECASE)."""
    result = _preprocess_text("Напомин мне")
    assert result.lower() == "напомни мне"


def test_uppercase_typo_corrected():
    """Fully uppercase typo should also be corrected."""
    result = _preprocess_text("НАПОМИН мне")
    # The replacement is lowercase 'напомни' because that is the dict value
    assert "напомни" in result.lower()


# ---------------------------------------------------------------------------
# No changes when no typo
# ---------------------------------------------------------------------------

def test_no_typo_text_unchanged():
    """Text without any typos should remain unchanged."""
    text = "привет как дела"
    assert _preprocess_text(text) == text


def test_empty_string_unchanged():
    """Empty string should return empty string."""
    assert _preprocess_text("") == ""


# ---------------------------------------------------------------------------
# Word boundary check (\b)
# ---------------------------------------------------------------------------

def test_partial_word_not_replaced():
    r"""'напоминалка' should NOT be corrected: \b prevents partial match."""
    assert _preprocess_text("напоминалка") == "напоминалка"


# ---------------------------------------------------------------------------
# Full correct word is not a typo key
# ---------------------------------------------------------------------------

def test_correct_word_kupit_not_replaced():
    """'купить' (correct form) is not in TYPO_CORRECTIONS keys, so stays."""
    assert _preprocess_text("я хочу купить молоко") == "я хочу купить молоко"
