"""Skip-LLM heuristics — §6.7.1 PRODUCT_PLAN.md.

«Регекс + словарь триггеров определяют kind для текстов < 5 слов без дат/цифр
(купить молоко, позвонить маме). Покрывает 20-30% моментов.»

Задача: дёшево угадать `kind` и построить минимальный `facets` + `title` для
коротких очевидных случаев. Если эвристика не уверена — возвращаем None,
вызывающий код идёт в LLM.

Важно: False positive (неверно угадать) хуже, чем False negative (пропустить).
Поэтому пороги строгие.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

# Жёсткие триггеры kind'ов по глаголу/ключевому слову.
# Ключ — подстрока начала нормализованного текста; значение — kind.
_SHOPPING_TRIGGERS = (
    "купить ", "купи ", "купим ", "заказать ", "заказ ",
)
_TASK_TRIGGERS = (
    "позвонить ", "позвони ", "написать ", "отправить ", "сделать ",
    "забрать ", "встретить ", "встретиться ", "заехать ", "зайти ",
    "проверить ", "напомни ", "напомнить ",
)
_THOUGHT_TRIGGERS = (
    "подумал", "подумалось", "кажется", "интересно",
)

# Паттерны, по которым мы ТОЧНО НЕ используем skip-LLM (§6.7.1: без цифр/дат).
# Даты, время, числительные на русском, @/#-метки, очевидные повторы.
_HAS_DIGITS = re.compile(r"\d")
_HAS_DATE_WORDS = re.compile(
    r"\b(сегодня|завтра|послезавтра|вчера|ночью|утром|днём|днем|вечером|"
    r"понедельник|вторник|сред[ау]|четверг|пятниц[ау]|суббот[ау]|воскресень[ея]|"
    r"в\s+\d+|через\s+|каждый|каждую|каждое|ежедневно|еженедельно)\b",
    flags=re.IGNORECASE,
)
_HAS_CURRENCY = re.compile(r"[₽$€]|\bруб(лей|ля)?\b", flags=re.IGNORECASE)

MAX_WORDS_FOR_TRIVIAL = 5
MAX_CHARS_FOR_TRIVIAL = 60


@dataclass(slots=True)
class TrivialResult:
    """Результат эвристики, если текст распознан как тривиальный.

    Совместим с форматом, который LLM вернул бы через extract_facets — чтобы
    дальнейший pipeline был одинаковый.
    """

    title: str
    kind: str                                # 'task' | 'shopping' | 'thought' | 'note'
    facets: dict[str, Any] = field(default_factory=dict)


def classify_trivial_text(raw_text: str) -> Optional[TrivialResult]:
    """Вернуть ``TrivialResult`` или None, если пропускать нельзя."""
    text = raw_text.strip()
    if not text:
        return None
    if len(text) > MAX_CHARS_FOR_TRIVIAL:
        return None

    words = text.split()
    if len(words) > MAX_WORDS_FOR_TRIVIAL or len(words) == 0:
        return None

    lower = text.lower()

    # Отсеиваем всё, где есть время/дата/деньги — это LLM.
    if _HAS_DIGITS.search(text):
        return None
    if _HAS_DATE_WORDS.search(lower):
        return None
    if _HAS_CURRENCY.search(lower):
        return None

    # Shopping.
    for trigger in _SHOPPING_TRIGGERS:
        if lower.startswith(trigger):
            item_text = text[len(trigger):].strip().rstrip(".")
            return TrivialResult(
                title=_capitalize_first(text.rstrip(".")),
                kind="shopping",
                facets={
                    "kind": "shopping",
                    "shopping_items": [
                        {"text": item_text, "qty": 1, "unit": "", "checked": False}
                    ],
                    "topics": ["покупки"],
                },
            )

    # Task.
    for trigger in _TASK_TRIGGERS:
        if lower.startswith(trigger):
            return TrivialResult(
                title=_capitalize_first(text.rstrip(".")),
                kind="task",
                facets={"kind": "task", "topics": []},
            )

    # Thought.
    for trigger in _THOUGHT_TRIGGERS:
        if lower.startswith(trigger):
            return TrivialResult(
                title=_capitalize_first(text.rstrip(".")),
                kind="thought",
                facets={"kind": "thought", "topics": []},
            )

    return None


def _capitalize_first(s: str) -> str:
    """Без полного Title Case — только первая буква, чтобы не ломать имена."""
    if not s:
        return s
    return s[0].upper() + s[1:]
