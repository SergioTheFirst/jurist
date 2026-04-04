"""Разрешение перекрывающихся span'ов — выбор лучшего при конфликте."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from legaldesk.anonymizer.models import DetectedSpan


def resolve_overlaps(spans: list[DetectedSpan]) -> list[DetectedSpan]:
    """Убрать пересечения: при конфликте побеждает больший span, при равенстве — LLM.

    Args:
        spans: Список span'ов (может содержать пересечения).

    Returns:
        Отсортированный по start список без пересекающихся span'ов.
    """
    if not spans:
        return []

    # Сортируем по start, затем по убыванию покрытия, затем LLM > dict > regex
    source_priority_map = {"llm": 0, "dict": 1, "regex": 2, "manual": 0}

    def sort_key(s: DetectedSpan) -> tuple[int, int, int]:
        coverage = s.end - s.start
        source_priority = source_priority_map.get(s.source, 3)
        return (s.start, -coverage, source_priority)

    sorted_spans = sorted(spans, key=sort_key)

    accepted: list[DetectedSpan] = []

    for candidate in sorted_spans:
        conflict_idx = _find_conflict(accepted, candidate)

        if conflict_idx == -1:
            accepted.append(candidate)
            continue

        incumbent = accepted[conflict_idx]
        incumbent_cov = incumbent.end - incumbent.start
        candidate_cov = candidate.end - candidate.start

        should_replace = candidate_cov > incumbent_cov or (
            candidate_cov == incumbent_cov and _llm_beats(candidate, incumbent)
        )
        if should_replace:
            accepted[conflict_idx] = candidate
        # else: incumbent wins, do nothing

    return sorted(accepted, key=lambda s: s.start)


def _find_conflict(accepted: list[DetectedSpan], candidate: DetectedSpan) -> int:
    """Вернуть индекс первого пересекающегося span'а или -1."""
    for i, acc in enumerate(accepted):
        if candidate.start < acc.end and candidate.end > acc.start:
            return i
    return -1


_PRIORITY_MAP: dict[str, int] = {"llm": 0, "dict": 1, "regex": 2, "manual": 0}


def _llm_beats(a: DetectedSpan, b: DetectedSpan) -> bool:
    """Истина, если a имеет более высокий приоритет источника, чем b."""
    return _PRIORITY_MAP.get(a.source, 3) < _PRIORITY_MAP.get(b.source, 3)
