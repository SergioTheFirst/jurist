"""Pipeline that refines Natasha PER/ORG candidates with local rules."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Mapping

from backend.core.entity_rules.common import clean_entity_text, normalize_entity_text, prefer_best
from backend.core.entity_rules.loc_rules import LocationRuleEngine
from backend.core.entity_rules.models import EntitySpan, ReviewCandidate, RuleDecision
from backend.core.entity_rules.org_rules import OrganizationRuleEngine
from backend.core.entity_rules.per_rules import PersonRuleEngine
from backend.core.legal_terms import LEGAL_WHITELIST


_NORMALIZED_WHITELIST = {normalize_entity_text(term): term for term in LEGAL_WHITELIST}


class EntityRuleLayer:
    """Validate, expand, and supplement named entities without using external LLMs."""

    def __init__(self, placeholders: Mapping[str, str]) -> None:
        self._person_rules = PersonRuleEngine(placeholders["PER"])
        self._organization_rules = OrganizationRuleEngine(placeholders["ORG"])
        self._location_rules = LocationRuleEngine(
            placeholders.get("АДРЕС", placeholders.get("LOC", "[АДРЕС]"))
        )

    def refine_candidates(
        self,
        text: str,
        candidates: Iterable[EntitySpan],
        warnings: list[str],
        whitelist_skipped: list[str],
        review_candidates: list[ReviewCandidate],
    ) -> list[EntitySpan]:
        """Refine raw Natasha candidates and add missed person/organization entities."""

        refined: list[EntitySpan] = []
        for candidate in candidates:
            cleaned = clean_entity_text(candidate.original)
            if self._is_whitelisted(cleaned):
                self._append_whitelist_skip(cleaned, candidate.entity_type, warnings, whitelist_skipped)
                continue
            if candidate.entity_type == "PER":
                decision_candidate = self._person_rules.expand_candidate(text, candidate)
                refined_candidate = self._accept_or_warn(
                    text=text,
                    candidate=decision_candidate,
                    decision=self._person_rules.validate_candidate(text, decision_candidate),
                    warnings=warnings,
                    review_candidates=review_candidates,
                )
                if refined_candidate is not None:
                    refined.append(self._person_rules.bind_identity(refined_candidate))
                continue
            if candidate.entity_type == "ORG":
                decision_candidate = self._organization_rules.expand_candidate(text, candidate)
                refined_candidate = self._accept_or_warn(
                    text=text,
                    candidate=decision_candidate,
                    decision=self._organization_rules.validate_candidate(text, decision_candidate),
                    warnings=warnings,
                    review_candidates=review_candidates,
                )
                if refined_candidate is not None:
                    refined.append(refined_candidate)
                continue
            if candidate.entity_type in ("LOC", "АДРЕС"):
                decision_candidate = self._location_rules.expand_candidate(text, candidate)
                refined_candidate = self._accept_or_warn(
                    text=text,
                    candidate=decision_candidate,
                    decision=self._location_rules.validate_candidate(text, decision_candidate),
                    warnings=warnings,
                    review_candidates=review_candidates,
                )
                if refined_candidate is not None:
                    refined.append(refined_candidate)
                continue
            refined.append(replace(candidate, original=clean_entity_text(candidate.original)))

        occupied = [(candidate.start, candidate.end) for candidate in refined]
        refined.extend(
            self._collect_supplements(
                text=text,
                occupied=occupied,
                warnings=warnings,
                whitelist_skipped=whitelist_skipped,
            )
        )
        person_candidates = [candidate for candidate in refined if candidate.entity_type == "PER"]
        alias_candidates = self._person_rules.supplement_aliases(text, occupied, person_candidates)
        refined.extend(alias_candidates)
        refined = self._person_rules.link_known_identities(refined)
        return prefer_best(refined)

    @staticmethod
    def _accept_or_warn(
        *,
        text: str,
        candidate: EntitySpan,
        decision: RuleDecision,
        warnings: list[str],
        review_candidates: list[ReviewCandidate],
    ) -> EntitySpan | None:
        """Return accepted candidates and separate borderline candidates into review bucket."""

        if decision.accepted:
            return replace(candidate, confidence=max(candidate.confidence, decision.score))
        original = clean_entity_text(text[candidate.start:candidate.end])
        if decision.reviewable:
            review_candidates.append(
                ReviewCandidate(
                    original=original,
                    entity_type=candidate.entity_type,
                    start=candidate.start,
                    end=candidate.end,
                    source=candidate.source,
                    confidence=candidate.confidence,
                    score=decision.score,
                    reason=decision.reason,
                    model_confidence=decision.model_confidence,
                    context_bonus=decision.context_bonus,
                    penalty=decision.penalty,
                )
            )
            warnings.append(f"Требует проверки {candidate.entity_type}: '{original}' ({decision.reason})")
            return None
        if candidate.source == "ner" and candidate.confidence >= 0.88:
            warnings.append(f"Отклонено правилом {candidate.entity_type}: '{original}' ({decision.reason})")
        return None

    def _collect_supplements(
        self,
        *,
        text: str,
        occupied: list[tuple[int, int]],
        warnings: list[str],
        whitelist_skipped: list[str],
    ) -> list[EntitySpan]:
        """Collect additional person and organization entities missed by NER."""

        supplemented: list[EntitySpan] = []
        for engine in (self._organization_rules, self._person_rules, self._location_rules):
            for candidate in engine.supplement_candidates(text, occupied):
                cleaned = clean_entity_text(candidate.original)
                if self._is_whitelisted(cleaned):
                    self._append_whitelist_skip(cleaned, candidate.entity_type, warnings, whitelist_skipped)
                    continue
                supplemented.append(candidate)
                occupied.append((candidate.start, candidate.end))
        return prefer_best(supplemented)

    @staticmethod
    def _append_whitelist_skip(
        term: str,
        entity_type: str,
        warnings: list[str],
        whitelist_skipped: list[str],
    ) -> None:
        """Record a unique whitelist skip warning."""

        if term and term not in whitelist_skipped:
            warnings.append(f"Пропущено из вайтлиста: '{term}' ({entity_type})")
            whitelist_skipped.append(term)

    @staticmethod
    def _is_whitelisted(value: str) -> bool:
        """Return True when a cleaned entity text exactly matches a whitelist term."""

        return normalize_entity_text(value) in _NORMALIZED_WHITELIST
