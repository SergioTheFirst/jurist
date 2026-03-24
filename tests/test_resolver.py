"""Тесты модуля разрешения перекрывающихся span'ов."""

from __future__ import annotations

from legaldesk.anonymizer.models import DetectedSpan, EntityType
from legaldesk.anonymizer.resolver import resolve_overlaps


def _span(
    start: int,
    end: int,
    source: str = "regex",
    entity_type: EntityType = EntityType.PERSON,
) -> DetectedSpan:
    return DetectedSpan(
        text="x" * (end - start),
        entity_type=entity_type,
        start=start,
        end=end,
        source=source,  # type: ignore[arg-type]
    )


def test_no_overlaps() -> None:
    """Непересекающиеся span'ы — все остаются."""
    spans = [_span(0, 5), _span(10, 15), _span(20, 25)]
    result = resolve_overlaps(spans)
    assert len(result) == 3
    assert result[0].start == 0
    assert result[1].start == 10
    assert result[2].start == 20


def test_full_overlap_keeps_larger() -> None:
    """Span внутри другого → остаётся больший."""
    large = _span(0, 20, source="regex")
    small = _span(5, 15, source="llm")
    result = resolve_overlaps([large, small])
    assert len(result) == 1
    assert result[0].start == 0
    assert result[0].end == 20


def test_partial_overlap_keeps_larger_coverage() -> None:
    """Частичное пересечение → побеждает span с большим покрытием."""
    a = _span(0, 10, source="regex")   # coverage=10
    b = _span(5, 20, source="regex")   # coverage=15
    result = resolve_overlaps([a, b])
    assert len(result) == 1
    assert result[0].start == 5
    assert result[0].end == 20


def test_equal_coverage_llm_wins() -> None:
    """При равном покрытии LLM побеждает regex."""
    regex_span = _span(0, 10, source="regex")
    llm_span = _span(0, 10, source="llm")
    result = resolve_overlaps([regex_span, llm_span])
    assert len(result) == 1
    assert result[0].source == "llm"


def test_non_overlapping_preserved_sorted() -> None:
    """Результат отсортирован по start."""
    spans = [_span(20, 25), _span(0, 5), _span(10, 15)]
    result = resolve_overlaps(spans)
    starts = [s.start for s in result]
    assert starts == sorted(starts)


def test_empty_input() -> None:
    """Пустой список → пустой результат."""
    assert resolve_overlaps([]) == []


def test_adjacent_spans_not_overlapping() -> None:
    """Смежные span'ы (end одного == start другого) не считаются пересекающимися."""
    a = _span(0, 5)
    b = _span(5, 10)
    result = resolve_overlaps([a, b])
    assert len(result) == 2
