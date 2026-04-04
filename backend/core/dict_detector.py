"""Словарный детектор марок/моделей ТС и региональных имён (полностью офлайн).

Не зависит от Natasha / pymorphy2 — работает только с frozenset-словарями.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import uuid4

from backend.core.dictionaries.names import FIRST_NAMES, PATRONYMICS, SURNAMES
from backend.core.dictionaries.vehicles import (
    VEHICLE_BRANDS,
    VEHICLE_CONTEXT_WORDS,
    VEHICLE_MODELS,
)


@dataclass(frozen=True)
class DictSpan:
    """Span обнаруженный словарным детектором."""

    id: str
    original: str
    placeholder: str
    entity_type: str
    start: int
    end: int
    source: str
    confidence: float
    identity_key: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

# Токенизация: слово = любая непробельная последовательность
_WORD_RE = re.compile(r"\b\S+\b", re.UNICODE)

# Максимум слов в наименовании марки+модели ТС
_VEHICLE_MAX_WORDS = 3

# Окно контекста (символов) для поиска контекстных слов рядом с ТС
_VEHICLE_CONTEXT_WINDOW = 120

# Нормализованные (lowercase) версии словарей для поиска
_BRANDS_LOWER: frozenset[str] = frozenset(b.lower() for b in VEHICLE_BRANDS)
_MODELS_LOWER: frozenset[str] = frozenset(m.lower() for m in VEHICLE_MODELS)
_CONTEXT_LOWER: frozenset[str] = frozenset(w.lower() for w in VEHICLE_CONTEXT_WORDS)

# Плейсхолдер и entity_type для марки/модели ТС
_VEHICLE_PLACEHOLDER = "[МАРКА/МОДЕЛЬ ТС]"
_VEHICLE_ENTITY_TYPE = "МАРКА_ТС"


def detect_vehicles(text: str) -> list[DictSpan]:
    """Найти марки и модели ТС в тексте с помощью словаря.

    Алгоритм: скользящее окно 1–3 слова + проверка контекста.
    """
    spans: list[DictSpan] = []
    text_lower = text.lower()

    tokens: list[tuple[str, int, int]] = [
        (m.group(), m.start(), m.end()) for m in _WORD_RE.finditer(text)
    ]

    context_positions = _find_context_positions(text_lower, _CONTEXT_LOWER)
    used_ranges: list[tuple[int, int]] = []

    for i in range(len(tokens)):
        for window in range(min(_VEHICLE_MAX_WORDS, len(tokens) - i), 0, -1):
            win_tokens = tokens[i : i + window]
            phrase_lower = " ".join(t[0].lower() for t in win_tokens)
            start = win_tokens[0][1]
            end = win_tokens[-1][2]

            if _overlaps_any(start, end, used_ranges):
                continue

            if phrase_lower not in _BRANDS_LOWER and phrase_lower not in _MODELS_LOWER:
                continue

            if _has_nearby_context(start, end, context_positions, len(text)):
                original = text[start:end]
                spans.append(
                    DictSpan(
                        id=str(uuid4()),
                        original=original,
                        placeholder=_VEHICLE_PLACEHOLDER,
                        entity_type=_VEHICLE_ENTITY_TYPE,
                        start=start,
                        end=end,
                        source="dict",
                        confidence=0.90,
                    )
                )
                used_ranges.append((start, end))
                break  # нашли лучший (самый длинный) вариант для этой позиции

    return spans


def detect_names(text: str) -> list[DictSpan]:
    """Найти имена/фамилии из словаря для региональных имён, которые Natasha может пропустить.

    Natasha хорошо знает русские имена, но хуже — среднеазиатские, кавказские, тюркские.
    Этот детектор дополняет NER-результаты.
    """
    spans: list[DictSpan] = []
    tokens: list[tuple[str, int, int]] = [
        (m.group(), m.start(), m.end()) for m in _WORD_RE.finditer(text)
    ]

    used_ranges: list[tuple[int, int]] = []
    i = 0
    while i < len(tokens):
        word, start, end = tokens[i]

        if _overlaps_any(start, end, used_ranges) or not word[0].isupper():
            i += 1
            continue

        matched_len = _try_match_fio(tokens, i, used_ranges)
        if matched_len > 0:
            win = tokens[i : i + matched_len]
            name_text = " ".join(t[0] for t in win)
            name_start = win[0][1]
            name_end = win[-1][2]
            spans.append(
                DictSpan(
                    id=str(uuid4()),
                    original=name_text,
                    placeholder="[ФИО]",
                    entity_type="PER",
                    start=name_start,
                    end=name_end,
                    source="dict",
                    confidence=0.80,
                )
            )
            used_ranges.append((name_start, name_end))
            i += matched_len
        else:
            i += 1

    return spans


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _find_context_positions(text_lower: str, words: frozenset[str]) -> list[int]:
    """Позиции всех вхождений контекстных слов."""
    positions: list[int] = []
    for word in words:
        pos = 0
        while True:
            idx = text_lower.find(word, pos)
            if idx == -1:
                break
            positions.append(idx)
            pos = idx + 1
    return positions


def _has_nearby_context(
    start: int, end: int, positions: list[int], text_len: int
) -> bool:
    """Проверить, есть ли контекстное слово в окне вокруг span'а."""
    w_start = max(0, start - _VEHICLE_CONTEXT_WINDOW)
    w_end = min(text_len, end + _VEHICLE_CONTEXT_WINDOW)
    return any(w_start <= p <= w_end for p in positions)


def _overlaps_any(start: int, end: int, used: list[tuple[int, int]]) -> bool:
    return any(start < e and end > s for s, e in used)


def _is_name_word(word: str) -> bool:
    return word in FIRST_NAMES or word in SURNAMES or word in PATRONYMICS


def _try_match_fio(
    tokens: list[tuple[str, int, int]],
    start_idx: int,
    used: list[tuple[int, int]],
) -> int:
    """Вернуть длину ФИО-цепочки (0 = не ФИО)."""
    result = 0
    max_idx = min(start_idx + 3, len(tokens))
    for j in range(start_idx, max_idx):
        word, pos_start, _ = tokens[j]
        if j > start_idx:
            prev_end = tokens[j - 1][2]
            if pos_start - prev_end > 2:
                break
        if _overlaps_any(pos_start, tokens[j][2], used):
            break
        if not word[0].isupper():
            break
        if _is_name_word(word):
            result = j - start_idx + 1
        else:
            break
    return result
