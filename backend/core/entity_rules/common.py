"""Common helpers shared by the entity rule engines."""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
import re
from typing import Iterable, Iterator

from pymorphy2 import MorphAnalyzer

from backend.core.entity_rules.models import EntitySpan


TRIM_CHARS = " \t\r\n,;:()[]{}<>«»\"'"
CONTEXT_WINDOW = 48

INITIALS_RE = re.compile(r"^[А-ЯЁ]\.(?:\s?[А-ЯЁ]\.)?$", re.IGNORECASE)
NAME_TOKEN_RE = re.compile(r"[А-ЯЁA-Z][А-Яа-яЁёA-Za-z-]{1,40}|[А-ЯЁ]\.|[A-Z]\.")
WORD_TOKEN_RE = re.compile(r"[А-ЯЁA-Zа-яёa-z][А-Яа-яЁёA-Za-z-]{0,40}")
CYRILLIC_WORD_RE = re.compile(r"[А-ЯЁA-Z][А-Яа-яЁёA-Za-z-]{1,40}")
ORG_CANONICAL_PREFIXES = {
    "общества с ограниченной ответственностью": "общество с ограниченной ответственностью",
    "акционерного общества": "акционерное общество",
    "публичного акционерного общества": "публичное акционерное общество",
    "закрытого акционерного общества": "закрытое акционерное общество",
    "открытого акционерного общества": "открытое акционерное общество",
}

_morph = MorphAnalyzer()


def collapse_spaces(text: str) -> str:
    """Collapse repeated internal whitespace into single spaces."""

    return re.sub(r"\s+", " ", text or "").strip()


def clean_entity_text(text: str) -> str:
    """Trim punctuation around an extracted entity span."""

    return collapse_spaces((text or "").strip(TRIM_CHARS))


def normalize_entity_text(text: str) -> str:
    """Produce a stable normalized key for dictionaries and comparisons."""

    return collapse_spaces(text).casefold()


@lru_cache(maxsize=32768)
def lemmatize_word(token: str) -> str:
    """Return a lowercase lemma for a Cyrillic token."""

    normalized = normalize_entity_text(token)
    if not normalized:
        return ""
    if "." in normalized or normalized.isupper():
        return normalized
    parsed = _morph.parse(normalized)
    return parsed[0].normal_form if parsed else normalized


def extract_word_tokens(text: str) -> list[str]:
    """Return capitalized and lowercase word-like tokens from an entity string."""

    return [match.group(0) for match in WORD_TOKEN_RE.finditer(clean_entity_text(text))]


def lemmatize_text_tokens(text: str) -> tuple[str, ...]:
    """Return lemmas for the word tokens found in the text."""

    lemmas = [lemmatize_word(token) for token in extract_word_tokens(text)]
    return tuple(lemma for lemma in lemmas if lemma)


def contains_any_lemma(text: str, lemmas: set[str]) -> bool:
    """Return True when any token lemma from the text is present in a lemma set."""

    return any(lemma in lemmas for lemma in lemmatize_text_tokens(text))


def lemma_overlap_count(text: str, lemmas: set[str]) -> int:
    """Return how many token lemmas from the text appear in the provided set."""

    return sum(1 for lemma in lemmatize_text_tokens(text) if lemma in lemmas)


def is_composed_only_of_lemmas(text: str, lemmas: set[str], *, min_tokens: int = 1) -> bool:
    """Return True when all token lemmas belong to a known generic/role dictionary."""

    token_lemmas = lemmatize_text_tokens(text)
    return len(token_lemmas) >= min_tokens and all(lemma in lemmas for lemma in token_lemmas)


def canonicalize_org_name(text: str) -> str:
    """Normalize common legal-form inflections so one company keeps one identity."""

    normalized = normalize_entity_text(clean_entity_text(text))
    for source, target in ORG_CANONICAL_PREFIXES.items():
        if normalized.startswith(source):
            return normalized.replace(source, target, 1)
    return normalized


def spans_overlap(start: int, end: int, other_start: int, other_end: int) -> bool:
    """Return True when two spans overlap by at least one character."""

    return start < other_end and end > other_start


def overlaps_any(start: int, end: int, occupied: Iterable[tuple[int, int]]) -> bool:
    """Return True when a span conflicts with any occupied range."""

    return any(spans_overlap(start, end, other_start, other_end) for other_start, other_end in occupied)


def extract_window(text: str, start: int, end: int, window: int = CONTEXT_WINDOW) -> str:
    """Return nearby lowercase context around a candidate."""

    left = max(0, start - window)
    right = min(len(text), end + window)
    return text[left:right].casefold()


def tokenize_name_fragments(text: str) -> list[str]:
    """Split a name-like phrase into word and initials fragments."""

    return [match.group(0).strip() for match in NAME_TOKEN_RE.finditer(text)]


def is_initials(token: str) -> bool:
    """Return True when the fragment is an initials token."""

    return bool(INITIALS_RE.fullmatch(token.strip()))


def is_name_like_token(token: str) -> bool:
    """Return True for tokens that structurally look like person-name parts."""

    value = token.strip()
    if not value:
        return False
    if is_initials(value):
        return True
    if len(value) < 2:
        return False
    if not re.fullmatch(r"[А-ЯЁA-Z][А-Яа-яЁёA-Za-z-]+", value):
        return False
    if value.isupper():
        return len(value) >= 4
    return True


def with_updated_span(candidate: EntitySpan, start: int, end: int, text: str, score: float) -> EntitySpan:
    """Return a candidate with updated coordinates and normalized text."""

    return replace(
        candidate,
        original=clean_entity_text(text[start:end]),
        start=start,
        end=end,
        confidence=max(candidate.confidence, score),
    )


def prefer_best(candidates: Iterable[EntitySpan]) -> list[EntitySpan]:
    """Drop duplicate spans while keeping the strongest candidate."""

    best_by_key: dict[tuple[str, int, int, str], EntitySpan] = {}
    for candidate in candidates:
        key = (
            candidate.entity_type,
            candidate.start,
            candidate.end,
            normalize_entity_text(candidate.original),
        )
        incumbent = best_by_key.get(key)
        if incumbent is None or (
            candidate.coverage,
            candidate.source == "regex",
            candidate.confidence,
        ) > (
            incumbent.coverage,
            incumbent.source == "regex",
            incumbent.confidence,
        ):
            best_by_key[key] = candidate
    return sorted(best_by_key.values(), key=lambda item: (item.start, item.end, item.entity_type))


def iter_capitalized_tokens(text: str) -> Iterator[re.Match[str]]:
    """Yield capitalized word matches from the original text."""

    yield from CYRILLIC_WORD_RE.finditer(text)
