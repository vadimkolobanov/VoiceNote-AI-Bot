"""Unit-тесты для skip-LLM эвристики (PRODUCT_PLAN.md §6.7.1).

Эвристика должна:
- уверенно ловить короткие «купить X», «позвонить Y», «подумал Z»
- отказываться, когда есть числа/дата/время/деньги/больше 5 слов
- никогда не путать kind с неверным (false positive хуже FN)
"""
from __future__ import annotations

import pytest

from src.services.moments.heuristics import (
    MAX_WORDS_FOR_TRIVIAL,
    classify_trivial_text,
)


class TestShoppingTriggers:
    @pytest.mark.parametrize("text", [
        "купить молоко",
        "купи хлеб",
        "купим сыр",
        "заказать пиццу",
    ])
    def test_hit(self, text: str) -> None:
        r = classify_trivial_text(text)
        assert r is not None
        assert r.kind == "shopping"
        assert "shopping_items" in r.facets
        assert len(r.facets["shopping_items"]) == 1

    def test_item_text_extracted(self) -> None:
        r = classify_trivial_text("купить молоко")
        assert r is not None
        item = r.facets["shopping_items"][0]
        assert item["text"] == "молоко"
        assert item["qty"] == 1
        assert item["checked"] is False


class TestTaskTriggers:
    @pytest.mark.parametrize("text", [
        "позвонить маме",
        "позвони Ане",
        "написать Пете",
        "зайти к врачу",
        "забрать посылку",
    ])
    def test_hit(self, text: str) -> None:
        r = classify_trivial_text(text)
        assert r is not None
        assert r.kind == "task"


class TestThoughtTriggers:
    def test_hit(self) -> None:
        r = classify_trivial_text("подумал про переезд")
        assert r is not None
        assert r.kind == "thought"


class TestRefusals:
    @pytest.mark.parametrize("text", [
        "",                                      # пусто
        "   ",                                   # пробелы
        "купить молоко завтра",                  # дата в тексте
        "позвонить маме в 15",                   # время
        "купить молоко 2 литра",                 # цифры
        "заплатить 500 рублей за интернет",      # деньги
        "купить молоко хлеб яйца сыр и мыло",    # > 5 слов
        "просто мысль без триггера",             # нет триггера
    ])
    def test_miss(self, text: str) -> None:
        r = classify_trivial_text(text)
        assert r is None, f"heuristic wrongly matched: {text}"

    def test_long_text_rejected(self) -> None:
        """MAX_WORDS_FOR_TRIVIAL + 1 — уже LLM."""
        text = "купить " + " ".join(f"w{i}" for i in range(MAX_WORDS_FOR_TRIVIAL))
        assert classify_trivial_text(text) is None

    def test_unknown_trigger_verb(self) -> None:
        """Глагол, которого нет в словаре — не трогаем."""
        assert classify_trivial_text("спеть песню") is None

    def test_uppercase_ok(self) -> None:
        """Триггер case-insensitive."""
        r = classify_trivial_text("Купить молоко")
        assert r is not None
        assert r.kind == "shopping"
