"""Rule engine that validates and supplements organization entities."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from backend.core.entity_rules.common import (
    clean_entity_text,
    contains_any_lemma,
    is_composed_only_of_lemmas,
    lemmatize_text_tokens,
    normalize_entity_text,
    with_updated_span,
)
from backend.core.entity_rules.context_rules import (
    ORG_KEYWORD_LEMMAS,
    ORG_LONG_FORMS,
    ORG_SHORT_FORMS,
    ORG_STOPWORD_LEMMAS,
    ROLE_OR_GENERIC_LEMMAS,
)
from backend.core.entity_rules.expanders import iter_org_matches
from backend.core.entity_rules.models import EntitySpan, RuleDecision
from backend.core.entity_rules.supplemental_rules import collect_supplement_spans


_REVIEW_THRESHOLD = 0.6
_ACCEPT_THRESHOLD = 0.77
_SHORT_FORM_SET = {item.casefold() for item in ORG_SHORT_FORMS}
_LONG_FORM_SET = {item.casefold() for item in ORG_LONG_FORMS}


def _score_decision(
    *,
    model_confidence: float,
    context_bonus: float,
    penalty: float,
    reason: str,
) -> RuleDecision:
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


def _is_bare_org_form(value: str) -> bool:
    return normalize_entity_text(value) in _SHORT_FORM_SET


def _has_quoted_name(value: str) -> bool:
    return '"' in value or "«" in value or "»" in value


def _has_distinctive_org_name(value: str) -> bool:
    token_lemmas = lemmatize_text_tokens(value)
    return any(lemma not in ROLE_OR_GENERIC_LEMMAS for lemma in token_lemmas)


class OrganizationRuleEngine:
    """Validate and supplement organization names around Natasha output."""

    def __init__(self, placeholder: str) -> None:
        self._placeholder = placeholder

    def expand_candidate(self, text: str, candidate: EntitySpan) -> EntitySpan:
        """Expand a partial organization span to include its legal form and quoted name."""

        best = candidate
        for start, end, _match_text, score in iter_org_matches(text):
            if not (start <= candidate.end and end >= candidate.start):
                continue
            expanded = with_updated_span(candidate, start, end, text, score)
            if expanded.coverage > best.coverage or expanded.confidence > best.confidence:
                best = expanded
        return replace(best, original=clean_entity_text(best.original))

    def validate_candidate(self, text: str, candidate: EntitySpan) -> RuleDecision:
        """Return whether an ORG candidate is safe to anonymize automatically."""

        del text
        original = clean_entity_text(candidate.original)
        if not original:
            return RuleDecision("reject", 0.0, "empty", penalty=1.0)
        if _is_bare_org_form(original):
            return RuleDecision("reject", 0.2, "bare_org_form", penalty=0.6)
        if is_composed_only_of_lemmas(original, ROLE_OR_GENERIC_LEMMAS, min_tokens=1):
            return RuleDecision("reject", 0.05, "generic_role_only_org", penalty=0.92)
        if contains_any_lemma(original, ORG_STOPWORD_LEMMAS):
            return RuleDecision("reject", 0.25, "legal_stopword", penalty=0.55)

        model_confidence = max(candidate.confidence, 0.48)
        context_bonus = 0.0
        penalty = 0.0
        normalized = normalize_entity_text(original)
        has_distinctive_name = _has_distinctive_org_name(original)
        has_quoted_name = _has_quoted_name(original)

        if any(form in normalized for form in _SHORT_FORM_SET):
            if has_distinctive_name and (has_quoted_name or len(original.split()) >= 2):
                context_bonus += 0.24
                return _score_decision(
                    model_confidence=model_confidence,
                    context_bonus=context_bonus,
                    penalty=penalty,
                    reason="short_form_with_name",
                )
            return RuleDecision("reject", 0.08, "short_form_without_distinctive_name", penalty=0.82)

        if any(form in normalized for form in _LONG_FORM_SET):
            if not has_distinctive_name:
                return RuleDecision("reject", 0.08, "long_form_without_distinctive_name", penalty=0.82)
            context_bonus += 0.28
            return _score_decision(
                model_confidence=model_confidence,
                context_bonus=context_bonus,
                penalty=penalty,
                reason="long_form_org",
            )

        if contains_any_lemma(original, ORG_KEYWORD_LEMMAS) and len(original.split()) >= 2 and has_distinctive_name:
            context_bonus += 0.16
            return _score_decision(
                model_confidence=model_confidence,
                context_bonus=context_bonus,
                penalty=penalty,
                reason="keyword_org",
            )

        if candidate.confidence >= 0.9 and len(original.split()) >= 2 and has_distinctive_name:
            context_bonus += 0.05
            return _score_decision(
                model_confidence=model_confidence,
                context_bonus=context_bonus,
                penalty=penalty,
                reason="high_confidence_org",
            )

        penalty += 0.08
        return _score_decision(
            model_confidence=model_confidence,
            context_bonus=context_bonus,
            penalty=penalty,
            reason="ambiguous_org",
        )

    def supplement_candidates(self, text: str, occupied: Iterable[tuple[int, int]]) -> list[EntitySpan]:
        """Find organization signatures that Natasha often misses in legal documents."""

        return collect_supplement_spans(
            text=text,
            occupied=occupied,
            placeholder=self._placeholder,
            entity_type="ORG",
            source="rule",
            matches=iter_org_matches(text),
            validator=self.validate_candidate,
        )
