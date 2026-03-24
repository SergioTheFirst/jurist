"""Tests for HTML highlight helpers."""

from __future__ import annotations

from legaldesk.anonymizer.models import DetectedSpan, EntityType
from legaldesk.web.helpers import highlight_spans, highlight_tokens


def test_highlight_spans_wraps_mark() -> None:
    """Detected spans are wrapped in <mark class="pdn">."""
    text = "Иванов Иван получил штраф"
    spans = [
        DetectedSpan(
            text="Иванов Иван",
            entity_type=EntityType.PERSON,
            start=0,
            end=11,
            source="llm",
        ),
    ]
    result = str(highlight_spans(text, spans))
    assert '<mark class="pdn"' in result
    assert "Иванов Иван" in result
    assert "получил штраф" in result


def test_highlight_escapes_html() -> None:
    """HTML special chars in text are escaped, preventing XSS."""
    text = "<script>alert(1)</script> Иванов"
    spans = [
        DetectedSpan(
            text="Иванов",
            entity_type=EntityType.PERSON,
            start=26,
            end=32,
            source="llm",
        ),
    ]
    result = str(highlight_spans(text, spans))
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
    assert '<mark class="pdn"' in result


def test_highlight_empty_spans() -> None:
    """Empty spans list returns escaped text unchanged."""
    text = "Обычный текст"
    result = str(highlight_spans(text, []))
    assert result == "Обычный текст"


def test_highlight_tokens_wraps_tokens() -> None:
    """Anonymisation tokens [TYPE_NNN] are wrapped in <mark class="token">."""
    text = "[PERSON_001] получил штраф, ИНН [INN_001]"
    result = str(highlight_tokens(text))
    assert '<mark class="token">[PERSON_001]</mark>' in result
    assert '<mark class="token">[INN_001]</mark>' in result
    assert "получил штраф" in result


def test_highlight_tokens_escapes_html() -> None:
    """HTML in token text is escaped."""
    text = "<b>bold</b> [PERSON_001]"
    result = str(highlight_tokens(text))
    assert "<b>" not in result
    assert "&lt;b&gt;" in result
    assert '<mark class="token">[PERSON_001]</mark>' in result
