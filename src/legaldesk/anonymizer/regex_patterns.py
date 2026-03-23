"""Regex-паттерны для обнаружения ПДн (ИНН, СНИЛС, телефон и т.д.)."""

from __future__ import annotations

import re

# ИНН физлица (12 цифр) или юрлица (10 цифр)
INN_PATTERN: re.Pattern[str] = re.compile(r"\b\d{10}(?:\d{2})?\b")

# СНИЛС: 000-000-000 00
SNILS_PATTERN: re.Pattern[str] = re.compile(r"\b\d{3}-\d{3}-\d{3}\s?\d{2}\b")

# Телефон: +7 (000) 000-00-00 и вариации
PHONE_PATTERN: re.Pattern[str] = re.compile(
    r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b"
)

ALL_PATTERNS: dict[str, re.Pattern[str]] = {
    "ИНН": INN_PATTERN,
    "СНИЛС": SNILS_PATTERN,
    "ТЕЛЕФОН": PHONE_PATTERN,
}
