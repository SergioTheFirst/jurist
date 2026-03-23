"""Тесты regex-паттернов для обнаружения ПДн."""

from __future__ import annotations

from legaldesk.anonymizer.regex_patterns import INN_PATTERN, PHONE_PATTERN, SNILS_PATTERN


def test_inn_10_digits() -> None:
    """ИНН юрлица — 10 цифр."""
    assert INN_PATTERN.search("ИНН: 1234567890") is not None


def test_inn_12_digits() -> None:
    """ИНН физлица — 12 цифр."""
    assert INN_PATTERN.search("ИНН: 123456789012") is not None


def test_snils_with_space() -> None:
    """СНИЛС с пробелом перед контрольной суммой."""
    assert SNILS_PATTERN.search("123-456-789 00") is not None


def test_phone_plus7() -> None:
    """Телефон в формате +7 (XXX) XXX-XX-XX."""
    assert PHONE_PATTERN.search("+7 (999) 123-45-67") is not None
