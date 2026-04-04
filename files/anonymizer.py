"""
Модуль локальной анонимизации персональных данных.
Все операции выполняются ТОЛЬКО локально — данные никуда не передаются.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from natasha import (
    Segmenter, MorphVocab,
    NewsEmbedding, NewsMorphTagger,
    NewsNERTagger, NamesExtractor,
    Doc
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Инициализация Natasha (один раз при импорте)
# ──────────────────────────────────────────────
_segmenter = Segmenter()
_morph_vocab = MorphVocab()
_emb = NewsEmbedding()
_morph_tagger = NewsMorphTagger(_emb)
_ner_tagger = NewsNERTagger(_emb)
_names_extractor = NamesExtractor(_morph_vocab)


# ──────────────────────────────────────────────
# Регулярные выражения для структурированных ПДн
# ──────────────────────────────────────────────
_PATTERNS: dict[str, re.Pattern] = {
    # Паспорт РФ: серия + номер (4 2 6 цифр или 10 подряд)
    "ПАСПОРТ": re.compile(
        r"\b(\d{4}[\s\-]?\d{6})\b"
    ),
    # ИНН физлица (12 цифр) и юрлица (10 цифр)
    "ИНН": re.compile(
        r"\bИНН[:\s]*(\d{10,12})\b", re.IGNORECASE
    ),
    # СНИЛС: 000-000-000 00
    "СНИЛС": re.compile(
        r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b"
    ),
    # Телефоны РФ
    "ТЕЛЕФОН": re.compile(
        r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
    ),
    # Email
    "EMAIL": re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    ),
    # Дата рождения (явный маркер)
    "ДАТА_РОЖДЕНИЯ": re.compile(
        r"(?:дата?\s+рождения|д\.р\.|ДР)[:\s]*\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}",
        re.IGNORECASE
    ),
    # ОГРН
    "ОГРН": re.compile(
        r"\bОГРН[:\s]*(\d{13,15})\b", re.IGNORECASE
    ),
    # Расчётный счёт
    "СЧЁТ": re.compile(
        r"\b\d{5}[\s\-]?\d{3}[\s\-]?\d{1}[\s\-]?\d{4}[\s\-]?\d{7}\b"
    ),
    # Адрес (упрощённый паттерн)
    "АДРЕС": re.compile(
        r"(?:г\.|город|ул\.|улица|пр\.|проспект|д\.|дом|кв\.|квартира)"
        r"[\s]*.{2,60}(?=\n|,|\.|;|$)",
        re.IGNORECASE
    ),
}


@dataclass
class AnonymizationResult:
    original_text: str
    anonymized_text: str
    entities_found: dict[str, list[str]] = field(default_factory=dict)
    total_replacements: int = 0
    warnings: list[str] = field(default_factory=list)


class Anonymizer:
    """
    Двухуровневая анонимизация:
    1. NER через Natasha (ФИО, организации, локации)
    2. Regex для структурированных ПДн (ИНН, СНИЛС, телефон и т.д.)
    """

    PLACEHOLDER = {
        "PER": "[ФИО]",
        "ORG": "[ОРГАНИЗАЦИЯ]",
        "LOC": "[АДРЕС]",
        "ПАСПОРТ": "[ПАСПОРТ]",
        "ИНН": "[ИНН]",
        "СНИЛС": "[СНИЛС]",
        "ТЕЛЕФОН": "[ТЕЛЕФОН]",
        "EMAIL": "[EMAIL]",
        "ДАТА_РОЖДЕНИЯ": "[ДАТА РОЖДЕНИЯ]",
        "ОГРН": "[ОГРН]",
        "СЧЁТ": "[БАНК. СЧЁТ]",
        "АДРЕС": "[АДРЕС]",
    }

    def anonymize(self, text: str) -> AnonymizationResult:
        if not text or not text.strip():
            return AnonymizationResult(
                original_text=text,
                anonymized_text=text,
                warnings=["Получен пустой текст"]
            )

        entities_found: dict[str, list[str]] = {}
        total = 0

        # ── Шаг 1: NER через Natasha ──────────────────────────────
        processed, ner_entities, ner_count = self._apply_ner(text)
        entities_found.update(ner_entities)
        total += ner_count

        # ── Шаг 2: Regex ──────────────────────────────────────────
        processed, regex_entities, regex_count = self._apply_regex(processed)
        for k, v in regex_entities.items():
            entities_found.setdefault(k, []).extend(v)
        total += regex_count

        return AnonymizationResult(
            original_text=text,
            anonymized_text=processed,
            entities_found=entities_found,
            total_replacements=total,
        )

    def _apply_ner(self, text: str) -> tuple[str, dict, int]:
        """NER: Находит и заменяет PER / ORG / LOC."""
        entities: dict[str, list[str]] = {}
        count = 0
        result = text

        try:
            doc = Doc(text)
            doc.segment(_segmenter)
            doc.tag_morph(_morph_tagger)
            doc.tag_ner(_ner_tagger)

            # Сортируем по позиции в обратном порядке, чтобы не сбивать индексы
            spans = sorted(doc.spans, key=lambda s: s.start, reverse=True)

            for span in spans:
                if span.type in self.PLACEHOLDER:
                    original = result[span.start:span.stop]
                    placeholder = self.PLACEHOLDER[span.type]
                    result = result[:span.start] + placeholder + result[span.stop:]
                    entities.setdefault(span.type, []).append(original)
                    count += 1
        except Exception as e:
            logger.warning(f"NER ошибка: {e}")

        return result, entities, count

    def _apply_regex(self, text: str) -> tuple[str, dict, int]:
        """Regex: структурированные ПДн."""
        entities: dict[str, list[str]] = {}
        count = 0
        result = text

        for label, pattern in _PATTERNS.items():
            matches = pattern.findall(result)
            if matches:
                entities[label] = [str(m) for m in matches]
                count += len(matches)
                result = pattern.sub(self.PLACEHOLDER.get(label, f"[{label}]"), result)

        return result, entities, count


# Singleton
anonymizer = Anonymizer()
