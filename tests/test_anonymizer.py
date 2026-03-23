"""Тесты модуля анонимизации."""

from __future__ import annotations

from legaldesk.anonymizer.anonymizer import anonymize_with_regex


def test_anonymize_inn_12() -> None:
    """ИНН физлица (12 цифр) заменяется токеном."""
    text = "ИНН клиента: 123456789012"
    result, mapping = anonymize_with_regex(text)
    assert "123456789012" not in result
    assert "[ИНН_" in result
    assert mapping.restore(result) == text


def test_anonymize_snils() -> None:
    """СНИЛС заменяется токеном."""
    text = "СНИЛС: 123-456-789 00"
    result, mapping = anonymize_with_regex(text)
    assert "123-456-789 00" not in result
    assert "[СНИЛС_" in result
    assert mapping.restore(result) == text


def test_anonymize_phone() -> None:
    """Телефонный номер заменяется токеном."""
    text = "Телефон: +7 (999) 123-45-67"
    result, mapping = anonymize_with_regex(text)
    assert "+7 (999) 123-45-67" not in result
    assert "[ТЕЛЕФОН_" in result
    assert mapping.restore(result) == text


def test_anonymize_no_pdn() -> None:
    """Текст без ПДн остаётся без изменений."""
    text = "Прошу разъяснить порядок обжалования."
    result, mapping = anonymize_with_regex(text)
    assert result == text
    assert mapping.entries == {}
