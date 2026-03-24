"""HTML helpers for rendering annotated text in templates.

SECURITY CONTRACT: these functions receive already-processed data (spans/tokens),
never raw PII mapping values. All user-supplied text is escaped via markupsafe.
"""

import re

from markupsafe import Markup, escape

from legaldesk.anonymizer.models import DetectedSpan


def highlight_spans(
    text: str,
    spans: list[DetectedSpan],
    css_class: str = "pdn",
) -> Markup:
    """Wrap detected spans in <mark> tags for display.

    Assumes spans do not overlap. Processes from end to start so indices remain
    valid as text grows.

    Args:
        text: Original plain text.
        spans: Detected spans to highlight.
        css_class: CSS class for the <mark> element.

    Returns:
        Markup with spans wrapped in <mark class="{css_class}" title="{entity_type}">.
    """
    # Sort descending by start position so insertions don't shift earlier indices
    sorted_spans = sorted(spans, key=lambda s: s.start, reverse=True)

    # Work character-by-character; build output list of escaped chunks
    # Strategy: split text at span boundaries, escape each chunk, wrap span chunks
    result_parts: list[str] = []
    cursor = len(text)

    for span in sorted_spans:
        if span.end > len(text) or span.start < 0 or span.start >= span.end:
            continue
        # Tail after this span
        tail = str(escape(text[span.end:cursor]))
        span_text = str(escape(text[span.start:span.end]))
        entity_label = str(escape(span.entity_type.value))
        mark = f'<mark class="{css_class}" title="{entity_label}">{span_text}</mark>'
        result_parts.append(tail)
        result_parts.append(mark)
        cursor = span.start

    # Prepend the remaining head (before first span)
    head = str(escape(text[:cursor]))
    result_parts.append(head)

    return Markup("".join(reversed(result_parts)))


def highlight_tokens(text: str) -> Markup:
    """Find anonymisation tokens like [PERSON_001] and wrap in <mark class="token">.

    Args:
        text: Anonymised plain text possibly containing tokens.

    Returns:
        Markup with tokens wrapped in <mark class="token">.
    """
    token_re = re.compile(r"(\[[A-Z_]+_\d+\])")
    parts: list[str] = []
    last = 0
    for match in token_re.finditer(text):
        # Escape text before match
        parts.append(str(escape(text[last:match.start()])))
        token = str(escape(match.group(1)))
        parts.append(f'<mark class="token">{token}</mark>')
        last = match.end()
    parts.append(str(escape(text[last:])))
    return Markup("".join(parts))
