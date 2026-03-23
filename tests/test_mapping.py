"""Тесты модуля маппинга токенов."""

from __future__ import annotations

from legaldesk.anonymizer.mapping import TokenMapping


def test_add_and_restore() -> None:
    """Добавленный токен восстанавливается обратно."""
    m = TokenMapping()
    token = m.add("Иванов", "ФИО")
    assert token == "[ФИО_1]"
    assert m.restore(f"Заявитель {token}") == "Заявитель Иванов"


def test_duplicate_original_returns_same_token() -> None:
    """Повторное добавление того же значения возвращает тот же токен."""
    m = TokenMapping()
    t1 = m.add("Иванов", "ФИО")
    t2 = m.add("Иванов", "ФИО")
    assert t1 == t2


def test_entries_returns_copy() -> None:
    """Свойство entries возвращает копию маппинга."""
    m = TokenMapping()
    m.add("123", "ИНН")
    entries = m.entries
    entries["другое"] = "значение"
    assert "другое" not in m.entries
