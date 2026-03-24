"""Тесты regex-паттернов для обнаружения ПДн в документах по ДТП."""

from __future__ import annotations

from legaldesk.anonymizer.regex_patterns import (
    BANK_ACCOUNT_PATTERN,
    BANK_CARD_PATTERN,
    BIK_PATTERN,
    EMAIL_PATTERN,
    INN_PATTERN,
    INSURANCE_POLICY_PATTERN,
    LICENSE_PLATE_PATTERN,
    PASSPORT_PATTERN,
    PHONE_PATTERN,
    SNILS_PATTERN,
    VEHICLE_REGISTRATION_PATTERN,
    VIN_PATTERN,
)

# --- ИНН ---

def test_inn_10_digits() -> None:
    """ИНН юрлица — 10 цифр."""
    assert INN_PATTERN.search("ИНН: 1234567890") is not None


def test_inn_12_digits() -> None:
    """ИНН физлица — 12 цифр."""
    assert INN_PATTERN.search("ИНН: 123456789012") is not None


def test_inn_no_match_9_digits() -> None:
    """9 цифр — не ИНН."""
    assert INN_PATTERN.search("код 123456789 конец") is None


# --- СНИЛС ---

def test_snils_with_space() -> None:
    """СНИЛС с пробелом перед контрольной суммой."""
    assert SNILS_PATTERN.search("123-456-789 00") is not None


def test_snils_without_space() -> None:
    """СНИЛС без пробела перед контрольной суммой."""
    assert SNILS_PATTERN.search("123-456-78900") is not None


# --- ТЕЛЕФОН ---

def test_phone_plus7() -> None:
    """Телефон в формате +7 (XXX) XXX-XX-XX."""
    assert PHONE_PATTERN.search("+7 (999) 123-45-67") is not None


def test_phone_8() -> None:
    """Телефон, начинающийся с 8."""
    assert PHONE_PATTERN.search("8 999 123 45 67") is not None


# --- ПАСПОРТ ---

def test_passport_with_spaces() -> None:
    """Паспорт с пробелами: XX XX XXXXXX."""
    assert PASSPORT_PATTERN.search("45 06 123456") is not None


def test_passport_no_spaces() -> None:
    """Паспорт без пробелов: XXXXXXXXXX."""
    assert PASSPORT_PATTERN.search("4506123456") is not None


def test_passport_no_match_short() -> None:
    """8 цифр — не паспорт."""
    assert PASSPORT_PATTERN.search("код 12345678 конец") is None


# --- EMAIL ---

def test_email_simple() -> None:
    """Стандартный email."""
    assert EMAIL_PATTERN.search("user@example.com") is not None


def test_email_with_dots() -> None:
    """Email с точками и дефисами."""
    assert EMAIL_PATTERN.search("first.last@mail.ru") is not None


def test_email_no_match() -> None:
    """Строка без @ — не email."""
    assert EMAIL_PATTERN.search("example.com") is None


# --- РАСЧЁТНЫЙ СЧЁТ ---

def test_bank_account_20_digits() -> None:
    """Расчётный счёт — ровно 20 цифр."""
    assert BANK_ACCOUNT_PATTERN.search("40817810099910004312") is not None


def test_bank_account_no_match_19() -> None:
    """19 цифр — не расчётный счёт."""
    assert BANK_ACCOUNT_PATTERN.search("1234567890123456789") is None


# --- БАНКОВСКАЯ КАРТА ---

def test_bank_card_with_spaces() -> None:
    """Номер карты с пробелами."""
    assert BANK_CARD_PATTERN.search("4276 1234 5678 9012") is not None


def test_bank_card_with_dashes() -> None:
    """Номер карты с дефисами."""
    assert BANK_CARD_PATTERN.search("4276-1234-5678-9012") is not None


def test_bank_card_no_spaces() -> None:
    """Номер карты без разделителей."""
    assert BANK_CARD_PATTERN.search("4276123456789012") is not None


# --- БИК ---

def test_bik_standard() -> None:
    """БИК — 9 цифр, начинается с 0."""
    assert BIK_PATTERN.search("044525225") is not None


def test_bik_no_match_not_leading_zero() -> None:
    """9 цифр без ведущего нуля — не БИК."""
    assert BIK_PATTERN.search(" 144525225 ") is None


# --- ГОСНОМЕР ---

def test_license_plate_cyrillic() -> None:
    """Госномер с кириллицей."""
    assert LICENSE_PLATE_PATTERN.search("А123ВС777") is not None


def test_license_plate_3digit_region() -> None:
    """Госномер с трёхзначным кодом региона."""
    assert LICENSE_PLATE_PATTERN.search("В456НА199") is not None


# --- VIN ---

def test_vin_standard() -> None:
    """Стандартный VIN — 17 знаков."""
    assert VIN_PATTERN.search("1HGBH41JXMN109186") is not None


def test_vin_no_match_16() -> None:
    """16 знаков — не VIN."""
    assert VIN_PATTERN.search("1HGBH41JXMN10918") is None


# --- ПОЛИС ОСАГО ---

def test_insurance_policy() -> None:
    """Полис ОСАГО: ТТТ 1234567890."""
    assert INSURANCE_POLICY_PATTERN.search("ТТТ 1234567890") is not None


def test_insurance_policy_no_space() -> None:
    """Полис без пробела."""
    assert INSURANCE_POLICY_PATTERN.search("ХХХ1234567890") is not None


# --- СТС ---

def test_vehicle_registration_sts() -> None:
    """СТС: XX ЯЯ ХХХXХХ."""
    assert VEHICLE_REGISTRATION_PATTERN.search("77 МА 123456") is not None


def test_vehicle_registration_no_space() -> None:
    """СТС без пробелов."""
    assert VEHICLE_REGISTRATION_PATTERN.search("77МА123456") is not None
