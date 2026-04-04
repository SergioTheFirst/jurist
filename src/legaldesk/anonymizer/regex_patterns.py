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

# Госномер: стандартный А123ВС77 / А123ВС777
LICENSE_PLATE_PATTERN: re.Pattern[str] = re.compile(
    r"\b[АВЕКМНОРСТУХABEKMHOPCTYX]\d{3}[АВЕКМНОРСТУХABEKMHOPCTYX]{2}\d{2,3}\b"
)

# Госномер прицепа: АА1234 77
TRAILER_PLATE_PATTERN: re.Pattern[str] = re.compile(
    r"\b[АВЕКМНОРСТУХABEKMHOPCTYX]{2}\d{4}\s?\d{2,3}\b"
)

# Госномер мотоцикла: 1234 АА 77
MOTORCYCLE_PLATE_PATTERN: re.Pattern[str] = re.compile(
    r"\b\d{4}\s?[АВЕКМНОРСТУХABEKMHOPCTYX]{2}\s?\d{2,3}\b"
)

# VIN: 17 символов из допустимого алфавита (без I, O, Q)
VIN_PATTERN: re.Pattern[str] = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")

# Полис ОСАГО/КАСКО: серия 3 буквы + 10 цифр
INSURANCE_POLICY_PATTERN: re.Pattern[str] = re.compile(r"\b[А-Я]{3}\s?\d{10}\b")

# СТС/ПТС: ХХ ЯЯ ХХХXХХ (2 цифры + 2 Кирилл. буквы + 6 цифр)
VEHICLE_REGISTRATION_PATTERN: re.Pattern[str] = re.compile(
    r"\b\d{2}\s?[А-Я]{2}\s?\d{6}\b"
)

# Дата: ДД.ММ.ГГГГ, ДД/ММ/ГГГГ, ДД-ММ-ГГГГ
DATE_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:0?[1-9]|[12]\d|3[01])[.\-/](?:0?[1-9]|1[0-2])[.\-/](?:19|20)\d{2}\b"
)

# Дата словесная: «12 января 2021 г.», «5 мая 2020 года»
DATE_VERBAL_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:0?[1-9]|[12]\d|3[01])\s+"
    r"(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)"
    r"\s+(?:19|20)\d{2}(?:\s+г(?:ода?|\.))?\b",
    re.IGNORECASE,
)

# Адрес: улица/проспект/переулок/дом/квартира (упрощённый паттерн)
ADDRESS_PATTERN: re.Pattern[str] = re.compile(
    r"(?:"
    r"(?:г\.|город|г)\s+[А-ЯЁ][а-яёА-ЯЁ\-]+|"
    r"(?:ул\.|улица|пр\.|просп\.|проспект|пер\.|переулок|бул\.|бульвар|пл\.|площадь|ш\.|шоссе|"
    r"пр-т|пр-кт)\s+[А-ЯЁ][а-яёА-ЯЁ0-9\s\-\.]+|"
    r"д\.\s?\d+[а-яА-Я]?(?:/\d+)?(?:\s*,\s*(?:кв\.|квартира|оф\.|офис|к\.)\s?\d+)?"
    r")",
    re.IGNORECASE,
)

# Номер дела: А00-0000/0000, 1-00/00, 00АП-0000/0000 и подобные
CASE_NUMBER_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:[А-Я]\d{2}-\d+/\d{4}|\d{1,2}-\d+/\d{2,4}|\d{2}[А-Я]{2}-\d+/\d{4})\b"
)

# Инициалы рядом с фамилией: Иванов И.И., И.И. Иванов
INITIALS_PATTERN: re.Pattern[str] = re.compile(
    r"\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.[А-ЯЁ]\."
    r"|\b[А-ЯЁ]\.[А-ЯЁ]\.\s+[А-ЯЁ][а-яё]+"
)

# Сопоставление EntityType → паттерн.
# Порядок важен: длинные/приоритетные шаблоны идут раньше коротких.
ALL_PATTERNS: dict[EntityType, re.Pattern[str]] = {
    EntityType.BANK_ACCOUNT: BANK_ACCOUNT_PATTERN,       # 20 цифр — до INN
    EntityType.BANK_CARD: BANK_CARD_PATTERN,
    EntityType.BIK: BIK_PATTERN,
    EntityType.VIN: VIN_PATTERN,
    EntityType.SNILS: SNILS_PATTERN,
    EntityType.INN: INN_PATTERN,
    EntityType.PHONE: PHONE_PATTERN,
    EntityType.PASSPORT: PASSPORT_PATTERN,
    EntityType.EMAIL: EMAIL_PATTERN,
    EntityType.LICENSE_PLATE: LICENSE_PLATE_PATTERN,
    EntityType.TRAILER_PLATE: TRAILER_PLATE_PATTERN,
    EntityType.MOTORCYCLE_PLATE: MOTORCYCLE_PLATE_PATTERN,
    EntityType.INSURANCE_POLICY: INSURANCE_POLICY_PATTERN,
    EntityType.VEHICLE_REGISTRATION: VEHICLE_REGISTRATION_PATTERN,
    EntityType.DATE_OF_BIRTH: DATE_PATTERN,               # будет уточнён контекстом
    EntityType.DATE: DATE_VERBAL_PATTERN,
    EntityType.ADDRESS: ADDRESS_PATTERN,
    EntityType.CASE_NUMBER: CASE_NUMBER_PATTERN,
    EntityType.PERSON: INITIALS_PATTERN,
}
