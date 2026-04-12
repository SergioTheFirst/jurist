"""Local anonymization logic for personally identifiable legal text."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from uuid import uuid4

from natasha import Doc, MorphVocab, NamesExtractor, NewsEmbedding, NewsMorphTagger, NewsNERTagger, Segmenter

from backend.core.dict_detector import DictSpan, detect_names, detect_vehicles
from backend.core.entity_rules import EntityRuleLayer
from backend.core.entity_rules.address_patterns import (
    CITY_STREET_RE,
    FULL_ADDRESS_RE,
    POI_ADDRESS_RE,
    POSTAL_CITY_RE,
    PREFIXED_ADDRESS_RE,
    PREPOSITIONAL_STREET_RE,
)
from backend.core.entity_rules.common import canonicalize_org_name, clean_entity_text, normalize_entity_text
from backend.core.entity_rules.context_rules import ADDRESS_CONTEXT_WORDS, has_nearby_context
from backend.core.entity_rules.models import EntitySpan, ReviewCandidate
from backend.core.legal_terms import LEGAL_WHITELIST


logger = logging.getLogger(__name__)

_segmenter = Segmenter()
_embedding = NewsEmbedding()
_morph_tagger = NewsMorphTagger(_embedding)
_ner_tagger = NewsNERTagger(_embedding)
_morph_vocab = MorphVocab()
_names_extractor = NamesExtractor(_morph_vocab)
_NORMALIZED_WHITELIST = {normalize_entity_text(term) for term in LEGAL_WHITELIST}


@dataclass(frozen=True)
class _PatternSpec:
    """Structured regex rule used for local PII detection."""

    entity_type: str
    pattern: re.Pattern[str]


_CandidateSpan = EntitySpan


_PATTERN_SPECS: tuple[_PatternSpec, ...] = (
    _PatternSpec("БАНК_СЧЁТ", re.compile(r"\b\d{20}\b")),
    _PatternSpec("БАНК_КАРТА", re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")),
    _PatternSpec("БИК", re.compile(r"\b0\d{8}\b")),
    _PatternSpec("VIN", re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")),
    _PatternSpec("ПАСПОРТ", re.compile(r"\b\d{2}\s?\d{2}\s?\d{6}\b")),
    _PatternSpec("ОГРН", re.compile(r"\bОГРН[:\s]*\d{13,15}\b", re.IGNORECASE)),
    _PatternSpec("ИНН", re.compile(r"\bИНН[:\s]*\d{10,12}\b", re.IGNORECASE)),
    _PatternSpec("СНИЛС", re.compile(r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b")),
    # Госномер прицепа: АА1234 77
    _PatternSpec(
        "ПРИЦЕП_НОМЕР",
        re.compile(r"\b[АВЕКМНОРСТУХABEKMHOPCTYX]{2}\d{4}\s?\d{2,3}\b"),
    ),
    # Госномер мотоцикла: 1234АА77
    _PatternSpec(
        "МОТО_НОМЕР",
        re.compile(r"\b\d{4}\s?[АВЕКМНОРСТУХABEKMHOPCTYX]{2}\s?\d{2,3}\b"),
    ),
    # Дата словесная: «12 января 2021 года»
    _PatternSpec(
        "ДАТА",
        re.compile(
            r"\b(?:0?[1-9]|[12]\d|3[01])\s+"
            r"(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)"
            r"\s+(?:19|20)\d{2}(?:\s+г(?:ода?|\.))?",
            re.IGNORECASE,
        ),
    ),
    # Дата в формате ДД.ММ.ГГГГ
    _PatternSpec(
        "ДАТА",
        re.compile(r"\b(?:0?[1-9]|[12]\d|3[01])[.\-/](?:0?[1-9]|1[0-2])[.\-/](?:19|20)\d{2}\b"),
    ),
    # Номер дела: А40-12345/2020
    _PatternSpec(
        "НОМЕР_ДЕЛА",
        re.compile(r"\b(?:[А-Я]\d{2}-\d+/\d{4}|\d{1,2}-\d+/\d{2,4}|\d{2}[А-Я]{2}-\d+/\d{4})\b"),
    ),
    # Инициалы: Иванов И.И.
    _PatternSpec(
        "ФИО_ИНИЦИАЛЫ",
        re.compile(
            r"\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.[А-ЯЁ]\."
            r"|\b[А-ЯЁ]\.[А-ЯЁ]\.\s+[А-ЯЁ][а-яё]+"
        ),
    ),
    _PatternSpec(
        "ТЕЛЕФОН",
        re.compile(r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"),
    ),
    _PatternSpec("EMAIL", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    _PatternSpec(
        "ДАТА_РОЖДЕНИЯ",
        re.compile(
            r"(?:дата?\s+рождения|д\.р\.|ДР)[:\s]*\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}",
            re.IGNORECASE,
        ),
    ),
    _PatternSpec("ПОЛИС", re.compile(r"\b[А-ЯA-Z]{3}\s?\d{10}\b")),
    _PatternSpec("СТС", re.compile(r"\b\d{2}\s?[А-ЯЁA-Z]{2}\s?\d{6}\b")),
    _PatternSpec(
        "ГОСНОМЕР",
        re.compile(r"\b[АВЕКМНОРСТУХABEKMHOPCTYX]\d{3}[АВЕКМНОРСТУХABEKMHOPCTYX]{2}\d{2,3}\b"),
    ),
    # Address detection uses composable primitives from `address_patterns.py`.
    # Order matters only for stable iteration — `_resolve_overlaps` picks the
    # widest match, so widest variants go first.
    _PatternSpec("АДРЕС", FULL_ADDRESS_RE),
    _PatternSpec("АДРЕС", PREFIXED_ADDRESS_RE),
    _PatternSpec("АДРЕС", POSTAL_CITY_RE),
    _PatternSpec("АДРЕС", CITY_STREET_RE),
    _PatternSpec("АДРЕС", PREPOSITIONAL_STREET_RE),
    _PatternSpec("АДРЕС", POI_ADDRESS_RE),
)


@dataclass
class ReplacementRecord:
    """A single replacement visible to the lawyer in the preview stage."""

    id: str
    original: str
    placeholder: str
    entity_type: str
    start: int
    end: int
    source: str
    confidence: float


@dataclass
class AnonymizationResult:
    """Structured anonymization output passed to API handlers and UI."""

    original_text: str
    anonymized_text: str
    entities_found: dict[str, list[str]] = field(default_factory=dict)
    total_replacements: int = 0
    warnings: list[str] = field(default_factory=list)
    replacements: list[ReplacementRecord] = field(default_factory=list)
    whitelist_skipped: list[str] = field(default_factory=list)
    review_candidates: list[ReviewCandidate] = field(default_factory=list)


class Anonymizer:
    """Hybrid local anonymizer: Natasha for named entities, regex for structured PII."""

    PLACEHOLDER = {
        "PER": "[ФИО]",
        "ORG": "[ОРГАНИЗАЦИЯ]",
        "ПАСПОРТ": "[ПАСПОРТ]",
        "ИНН": "[ИНН]",
        "СНИЛС": "[СНИЛС]",
        "ТЕЛЕФОН": "[ТЕЛЕФОН]",
        "EMAIL": "[EMAIL]",
        "ДАТА_РОЖДЕНИЯ": "[ДАТА РОЖДЕНИЯ]",
        "ДАТА": "[ДАТА]",
        "ОГРН": "[ОГРН]",
        "АДРЕС": "[АДРЕС]",
        "БАНК_СЧЁТ": "[БАНК. СЧЁТ]",
        "БАНК_КАРТА": "[БАНК. КАРТА]",
        "БИК": "[БИК]",
        "VIN": "[VIN]",
        "ГОСНОМЕР": "[ГОСНОМЕР]",
        "ПРИЦЕП_НОМЕР": "[ПРИЦЕП НОМЕР]",
        "МОТО_НОМЕР": "[МОТО НОМЕР]",
        "ПОЛИС": "[СТРАХ. ПОЛИС]",
        "СТС": "[СТС]",
        "МАРКА_ТС": "[МАРКА/МОДЕЛЬ ТС]",
        "НОМЕР_ДЕЛА": "[№ ДЕЛА]",
        "ФИО_ИНИЦИАЛЫ": "[ФИО]",
    }

    def __init__(self) -> None:
        """Initialize deterministic refinements above Natasha NER."""

        self._rule_layer = EntityRuleLayer(self.PLACEHOLDER)

    def anonymize(self, text: str) -> AnonymizationResult:
        """Replace detected personal data with placeholders and metadata."""

        if not text or not text.strip():
            return AnonymizationResult(
                original_text=text,
                anonymized_text=text,
                warnings=["Получен пустой текст"],
            )

        warnings: list[str] = []
        whitelist_skipped: list[str] = []
        review_candidates: list[ReviewCandidate] = []
        candidates: list[_CandidateSpan] = []

        candidates.extend(self._collect_ner_candidates(text, warnings, whitelist_skipped, review_candidates))
        candidates.extend(self._collect_dict_candidates(text))
        candidates.extend(self._collect_regex_candidates(text))

        resolved = self._resolve_overlaps(candidates)
        anonymized_text, records, entities_found = self._render_replacements(text, resolved)

        return AnonymizationResult(
            original_text=text,
            anonymized_text=anonymized_text,
            entities_found=entities_found,
            total_replacements=len(records),
            warnings=warnings,
            replacements=records,
            whitelist_skipped=whitelist_skipped,
            review_candidates=review_candidates,
        )

    @classmethod
    def _build_placeholder(cls, entity_type: str, index: int) -> str:
        """Return a stable numbered placeholder for a detected entity."""

        base = cls.PLACEHOLDER.get(entity_type, f"[{entity_type}]")
        if base.endswith("]"):
            return f"{base[:-1]}{index}]"
        return f"{base}{index}"

    @staticmethod
    def _normalize_original_key(value: str) -> str:
        """Normalize entity text so repeated mentions reuse the same placeholder number."""

        normalized = " ".join(str(value or "").split()).strip().casefold()
        return normalized or str(value or "").strip()

    def _collect_ner_candidates(
        self,
        text: str,
        warnings: list[str],
        whitelist_skipped: list[str],
        review_candidates: list[ReviewCandidate],
    ) -> list[_CandidateSpan]:
        candidates: list[_CandidateSpan] = []

        try:
            doc = Doc(text)
            doc.segment(_segmenter)
            doc.tag_morph(_morph_tagger)
            doc.tag_ner(_ner_tagger)
        except Exception as exc:  # pragma: no cover - Natasha runtime failure path
            logger.warning("NER failed: %s", exc)
            return candidates

        for span in doc.spans:
            if span.type not in {"PER", "ORG", "LOC"}:
                continue

            metadata: dict[str, str] = {}
            if span.type == "PER":
                try:
                    span.normalize(_morph_vocab)
                    span.extract_fact(_names_extractor)
                except Exception as exc:  # pragma: no cover - Natasha fact extraction failure
                    logger.debug("Name fact extraction failed for '%s': %s", text[span.start:span.stop], exc)
                else:
                    fact = getattr(span, "fact", None)
                    if fact is not None:
                        components = [
                            clean_entity_text(str(getattr(fact, "last", "") or "")),
                            clean_entity_text(str(getattr(fact, "first", "") or "")),
                            clean_entity_text(str(getattr(fact, "middle", "") or "")),
                        ]
                        normalized_fact = " ".join(component for component in components if component).strip()
                        if normalized_fact:
                            metadata["has_name_fact"] = "1"
                            metadata["name_fact"] = normalized_fact

            span_text = clean_entity_text(text[span.start:span.stop])
            if span.type == "LOC" and self._should_skip_loc_candidate(text, span.start, span.stop, span_text):
                continue
            if self._is_exact_whitelist_term(span_text):
                if span_text and span_text not in whitelist_skipped:
                    warnings.append(f"Пропущено из вайтлиста: '{span_text}' ({span.type})")
                    whitelist_skipped.append(span_text)
                continue

            # Unify LOC → АДРЕС so Natasha LOC candidates share the counter
            # with regex-based address matches in `_render_replacements`.
            canonical_type = "АДРЕС" if span.type == "LOC" else span.type
            candidates.append(
                _CandidateSpan(
                    id=str(uuid4()),
                    original=span_text,
                    placeholder=self.PLACEHOLDER[canonical_type],
                    entity_type=canonical_type,
                    start=span.start,
                    end=span.stop,
                    source="ner",
                    confidence=float(getattr(span, "score", 0.85) or 0.85),
                    metadata=metadata,
                )
            )

        return self._rule_layer.refine_candidates(text, candidates, warnings, whitelist_skipped, review_candidates)

    def _collect_dict_candidates(self, text: str) -> list[_CandidateSpan]:
        """Detect vehicles (brand/model) and regional names via offline dictionaries."""
        all_dict_spans: list[DictSpan] = list(detect_vehicles(text)) + list(detect_names(text))
        return [
            _CandidateSpan(
                id=span.id,
                original=span.original,
                placeholder=self.PLACEHOLDER.get(span.entity_type, f"[{span.entity_type}]"),
                entity_type=span.entity_type,
                start=span.start,
                end=span.end,
                source="dict",
                confidence=span.confidence,
            )
            for span in all_dict_spans
        ]

    def _collect_regex_candidates(self, text: str) -> list[_CandidateSpan]:
        candidates: list[_CandidateSpan] = []

        for spec in _PATTERN_SPECS:
            for match in spec.pattern.finditer(text):
                original = match.group(0)
                candidates.append(
                    _CandidateSpan(
                        id=str(uuid4()),
                        original=original,
                        placeholder=self.PLACEHOLDER[spec.entity_type],
                        entity_type=spec.entity_type,
                        start=match.start(),
                        end=match.end(),
                        source="regex",
                        confidence=1.0,
                    )
                )

        return candidates

    def _resolve_overlaps(self, candidates: list[_CandidateSpan]) -> list[_CandidateSpan]:
        if not candidates:
            return []

        # Приоритет источников: ner(0) > dict(1) > regex(2)
        _source_priority = {"ner": 0, "dict": 1, "regex": 2}

        def sort_key(candidate: _CandidateSpan) -> tuple[int, int, int]:
            coverage = candidate.end - candidate.start
            source_priority = _source_priority.get(candidate.source, 3)
            return (candidate.start, -coverage, source_priority)

        accepted: list[_CandidateSpan] = []
        for candidate in sorted(candidates, key=sort_key):
            conflict_index = self._find_conflict(accepted, candidate)
            if conflict_index == -1:
                accepted.append(candidate)
                continue

            incumbent = accepted[conflict_index]
            if self._should_replace_overlap(candidate, incumbent):
                accepted[conflict_index] = candidate

        return sorted(accepted, key=lambda candidate: candidate.start)

    @staticmethod
    def _find_conflict(accepted: list[_CandidateSpan], candidate: _CandidateSpan) -> int:
        for index, item in enumerate(accepted):
            if candidate.start < item.end and candidate.end > item.start:
                return index
        return -1

    @staticmethod
    def _should_replace_overlap(candidate: _CandidateSpan, incumbent: _CandidateSpan) -> bool:
        candidate_coverage = candidate.end - candidate.start
        incumbent_coverage = incumbent.end - incumbent.start

        if candidate_coverage != incumbent_coverage:
            return candidate_coverage > incumbent_coverage
        # При равном покрытии выигрывает источник с более высоким приоритетом: ner > dict > regex
        _priority = {"ner": 0, "dict": 1, "regex": 2}
        candidate_prio = _priority.get(candidate.source, 3)
        incumbent_prio = _priority.get(incumbent.source, 3)
        if candidate_prio != incumbent_prio:
            return candidate_prio < incumbent_prio
        return candidate.confidence > incumbent.confidence

    def _render_replacements(
        self,
        text: str,
        spans: list[_CandidateSpan],
    ) -> tuple[str, list[ReplacementRecord], dict[str, list[str]]]:
        cursor = 0
        final_length = 0
        parts: list[str] = []
        records: list[ReplacementRecord] = []
        entities_found: dict[str, list[str]] = {}
        placeholder_map: dict[str, dict[str, int]] = {}
        placeholder_counters: dict[str, int] = {}

        for span in spans:
            if span.start < cursor:
                continue

            plain_chunk = text[cursor:span.start]
            parts.append(plain_chunk)
            final_length += len(plain_chunk)

            entity_registry = placeholder_map.setdefault(span.entity_type, {})
            if span.entity_type == "ORG":
                normalized_original_key = canonicalize_org_name(span.original)
            else:
                normalized_original_key = self._normalize_original_key(span.original)
            entity_key = span.identity_key or normalized_original_key
            if entity_key not in entity_registry:
                next_index = placeholder_counters.get(span.entity_type, 0) + 1
                placeholder_counters[span.entity_type] = next_index
                entity_registry[entity_key] = next_index
            placeholder = self._build_placeholder(span.entity_type, entity_registry[entity_key])

            record = ReplacementRecord(
                id=span.id,
                original=span.original,
                placeholder=placeholder,
                entity_type=span.entity_type,
                start=final_length,
                end=final_length + len(placeholder),
                source=span.source,
                confidence=span.confidence,
            )
            parts.append(placeholder)
            records.append(record)
            entities_found.setdefault(span.entity_type, []).append(span.original)
            final_length = record.end
            cursor = span.end

        parts.append(text[cursor:])
        return "".join(parts), records, entities_found

    @staticmethod
    def _is_exact_whitelist_term(value: str) -> bool:
        """Return True when the cleaned span exactly matches a legal whitelist term."""

        return normalize_entity_text(value) in _NORMALIZED_WHITELIST

    @staticmethod
    def _should_skip_loc_candidate(text: str, start: int, end: int, value: str) -> bool:
        """Drop noisy Natasha LOC abbreviations that are not personal data.

        Short uppercase acronyms (e.g. "РТ", "КБР") pass through when an
        address-context word sits nearby — they're abbreviated subject names.
        """

        normalized = normalize_entity_text(value)
        if normalized in {"рф", "россия", "российская федерация", "ссср"}:
            return True
        stripped = value.strip()
        if len(normalized) <= 3 and stripped.isupper():
            return not has_nearby_context(text, start, end, ADDRESS_CONTEXT_WORDS)
        return False


anonymizer = Anonymizer()
