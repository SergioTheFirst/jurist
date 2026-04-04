"""Regex-based expanders for person and organization candidate spans."""

from __future__ import annotations

import re

from backend.core.entity_rules.common import clean_entity_text
from backend.core.entity_rules.context_rules import ORG_LONG_FORMS, ORG_SHORT_FORMS


NAME_WORD = r"(?:[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?|[А-ЯЁ]{2,40})"
INITIALS = r"(?:[А-ЯЁ]\.\s?[А-ЯЁ]\.)"
QUOTED_NAME = r"(?:«[^»\n]{2,80}»|\"[^\"]{2,80}\")"
NAME_SEQUENCE = r"(?:[А-ЯЁA-Z][А-Яа-яЁёA-Za-z0-9-]{1,40})(?:\s+[А-ЯЁA-Z][А-Яа-яЁёA-Za-z0-9-]{1,40}){0,5}"
LONG_FORM_GROUP = "|".join(re.escape(item) for item in ORG_LONG_FORMS)
SHORT_FORM_GROUP = "|".join(re.escape(item) for item in ORG_SHORT_FORMS)


PERSON_PATTERNS: tuple[tuple[re.Pattern[str], float], ...] = (
    (re.compile(fr"\b{NAME_WORD}\s+{NAME_WORD}\s+{NAME_WORD}\b"), 0.96),
    (re.compile(fr"\b{NAME_WORD}\s+{INITIALS}(?=\s|$|[,;:])"), 0.9),
    (re.compile(fr"\b{INITIALS}\s*{NAME_WORD}\b"), 0.9),
    (re.compile(fr"\b{NAME_WORD}\s+{NAME_WORD}\b"), 0.8),
)

ORG_PATTERNS: tuple[tuple[re.Pattern[str], float], ...] = (
    (
        re.compile(
            fr"\b(?:{LONG_FORM_GROUP})\s+(?:{QUOTED_NAME}|{NAME_SEQUENCE})",
            re.IGNORECASE,
        ),
        0.96,
    ),
    (
        re.compile(
            fr"\b(?:{SHORT_FORM_GROUP})\s+(?:{QUOTED_NAME}|{NAME_SEQUENCE})",
            re.IGNORECASE,
        ),
        0.92,
    ),
    (
        re.compile(
            r"\b(?:Министерство|Департамент|Управление|Служба|Администрация|Комитет|Инспекция|Фонд|Банк)\s+"
            r"[А-ЯЁA-Z][^,\n;:.]{2,80}",
            re.IGNORECASE,
        ),
        0.82,
    ),
)


def iter_person_matches(text: str) -> list[tuple[int, int, str, float]]:
    """Return person-like matches used for expansion and supplementation."""

    matches: list[tuple[int, int, str, float]] = []
    for pattern, score in PERSON_PATTERNS:
        overlap_pattern = re.compile(f"(?=({pattern.pattern}))", pattern.flags)
        for match in overlap_pattern.finditer(text):
            candidate_text = clean_entity_text(match.group(1))
            if candidate_text:
                matches.append((match.start(1), match.end(1), candidate_text, score))
    return matches


def iter_org_matches(text: str) -> list[tuple[int, int, str, float]]:
    """Return organization-like matches used for expansion and supplementation."""

    matches: list[tuple[int, int, str, float]] = []
    for pattern, score in ORG_PATTERNS:
        for match in pattern.finditer(text):
            candidate_text = clean_entity_text(match.group(0))
            if candidate_text:
                matches.append((match.start(), match.end(), candidate_text, score))
    return matches
