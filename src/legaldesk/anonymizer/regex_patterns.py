"""Regex-паттерны для обнаружения ПДн с фиксированным форматом."""

from __future__ import annotations

import re

from legaldesk.anonymizer.models import EntityType

# ИНН физлица (12 цифр) или юрлица (10 цифр)
INN_PATTERN: re.Pattern[str] = re.compile(r"\b\d{10}(?:\d{2})?\b")

# СНИЛС: 000-000-000 00
SNILS_PATTERN: re.Pattern[str] = re.compile(r"\b\d{3}-\d{3}-\d{3}\s?\d{2}\b")

# Телефон: +7 (000) 000-00-00 и вариации
PHONE_PATTERN: re.Pattern[str] = re.compile(
    r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b"
)

# Паспорт РФ: XX XX XXXXXX (серия + номер)
PASSPORT_PATTERN: re.Pattern[str] = re.compile(r"\b\d{2}\s?\d{2}\s?\d{6}\b")

# Email
EMAIL_PATTERN: re.Pattern[str] = re.compile(r"[\w.\-]+@[\w.\-]+\.\w{2,}")

# Расчётный счёт: ровно 20 цифр — проверяется ДО ИНН
BANK_ACCOUNT_PATTERN: re.Pattern[str] = re.compile(r"\b\d{20}\b")

# Номер банковской карты: 4×4 цифры с разделителями
BANK_CARD_PATTERN: re.Pattern[str] = re.compile(
    r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"
)

# БИК: 9 цифр, начинается с 0
BIK_PATTERN: re.Pattern[str] = re.compile(r"\b0\d{8}\b")

# Госномер: А123ВС777 — русские и латинские буквы из допустимого набора
LICENSE_PLATE_PATTERN: re.Pattern[str] = re.compile(
    r"\b[АВЕКМНОРСТУХABEKMHOPCTYX]\d{3}[АВЕКМНОРСТУХABEKMHOPCTYX]{2}\d{2,3}\b"
)

# VIN: 17 символов из допустимого алфавита (без I, O, Q)
VIN_PATTERN: re.Pattern[str] = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")

# Полис ОСАГО/КАСКО: серия 3 буквы + 10 цифр
INSURANCE_POLICY_PATTERN: re.Pattern[str] = re.compile(r"\b[А-Я]{3}\s?\d{10}\b")

# СТС: ХХ ЯЯ ХХХXХХ (2 цифры + 2 Кирилл. буквы + 6 цифр)
# Та же формула — у ПТС, поэтому в regex используем VEHICLE_REGISTRATION
VEHICLE_REGISTRATION_PATTERN: re.Pattern[str] = re.compile(
    r"\b\d{2}\s?[А-Я]{2}\s?\d{6}\b"
)

# Сопоставление EntityType → паттерн.
# Порядок важен для str.replace-логики: длинные шаблоны идут раньше коротких.
ALL_PATTERNS: dict[EntityType, re.Pattern[str]] = {
    EntityType.BANK_ACCOUNT: BANK_ACCOUNT_PATTERN,       # 20 цифр — до INN
    EntityType.BANK_CARD: BANK_CARD_PATTERN,
    EntityType.BIK: BIK_PATTERN,
    EntityType.VIN: VIN_PATTERN,
    EntityType.INN: INN_PATTERN,
    EntityType.SNILS: SNILS_PATTERN,
    EntityType.PHONE: PHONE_PATTERN,
    EntityType.PASSPORT: PASSPORT_PATTERN,
    EntityType.EMAIL: EMAIL_PATTERN,
    EntityType.LICENSE_PLATE: LICENSE_PLATE_PATTERN,
    EntityType.INSURANCE_POLICY: INSURANCE_POLICY_PATTERN,
    EntityType.VEHICLE_REGISTRATION: VEHICLE_REGISTRATION_PATTERN,
}
