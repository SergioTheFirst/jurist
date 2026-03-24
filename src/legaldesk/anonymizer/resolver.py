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

    # Сортируем по start, затем по убыванию покрытия, затем LLM > regex
    def sort_key(s: DetectedSpan) -> tuple[int, int, int]:
        coverage = s.end - s.start
        source_priority = 0 if s.source == "llm" else 1
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


def _llm_beats(a: DetectedSpan, b: DetectedSpan) -> bool:
    """Истина, если a является LLM-источником, а b — regex."""
    return a.source == "llm" and b.source == "regex"
