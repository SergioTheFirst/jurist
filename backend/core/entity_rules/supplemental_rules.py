"""Supplement helpers that add missed entities without using external LLMs."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Callable, Iterable
from uuid import uuid4

from backend.core.entity_rules.common import clean_entity_text, normalize_entity_text, overlaps_any, prefer_best
from backend.core.entity_rules.models import EntitySpan, RuleDecision


Validator = Callable[[str, EntitySpan], RuleDecision]
Mutator = Callable[[EntitySpan], EntitySpan]


def collect_supplement_spans(
    *,
    text: str,
    occupied: Iterable[tuple[int, int]],
    placeholder: str,
    entity_type: str,
    source: str,
    matches: Iterable[tuple[int, int, str, float]],
    validator: Validator,
    mutator: Mutator | None = None,
) -> list[EntitySpan]:
    """Build accepted supplement candidates from regex/rule matches."""

    supplemented: list[EntitySpan] = []
    current_occupied = list(occupied)
    for start, end, original, score in matches:
        if overlaps_any(start, end, current_occupied):
            continue
        candidate = EntitySpan(
            id=str(uuid4()),
            original=original,
            placeholder=placeholder,
            entity_type=entity_type,
            start=start,
            end=end,
            source=source,
            confidence=score,
        )
        decision = validator(text, candidate)
        if not decision.accepted:
            continue
        accepted = replace(candidate, confidence=max(candidate.confidence, decision.score))
        if mutator is not None:
            accepted = mutator(accepted)
        supplemented.append(accepted)
        current_occupied.append((accepted.start, accepted.end))
    return prefer_best(supplemented)


def iter_person_alias_matches(
    *,
    text: str,
    canonical_key: str,
    surname: str,
    initials: tuple[str, ...],
    prefixes: Iterable[str],
    context_check: Callable[[int, int], bool],
) -> list[tuple[int, int, str, float]]:
    """Yield aliases that should reuse an already-known person placeholder."""

    matches: list[tuple[int, int, str, float]] = []
    surname_pattern = re.escape(surname)
    initials_pattern = r"\s*".join(re.escape(item) for item in initials)

    if initials:
        for pattern in (
            re.compile(fr"\b{surname_pattern}\s+{initials_pattern}(?=\s|$|[,;:])"),
            re.compile(fr"\b{initials_pattern}\s*{surname_pattern}\b"),
        ):
            for match in pattern.finditer(text):
                alias = clean_entity_text(match.group(0))
                if alias and normalize_entity_text(alias) != canonical_key:
                    matches.append((match.start(), match.end(), alias, 0.9))

    prefix_group = "|".join(re.escape(item) for item in prefixes)
    prefix_pattern = re.compile(fr"\b(?:{prefix_group})\.?\s+({surname_pattern})\b", re.IGNORECASE)
    for match in prefix_pattern.finditer(text):
        alias = clean_entity_text(match.group(1))
        if alias and normalize_entity_text(alias) != canonical_key:
            matches.append((match.start(1), match.end(1), alias, 0.78))

    bare_surname_pattern = re.compile(fr"\b{surname_pattern}\b")
    for match in bare_surname_pattern.finditer(text):
        alias = clean_entity_text(match.group(0))
        if not alias or normalize_entity_text(alias) == canonical_key:
            continue
        if not context_check(match.start(), match.end()):
            continue
        matches.append((match.start(), match.end(), alias, 0.76))

    return matches
