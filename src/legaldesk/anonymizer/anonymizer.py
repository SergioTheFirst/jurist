"""Основная логика анонимизации: LLM + regex → замены."""

from __future__ import annotations

from legaldesk.anonymizer.mapping import TokenMapping
from legaldesk.anonymizer.regex_patterns import ALL_PATTERNS


def anonymize_with_regex(text: str) -> tuple[str, TokenMapping]:
    """Анонимизировать текст с помощью regex-паттернов.

    Возвращает очищенный текст и маппинг замен.
    """
    mapping = TokenMapping()
    result = text
    for category, pattern in ALL_PATTERNS.items():
        for match in pattern.finditer(text):
            original = match.group()
            token = mapping.add(original, category)
            result = result.replace(original, token)
    return result, mapping
