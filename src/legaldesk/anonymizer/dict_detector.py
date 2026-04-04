"""Детектор ПДн на основе словарей: ТС и имена/фамилии."""

from __future__ import annotations

import re

from legaldesk.anonymizer.dictionaries.names import FIRST_NAMES, PATRONYMICS, SURNAMES
from legaldesk.anonymizer.dictionaries.vehicles import (
    VEHICLE_BRANDS,
    VEHICLE_CONTEXT_WORDS,
    VEHICLE_MODELS,
)
from legaldesk.anonymizer.models import DetectedSpan, EntityType

# Предкомпилируем regex для ускорения поиска отдельных слов
_WORD_PATTERN = re.compile(r"\b\S+\b", re.UNICODE)
_VEHICLE_MAX_WORDS = 3   # максимальная длина наименования марки+модели в словах

# Окно контекста (символов), в котором ищем контекстные слова для ТС
_VEHICLE_CONTEXT_WINDOW = 120

# Окно (символов) для поиска отчества рядом с именем/фамилией
_PERSON_CONTEXT_WINDOW = 80

# Предварительно нормализованные (lowercase) версии словарей для поиска
_BRANDS_LOWER: frozenset[str] = frozenset(b.lower() for b in VEHICLE_BRANDS)
_MODELS_LOWER: frozenset[str] = frozenset(m.lower() for m in VEHICLE_MODELS)
_CONTEXT_LOWER: frozenset[str] = frozenset(w.lower() for w in VEHICLE_CONTEXT_WORDS)


def detect_vehicles(text: str) -> list[DetectedSpan]:
    """Найти марки и модели ТС в тексте с помощью словаря.

    Алгоритм:
    1. Скользящее окно 1–3 слова по тексту.
    2. Проверка вхождения в VEHICLE_BRANDS или VEHICLE_MODELS.
    3. Валидация контекста: рядом должно быть ключевое слово из VEHICLE_CONTEXT_WORDS.

    Args:
        text: Исходный текст.

    Returns:
        Список DetectedSpan с entity_type=VEHICLE_MAKE_MODEL.
    """
    spans: list[DetectedSpan] = []
    text_lower = text.lower()

    # Собираем позиции всех токенов (слово → (start, end))
    tokens: list[tuple[str, int, int]] = [
        (m.group(), m.start(), m.end()) for m in _WORD_PATTERN.finditer(text)
    ]

    # Строим набор контекстных позиций один раз (используем нормализованные слова)
    context_positions = _find_context_positions(text_lower, _CONTEXT_LOWER)

    used_positions: set[int] = set()  # стартовые позиции уже принятых span'ов

    for i in range(len(tokens)):
        # Пробуем от самых длинных фраз к коротким, чтобы захватить «Toyota Camry»
        for window in range(min(_VEHICLE_MAX_WORDS, len(tokens) - i), 0, -1):
            window_tokens = tokens[i : i + window]
            phrase = " ".join(t[0] for t in window_tokens)
            phrase_lower = phrase.lower()
            start = window_tokens[0][1]
            end = window_tokens[-1][2]

            # Проверяем перекрытие с уже принятыми
            if any(start <= p < end or p <= start < p + 1 for p in used_positions):
                continue

            if phrase_lower not in _BRANDS_LOWER and phrase_lower not in _MODELS_LOWER:
                continue

            # Проверка контекста
            if _has_nearby_context(start, end, context_positions, len(text)):
                spans.append(
                    DetectedSpan(
                        text=phrase,
                        entity_type=EntityType.VEHICLE_MAKE_MODEL,
                        start=start,
                        end=end,
                        source="dict",
                    )
                )
                for pos in range(start, end):
                    used_positions.add(pos)
                break  # нашли лучшее (самое длинное) совпадение для этой позиции

    return spans


def detect_names(text: str) -> list[DetectedSpan]:
    """Найти имена, фамилии и отчества в тексте с помощью словаря.

    Алгоритм:
    1. Перебираем слова с заглавной буквы.
    2. Проверяем принадлежность к FIRST_NAMES, SURNAMES, PATRONYMICS.
    3. Пытаемся сформировать полное ФИО (2–3 компонента подряд).

    Args:
        text: Исходный текст.

    Returns:
        Список DetectedSpan с entity_type=PERSON.
    """
    spans: list[DetectedSpan] = []
    tokens: list[tuple[str, int, int]] = [
        (m.group(), m.start(), m.end()) for m in _WORD_PATTERN.finditer(text)
    ]

    used_positions: set[int] = set()

    i = 0
    while i < len(tokens):
        word, start, end = tokens[i]

        # Пропускаем служебные слова и уже покрытые позиции
        if start in used_positions or not word[0].isupper():
            i += 1
            continue

        # Пытаемся собрать ФИО из 2–3 токенов (вперёд)
        matched_len = _try_match_fio(tokens, i, used_positions)
        if matched_len > 0:
            name_tokens = tokens[i : i + matched_len]
            name_text = " ".join(t[0] for t in name_tokens)
            name_start = name_tokens[0][1]
            name_end = name_tokens[-1][2]
            spans.append(
                DetectedSpan(
                    text=name_text,
                    entity_type=EntityType.PERSON,
                    start=name_start,
                    end=name_end,
                    source="dict",
                )
            )
            for pos in range(name_start, name_end):
                used_positions.add(pos)
            i += matched_len
        else:
            i += 1

    return spans


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _find_context_positions(
    text_lower: str, context_words: frozenset[str]
) -> list[int]:
    """Вернуть список позиций, где встречаются контекстные слова."""
    positions: list[int] = []
    for word in context_words:
        pos = 0
        while True:
            idx = text_lower.find(word, pos)
            if idx == -1:
                break
            positions.append(idx)
            pos = idx + 1
    return positions


def _has_nearby_context(
    start: int, end: int, context_positions: list[int], text_len: int
) -> bool:
    """Проверить, есть ли контекстное слово рядом со span'ом."""
    window_start = max(0, start - _VEHICLE_CONTEXT_WINDOW)
    window_end = min(text_len, end + _VEHICLE_CONTEXT_WINDOW)
    return any(window_start <= pos <= window_end for pos in context_positions)


def _is_name_word(word: str) -> bool:
    """Слово принадлежит к именам, фамилиям или отчествам."""
    return word in FIRST_NAMES or word in SURNAMES or word in PATRONYMICS


def _try_match_fio(
    tokens: list[tuple[str, int, int]],
    start_idx: int,
    used_positions: set[int],
) -> int:
    """Определить длину ФИО-цепочки начиная с tokens[start_idx].

    Returns:
        Количество токенов, входящих в ФИО (0 если ни одного).
    """
    max_idx = min(start_idx + 3, len(tokens))  # ФИО — максимум 3 слова
    result = 0
    for j in range(start_idx, max_idx):
        word, pos_start, pos_end = tokens[j]
        # Токены должны быть соседними (не через символы за пределами пробелов)
        if j > start_idx:
            prev_end = tokens[j - 1][2]
            # Допускаем только пробелы между компонентами ФИО
            if pos_start - prev_end > 2:
                break
        if pos_start in used_positions:
            break
        if not word[0].isupper():
            break
        if _is_name_word(word):
            result = j - start_idx + 1
        else:
            # Незнакомое слово прерывает цепочку ФИО
            break
    return result
