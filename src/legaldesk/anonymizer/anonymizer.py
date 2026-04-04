"""Главный pipeline анонимизации: regex + LLM → токены."""

from __future__ import annotations

from legaldesk.anonymizer.config import AnonymizerConfig
from legaldesk.anonymizer.dict_detector import detect_names, detect_vehicles
from legaldesk.anonymizer.llm_client import OllamaClient
from legaldesk.anonymizer.mapping import TokenMapping
from legaldesk.anonymizer.models import AnonymizationResult, DetectedSpan
from legaldesk.anonymizer.regex_patterns import ALL_PATTERNS
from legaldesk.anonymizer.resolver import resolve_overlaps


def anonymize(
    text: str,
    config: AnonymizerConfig | None = None,
) -> AnonymizationResult:
    """Анонимизировать текст: regex + LLM → токены [ENTITY_TYPE_001].

    Args:
        text: Исходный текст с ПДн.
        config: Конфигурация (если None — загружается из окружения).

    Returns:
        AnonymizationResult с анонимизированным текстом и маппингом.
    """
    if config is None:
        config = AnonymizerConfig()

    # Шаг 1: regex-детекция
    regex_spans = _detect_with_regex(text)

    # Шаг 2: словарная детекция (офлайн, без сети)
    dict_spans = _detect_with_dicts(text)

    # Шаг 3: LLM-детекция
    llm_spans: list[DetectedSpan] = []
    degraded = False
    if config.use_llm:
        client = OllamaClient(config)
        llm_spans, degraded = client.detect(text)

    # Шаг 4: объединение и устранение перекрытий (LLM > dict > regex)
    all_spans = resolve_overlaps(regex_spans + dict_spans + llm_spans)

    # Шаг 4: генерация токенов и замена (с конца текста, чтобы не сдвигать индексы)
    original_to_token: dict[str, str] = {}
    token_to_original: dict[str, str] = {}
    counters: dict[str, int] = {}

    anonymized = text
    for span in sorted(all_spans, key=lambda s: s.start, reverse=True):
        original = span.text
        et = span.entity_type.value
        if original not in original_to_token:
            counters[et] = counters.get(et, 0) + 1
            token = f"[{et}_{counters[et]:03d}]"
            original_to_token[original] = token
            token_to_original[token] = original
        token = original_to_token[original]
        anonymized = anonymized[: span.start] + token + anonymized[span.end :]

    return AnonymizationResult(
        original_text=text,
        anonymized_text=anonymized,
        spans=all_spans,
        mapping=token_to_original,
        reverse_mapping=original_to_token,
        degraded=degraded,
    )


def deanonymize(text: str, mapping: dict[str, str]) -> str:
    """Восстановить ПДн: заменить токены обратно на оригиналы.

    Args:
        text: Анонимизированный текст с токенами.
        mapping: Словарь token → original (поле AnonymizationResult.mapping).

    Returns:
        Текст с восстановленными ПДн.
    """
    result = text
    for token, original in mapping.items():
        result = result.replace(token, original)
    return result


def anonymize_with_regex(text: str) -> tuple[str, TokenMapping]:
    """Regex-only анонимизация. Обратно совместимая обёртка.

    Returns:
        (анонимизированный текст, маппинг для обратной подстановки).
    """
    mapping = TokenMapping()
    result = text

    regex_spans = _detect_with_regex(text)
    resolved = resolve_overlaps(regex_spans)

    for span in sorted(resolved, key=lambda s: s.start, reverse=True):
        original = span.text
        entity_key = span.entity_type.value
        token = mapping.add(original, entity_key)
        result = result[: span.start] + token + result[span.end :]

    return result, mapping


def _detect_with_dicts(text: str) -> list[DetectedSpan]:
    """Запустить словарную детекцию и вернуть список DetectedSpan."""
    return detect_vehicles(text) + detect_names(text)


def _detect_with_regex(text: str) -> list[DetectedSpan]:
    """Запустить все regex-паттерны и вернуть список DetectedSpan."""
    spans: list[DetectedSpan] = []
    for entity_type, pattern in ALL_PATTERNS.items():
        for match in pattern.finditer(text):
            spans.append(
                DetectedSpan(
                    text=match.group(),
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    source="regex",
                )
            )
    return spans
