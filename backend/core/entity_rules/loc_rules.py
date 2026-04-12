"""Rule engine that expands and validates address (LOC / АДРЕС) entities.

Mirrors `OrganizationRuleEngine`: given a raw Natasha LOC candidate (usually a
single token like "Москва"), walks rightward through adjacent address
primitives (постиндекс, регион, улица, дом, квартира) to reconstruct the full
address span. Also supplements the candidate set with regex matches Natasha
missed entirely.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable
from uuid import uuid4

from backend.core.entity_rules.address_patterns import (
    ADDRESS_EXPANSION_RE,
    CITY_STREET_RE,
    FULL_ADDRESS_RE,
    HOUSE_RE,
    POSTAL_CITY_RE,
    POSTAL_RE,
    PREFIXED_ADDRESS_RE,
    PREPOSITIONAL_STREET_RE,
    REGION_RE,
    STREET_RE,
)
from backend.core.entity_rules.common import (
    clean_entity_text,
    normalize_entity_text,
    prefer_best,
    with_updated_span,
)
from backend.core.entity_rules.context_rules import (
    ADDRESS_CONTEXT_WORDS,
    has_nearby_context,
)
from backend.core.entity_rules.models import EntitySpan, RuleDecision


_ACCEPT_THRESHOLD = 0.72
_REVIEW_THRESHOLD = 0.55
_MAX_SPAN_LEN = 220
_RIGHTWARD_GAP = 3
_LEFTWARD_GAP = 40

# Noisy LOC values that are never personal data
_LOC_REJECT_EXACT = frozenset({
    "рф",
    "россия",
    "российская федерация",
    "ссср",
})


def _score_decision(
    *,
    model_confidence: float,
    context_bonus: float,
    penalty: float,
    reason: str,
) -> RuleDecision:
    """Combine the usual (model + context − penalty) score into a decision."""

    score = max(0.0, min(1.0, model_confidence + context_bonus - penalty))
    if score >= _ACCEPT_THRESHOLD:
        verdict = "accept"
    elif score >= _REVIEW_THRESHOLD:
        verdict = "review"
    else:
        verdict = "reject"
    return RuleDecision(
        verdict=verdict,
        score=score,
        reason=reason,
        model_confidence=model_confidence,
        context_bonus=context_bonus,
        penalty=penalty,
    )


def _is_separator_only(segment: str) -> bool:
    """Return True when the gap between two spans contains only punctuation/ws."""

    return all(ch in " \t\r\n,;." for ch in segment)


def _blocks_expansion(segment: str) -> bool:
    """Return True when the gap contains a hard stop (paragraph break / sentence)."""

    if "\n\n" in segment:
        return True
    stripped = segment.rstrip()
    # Terminal punctuation followed by nothing or only whitespace – sentence end
    if stripped.endswith((".", "!", "?")) and stripped not in {".", "!", "?"}:
        return True
    return False


class LocationRuleEngine:
    """Expand Natasha LOC candidates into full address spans."""

    def __init__(self, placeholder: str) -> None:
        self._placeholder = placeholder

    def expand_candidate(self, text: str, candidate: EntitySpan) -> EntitySpan:
        """Extend the span through adjacent address components."""

        start, end = candidate.start, candidate.end

        # Rightward walk — grow end across adjacent components
        while True:
            if end - start >= _MAX_SPAN_LEN:
                break
            next_match = ADDRESS_EXPANSION_RE.search(text, end)
            if next_match is None:
                break
            gap = text[end:next_match.start()]
            if len(gap) > _RIGHTWARD_GAP * 4:
                # Too far — the next component belongs to a different address
                break
            if not _is_separator_only(gap):
                break
            if _blocks_expansion(gap):
                break
            end = next_match.end()

        # Leftward walk — POSTAL / REGION prefix
        left_window_start = max(0, start - _LEFTWARD_GAP)
        left_snippet = text[left_window_start:start]
        for pattern in (POSTAL_RE, REGION_RE):
            leftward = None
            for match in pattern.finditer(left_snippet):
                leftward = match  # keep the last one (closest to start)
            if leftward is None:
                continue
            gap = left_snippet[leftward.end():]
            if _is_separator_only(gap) and not _blocks_expansion(gap):
                new_start = left_window_start + leftward.start()
                if new_start < start:
                    start = new_start

        return with_updated_span(candidate, start, end, text, candidate.confidence)

    def validate_candidate(self, text: str, candidate: EntitySpan) -> RuleDecision:
        """Decide whether an address candidate is safe to anonymize."""

        original = clean_entity_text(candidate.original)
        if not original:
            return RuleDecision("reject", 0.0, "empty", penalty=1.0)

        normalized = normalize_entity_text(original)
        if normalized in _LOC_REJECT_EXACT:
            return RuleDecision("reject", 0.05, "generic_country", penalty=0.9)

        # Very short uppercase acronyms (e.g. "РТ", "КБР") are too ambiguous
        # unless accompanied by a strong address-context word.
        stripped = original.strip()
        if len(normalized) <= 3 and stripped.isupper():
            if not has_nearby_context(text, candidate.start, candidate.end, ADDRESS_CONTEXT_WORDS):
                return RuleDecision("reject", 0.1, "short_upper_acronym", penalty=0.85)

        model_confidence = max(candidate.confidence, 0.48)
        context_bonus = 0.0
        penalty = 0.0

        has_street = bool(STREET_RE.search(original))
        has_house = bool(HOUSE_RE.search(original))
        has_postal = bool(POSTAL_RE.search(original))

        # Strong structural signals → auto accept
        if has_street or has_house or has_postal:
            context_bonus += 0.24
            return _score_decision(
                model_confidence=model_confidence,
                context_bonus=context_bonus,
                penalty=penalty,
                reason="structural_address",
            )

        if has_nearby_context(text, candidate.start, candidate.end, ADDRESS_CONTEXT_WORDS):
            context_bonus += 0.18
            return _score_decision(
                model_confidence=model_confidence,
                context_bonus=context_bonus,
                penalty=penalty,
                reason="context_boost",
            )

        # Bare LOC candidate, no structural or contextual signal
        if candidate.source == "ner" and candidate.confidence >= 0.88:
            return _score_decision(
                model_confidence=model_confidence,
                context_bonus=0.0,
                penalty=0.05,
                reason="bare_loc_high_confidence",
            )

        return _score_decision(
            model_confidence=model_confidence,
            context_bonus=0.0,
            penalty=0.15,
            reason="ambiguous_loc",
        )

    def supplement_candidates(
        self, text: str, occupied: Iterable[tuple[int, int]]
    ) -> list[EntitySpan]:
        """Emit address candidates Natasha missed entirely (rural, no-name cities, POI)."""

        current_occupied = list(occupied)
        supplemented: list[EntitySpan] = []

        patterns: tuple[tuple[object, float], ...] = (
            (FULL_ADDRESS_RE, 0.9),
            (POSTAL_CITY_RE, 0.82),
            (CITY_STREET_RE, 0.78),
            (PREPOSITIONAL_STREET_RE, 0.72),
            (PREFIXED_ADDRESS_RE, 0.86),
        )

        for pattern, score in patterns:
            for match in pattern.finditer(text):  # type: ignore[attr-defined]
                start, end = match.start(), match.end()
                if any(start < occ_end and end > occ_start for occ_start, occ_end in current_occupied):
                    continue
                original = clean_entity_text(match.group(0))
                if not original:
                    continue
                candidate = EntitySpan(
                    id=str(uuid4()),
                    original=original,
                    placeholder=self._placeholder,
                    entity_type="АДРЕС",
                    start=start,
                    end=end,
                    source="rule",
                    confidence=score,
                )
                decision = self.validate_candidate(text, candidate)
                if not decision.accepted:
                    continue
                accepted = replace(candidate, confidence=max(candidate.confidence, decision.score))
                supplemented.append(accepted)
                current_occupied.append((accepted.start, accepted.end))

        return prefer_best(supplemented)
