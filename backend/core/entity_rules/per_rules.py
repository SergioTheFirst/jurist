"""Rule engine that validates, supplements, and links person-name aliases."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Iterable
from uuid import uuid4

from backend.core.entity_rules.common import (
    clean_entity_text,
    is_initials,
    is_composed_only_of_lemmas,
    is_name_like_token,
    lemmatize_word,
    lemma_overlap_count,
    normalize_entity_text,
    tokenize_name_fragments,
    with_updated_span,
)
from backend.core.entity_rules.context_rules import (
    PERSON_ALIAS_PREFIXES,
    PERSON_CONTEXT_WORDS,
    PERSON_STOPWORD_LEMMAS,
    PROCEDURAL_ROLE_LEMMAS,
    ROLE_OR_GENERIC_LEMMAS,
    TABLE_HEADER_LEMMAS,
    has_nearby_context,
)
from backend.core.entity_rules.expanders import iter_person_matches
from backend.core.entity_rules.models import EntitySpan, RuleDecision
from backend.core.entity_rules.supplemental_rules import collect_supplement_spans, iter_person_alias_matches


_PATRONYMIC_SUFFIXES = (
    "ович",
    "евич",
    "ич",
    "овна",
    "евна",
    "ична",
    "оглы",
    "кызы",
)

_SURNAME_SUFFIXES = (
    "ов",
    "ев",
    "ёв",
    "ин",
    "ын",
    "ский",
    "цкий",
    "енко",
    "ук",
    "юк",
    "ич",
    "ко",
    "дзе",
    "швили",
)

_REVIEW_THRESHOLD = 0.62
_ACCEPT_THRESHOLD = 0.78
_ROLE_PREFIX_TOKEN_RE = re.compile(r"[А-ЯЁA-Zа-яёa-z][А-ЯЁA-Zа-яёa-z.-]*")
_NORMALIZED_ALIAS_PREFIXES = {normalize_entity_text(prefix).rstrip(".") for prefix in PERSON_ALIAS_PREFIXES}


@dataclass(frozen=True)
class _PersonSignature:
    """Canonical person identity used to bind aliases to one placeholder."""

    canonical_key: str
    full_name: str
    surname: str
    initials: tuple[str, ...]


def _looks_like_patronymic(token: str) -> bool:
    value = normalize_entity_text(token)
    return any(value.endswith(suffix) for suffix in _PATRONYMIC_SUFFIXES)


def _looks_like_surname(token: str) -> bool:
    value = normalize_entity_text(token)
    if len(value) < 4:
        return False
    return any(value.endswith(suffix) for suffix in _SURNAME_SUFFIXES)


def _has_person_context(text: str, start: int, end: int) -> bool:
    return has_nearby_context(text, start, end, PERSON_CONTEXT_WORDS)


def _contains_blocking_terms(tokens: list[str]) -> bool:
    return is_composed_only_of_lemmas(" ".join(tokens), PERSON_STOPWORD_LEMMAS)


def _table_header_hits(tokens: list[str]) -> int:
    return lemma_overlap_count(" ".join(tokens), TABLE_HEADER_LEMMAS)


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


def _is_role_prefix_token(token: str) -> bool:
    normalized = normalize_entity_text(token).rstrip(".")
    if not normalized:
        return False
    if normalized in _NORMALIZED_ALIAS_PREFIXES:
        return True
    lemma = lemmatize_word(normalized)
    return lemma in PROCEDURAL_ROLE_LEMMAS or lemma in ROLE_OR_GENERIC_LEMMAS


class PersonRuleEngine:
    """Validate and supplement person-name entities around Natasha output."""

    def __init__(self, placeholder: str) -> None:
        self._placeholder = placeholder

    def bind_identity(self, candidate: EntitySpan) -> EntitySpan:
        """Attach a canonical identity key so aliases reuse the same placeholder."""

        signature = self._signature_from_text(candidate.original)
        if signature is None:
            return candidate
        return replace(candidate, identity_key=signature.canonical_key)

    def expand_candidate(self, text: str, candidate: EntitySpan) -> EntitySpan:
        """Expand a partial NER span to a full FIO or initials pattern when possible."""

        best = self._strip_leading_role_prefixes(text, candidate)
        best_decision = self.validate_candidate(text, best)
        for start, end, _match_text, score in self._normalized_person_matches(text):
            if not (start <= candidate.end and end >= candidate.start):
                continue
            expanded = self._strip_leading_role_prefixes(
                text,
                with_updated_span(best, start, end, text, score),
            )
            decision = self.validate_candidate(text, expanded)
            if (
                int(decision.accepted),
                int(decision.reviewable),
                decision.score,
                expanded.coverage,
                expanded.confidence,
            ) > (
                int(best_decision.accepted),
                int(best_decision.reviewable),
                best_decision.score,
                best.coverage,
                best.confidence,
            ):
                best = expanded
                best_decision = decision
        return replace(best, original=clean_entity_text(best.original))

    def validate_candidate(self, text: str, candidate: EntitySpan) -> RuleDecision:
        """Return whether a PER candidate should survive automatic anonymization."""

        candidate = self._strip_leading_role_prefixes(text, candidate)
        original = clean_entity_text(candidate.original)
        if not original:
            return RuleDecision("reject", 0.0, "empty", penalty=1.0)

        tokens = tokenize_name_fragments(original)
        if not tokens:
            return RuleDecision("reject", 0.0, "no_name_tokens", penalty=1.0)
        if not all(is_name_like_token(token) for token in tokens):
            return RuleDecision("reject", 0.2, "non_name_token", penalty=0.5)

        model_confidence = max(candidate.confidence, 0.42)
        context_bonus = 0.0
        penalty = 0.0
        context = _has_person_context(text, candidate.start, candidate.end)
        has_name_fact = candidate.metadata.get("has_name_fact") == "1"
        token_count = len(tokens)
        surname_hits = sum(1 for token in tokens if not is_initials(token) and _looks_like_surname(token))
        patronymic_present = any(_looks_like_patronymic(token) for token in tokens if not is_initials(token))
        table_header_hits = _table_header_hits(tokens)
        generic_hits = lemma_overlap_count(original, ROLE_OR_GENERIC_LEMMAS)

        if _contains_blocking_terms(tokens):
            return RuleDecision("reject", 0.2, "generic_role_or_legal_term", penalty=0.6)
        if is_composed_only_of_lemmas(original, ROLE_OR_GENERIC_LEMMAS, min_tokens=1):
            return RuleDecision("reject", 0.05, "generic_role_only_sequence", penalty=0.9)

        if has_name_fact:
            context_bonus += 0.16

        if table_header_hits >= 2 and not context and not has_name_fact:
            return RuleDecision("reject", 0.08, "tabular_header_terms", penalty=0.75)

        if token_count >= 3:
            if generic_hits >= 2 and not has_name_fact and not context:
                return RuleDecision("reject", 0.06, "mostly_generic_three_part_sequence", penalty=0.82)
            if not has_name_fact and not patronymic_present and surname_hits == 0 and not context:
                return RuleDecision("reject", 0.12, "non_person_three_part_sequence", penalty=0.7)
            context_bonus += 0.2
            if patronymic_present:
                context_bonus += 0.08
            if surname_hits:
                context_bonus += 0.04
            return _score_decision(
                model_confidence=model_confidence,
                context_bonus=context_bonus,
                penalty=penalty,
                reason="three_part_name",
            )

        if token_count == 2:
            if generic_hits >= 1 and not context and not has_name_fact:
                return RuleDecision("reject", 0.08, "generic_two_part_sequence", penalty=0.76)
            if any(is_initials(token) for token in tokens):
                context_bonus += 0.22
                return _score_decision(
                    model_confidence=model_confidence,
                    context_bonus=context_bonus,
                    penalty=penalty,
                    reason="surname_with_initials",
                )
            if context:
                context_bonus += 0.14
                return _score_decision(
                    model_confidence=model_confidence,
                    context_bonus=context_bonus,
                    penalty=penalty,
                    reason="two_part_name_with_context",
                )
            if any(_looks_like_surname(token) for token in tokens) and (candidate.confidence >= 0.9 or has_name_fact):
                context_bonus += 0.05
                return _score_decision(
                    model_confidence=model_confidence,
                    context_bonus=context_bonus,
                    penalty=penalty,
                    reason="borderline_two_part_name",
                )
            penalty += 0.08
            return _score_decision(
                model_confidence=model_confidence,
                context_bonus=context_bonus,
                penalty=penalty,
                reason="ambiguous_two_part_name",
            )

        token = tokens[0]
        if generic_hits >= 1:
            return RuleDecision("reject", 0.05, "generic_single_token", penalty=0.88)
        if context and (_looks_like_surname(token) or candidate.confidence >= 0.93 or has_name_fact):
            context_bonus += 0.12
            return _score_decision(
                model_confidence=model_confidence,
                context_bonus=context_bonus,
                penalty=penalty,
                reason="single_token_with_context",
            )
        penalty += 0.15
        return _score_decision(
            model_confidence=model_confidence,
            context_bonus=context_bonus,
            penalty=penalty,
            reason="ambiguous_single_token",
        )

    def supplement_candidates(self, text: str, occupied: Iterable[tuple[int, int]]) -> list[EntitySpan]:
        """Find FIO patterns that Natasha often misses in legal documents."""

        return collect_supplement_spans(
            text=text,
            occupied=occupied,
            placeholder=self._placeholder,
            entity_type="PER",
            source="rule",
            matches=self._normalized_person_matches(text),
            validator=self.validate_candidate,
            mutator=lambda candidate: self.bind_identity(self._strip_leading_role_prefixes(text, candidate)),
        )

    def supplement_aliases(
        self,
        text: str,
        occupied: Iterable[tuple[int, int]],
        known_people: Iterable[EntitySpan],
    ) -> list[EntitySpan]:
        """Link short aliases of already-known persons to the same placeholder."""

        alias_matches: list[tuple[int, int, str, float, str]] = []
        seen: set[tuple[int, int, str]] = set()

        for signature in self._collect_signatures(known_people):
            for start, end, original, score in iter_person_alias_matches(
                text=text,
                canonical_key=signature.canonical_key,
                surname=signature.surname,
                initials=signature.initials,
                prefixes=PERSON_ALIAS_PREFIXES,
                context_check=lambda alias_start, alias_end: _has_person_context(text, alias_start, alias_end),
            ):
                dedupe_key = (start, end, signature.canonical_key)
                if dedupe_key in seen:
                    continue
                alias_matches.append((start, end, original, score, signature.canonical_key))
                seen.add(dedupe_key)

        raw_candidates = [
            EntitySpan(
                id=str(uuid4()),
                original=original,
                placeholder=self._placeholder,
                entity_type="PER",
                start=start,
                end=end,
                source="alias",
                confidence=score,
                identity_key=identity_key,
            )
            for start, end, original, score, identity_key in alias_matches
        ]

        current_occupied = list(occupied)
        accepted: list[EntitySpan] = []
        for candidate in raw_candidates:
            if any(candidate.start < end and candidate.end > start for start, end in current_occupied):
                continue
            decision = self.validate_candidate(text, candidate)
            if not decision.accepted:
                continue
            item = replace(candidate, confidence=max(candidate.confidence, decision.score))
            accepted.append(item)
            current_occupied.append((item.start, item.end))
        return accepted

    def link_known_identities(self, candidates: Iterable[EntitySpan]) -> list[EntitySpan]:
        """Bind short aliases to the strongest full-name identity in the same document."""

        signatures_by_surname: dict[str, list[_PersonSignature]] = {}
        candidate_signatures: list[tuple[EntitySpan, _PersonSignature | None]] = []

        for candidate in candidates:
            if candidate.entity_type != "PER":
                candidate_signatures.append((candidate, None))
                continue
            signature = self._signature_from_candidate(candidate)
            candidate_signatures.append((candidate, signature))
            if signature is None:
                continue
            surname_key = normalize_entity_text(signature.surname)
            bucket = signatures_by_surname.setdefault(surname_key, [])
            if all(existing.canonical_key != signature.canonical_key for existing in bucket):
                bucket.append(signature)

        linked: list[EntitySpan] = []
        for candidate, signature in candidate_signatures:
            if candidate.entity_type != "PER" or signature is None:
                linked.append(candidate)
                continue
            surname_key = normalize_entity_text(signature.surname)
            target = self._pick_identity_target(signature, signatures_by_surname.get(surname_key, []))
            if target is None:
                linked.append(self.bind_identity(candidate))
                continue
            linked.append(replace(candidate, identity_key=target.canonical_key))
        return linked

    def _collect_signatures(self, known_people: Iterable[EntitySpan]) -> list[_PersonSignature]:
        """Normalize accepted person candidates into unique identity signatures."""

        signatures: dict[str, _PersonSignature] = {}
        for candidate in known_people:
            signature = self._signature_from_candidate(candidate)
            if signature is None:
                continue
            incumbent = signatures.get(signature.canonical_key)
            if incumbent is None or len(signature.full_name) > len(incumbent.full_name):
                signatures[signature.canonical_key] = signature
        return list(signatures.values())

    @staticmethod
    def _pick_identity_target(
        signature: _PersonSignature,
        candidates: list[_PersonSignature],
    ) -> _PersonSignature | None:
        """Pick the canonical signature that should own the alias placeholder."""

        if not candidates:
            return None
        sorted_candidates = sorted(candidates, key=PersonRuleEngine._signature_rank, reverse=True)
        exact = next(
            (candidate for candidate in sorted_candidates if candidate.canonical_key == signature.canonical_key),
            None,
        )
        exact_rank = PersonRuleEngine._signature_rank(exact) if exact is not None else None
        signature_rank = PersonRuleEngine._signature_rank(signature)
        best_candidate = sorted_candidates[0]
        best_rank = PersonRuleEngine._signature_rank(best_candidate)

        if best_rank <= signature_rank and exact is not None:
            return exact

        if signature.initials:
            compatible = [
                candidate
                for candidate in sorted_candidates
                if candidate.initials[: len(signature.initials)] == signature.initials
            ]
            if compatible:
                best_compatible = compatible[0]
                if PersonRuleEngine._signature_rank(best_compatible) > signature_rank:
                    return best_compatible
                if len(compatible) == 1:
                    return best_compatible
            return exact

        informative = [candidate for candidate in sorted_candidates if candidate.initials]
        if len(informative) == 1:
            return informative[0]
        if exact is not None and exact_rank is not None and exact_rank >= best_rank:
            return exact
        return best_candidate if best_rank > signature_rank else exact

    @staticmethod
    def _signature_rank(signature: _PersonSignature) -> tuple[int, int, int]:
        """Prefer longer and more informative signatures as canonical identities."""

        token_count = len(tokenize_name_fragments(signature.full_name))
        return (token_count, len(signature.initials), len(signature.full_name))

    def _signature_from_candidate(self, candidate: EntitySpan) -> _PersonSignature | None:
        """Build a canonical signature from an accepted candidate."""

        signature = self._signature_from_text(candidate.original)
        if signature is None:
            return None
        canonical_key = candidate.identity_key or signature.canonical_key
        return replace(signature, canonical_key=canonical_key)

    @staticmethod
    def _signature_from_text(text: str) -> _PersonSignature | None:
        """Extract surname and initials from a person-like mention."""

        tokens = tokenize_name_fragments(clean_entity_text(text))
        while len(tokens) >= 2 and _is_role_prefix_token(tokens[0]):
            tokens = tokens[1:]
        if not tokens:
            return None

        words = [token for token in tokens if not is_initials(token)]
        initials_tokens = [token for token in tokens if is_initials(token)]
        if not words:
            return None

        surname = ""
        initials: list[str] = []
        if initials_tokens:
            if tokens and is_initials(tokens[0]) and len(words) >= 1:
                surname = words[-1]
            else:
                surname = words[0]
            initials.extend(PersonRuleEngine._split_initials(initials_tokens[0]))
        else:
            surname = words[0]
            if len(words) >= 2:
                initials.append(f"{words[1][0].upper()}.")
            if len(words) >= 3:
                initials.append(f"{words[2][0].upper()}.")

        canonical_key = normalize_entity_text(clean_entity_text(text))
        return _PersonSignature(
            canonical_key=canonical_key,
            full_name=clean_entity_text(text),
            surname=surname,
            initials=tuple(initials),
        )

    @staticmethod
    def _split_initials(token: str) -> list[str]:
        """Split a combined initials token into individual initials."""

        return [f"{letter.upper()}." for letter in token if "А" <= letter.upper() <= "Я" or letter.upper() == "Ё"]

    def _normalized_person_matches(self, text: str) -> list[tuple[int, int, str, float]]:
        """Normalize regex person matches so role prefixes do not become part of the entity."""

        best_by_key: dict[tuple[int, int, str], tuple[int, int, str, float]] = {}
        for start, end, original, score in iter_person_matches(text):
            candidate = EntitySpan(
                id=str(uuid4()),
                original=original,
                placeholder=self._placeholder,
                entity_type="PER",
                start=start,
                end=end,
                source="rule",
                confidence=score,
            )
            trimmed = self._strip_leading_role_prefixes(text, candidate)
            if not trimmed.original:
                continue
            key = (trimmed.start, trimmed.end, normalize_entity_text(trimmed.original))
            incumbent = best_by_key.get(key)
            current = (trimmed.start, trimmed.end, trimmed.original, score)
            if incumbent is None or (current[1] - current[0], current[3]) > (incumbent[1] - incumbent[0], incumbent[3]):
                best_by_key[key] = current
        return sorted(best_by_key.values(), key=lambda item: (item[0], item[1], item[2]))

    @staticmethod
    def _strip_leading_role_prefixes(text: str, candidate: EntitySpan) -> EntitySpan:
        """Trim leading role words from a person span while preserving exact document offsets."""

        raw = text[candidate.start:candidate.end]
        matches = list(_ROLE_PREFIX_TOKEN_RE.finditer(raw))
        if len(matches) < 2:
            return replace(candidate, original=clean_entity_text(raw))

        trim_to = 0
        trimmed = False
        remaining = len(matches)
        for match in matches:
            if remaining <= 1:
                break
            if not _is_role_prefix_token(match.group(0)):
                break
            trim_to = match.end()
            trimmed = True
            remaining -= 1

        if not trimmed:
            return replace(candidate, original=clean_entity_text(raw))

        while trim_to < len(raw) and raw[trim_to].isspace():
            trim_to += 1
        if trim_to >= len(raw):
            return replace(candidate, original=clean_entity_text(raw))

        new_start = candidate.start + trim_to
        return replace(
            candidate,
            start=new_start,
            original=clean_entity_text(text[new_start:candidate.end]),
        )
