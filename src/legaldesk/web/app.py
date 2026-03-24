"""Flask-приложение LegalDesk — Web UI с Review Gate."""

from __future__ import annotations

import html as html_mod
import re
from typing import Any

from flask import Flask, redirect, render_template, request
from markupsafe import Markup
from werkzeug.wrappers import Response

from legaldesk.anonymizer.anonymizer import anonymize
from legaldesk.anonymizer.models import AnonymizationResult, DetectedSpan, EntityType
from legaldesk.anonymizer.resolver import resolve_overlaps
from legaldesk.legal_engine.provider import SearchResult
from legaldesk.legal_engine.stub_provider import StubProvider
from legaldesk.web.session_store import review_store

# ---------------------------------------------------------------------------
# Вспомогательные функции (не логируют текст — Статья 2 CONSTITUTION)
# ---------------------------------------------------------------------------

def _annotate_original(text: str, spans: list[DetectedSpan]) -> Markup:
    """Обернуть каждый span в <mark class="pdn"> для отображения исходника."""
    sorted_spans = sorted(spans, key=lambda s: s.start)
    parts: list[str] = []
    prev = 0
    for span in sorted_spans:
        parts.append(html_mod.escape(text[prev : span.start]))
        parts.append(f'<mark class="pdn">{html_mod.escape(span.text)}</mark>')
        prev = span.end
    parts.append(html_mod.escape(text[prev:]))
    return Markup("".join(parts))


def _annotate_anonymized(text: str) -> Markup:
    """Обернуть токены [TYPE_NNN] в <mark class="token">."""
    escaped = html_mod.escape(text)
    marked = re.sub(
        r"(\[[A-Z_]+_\d{3}\])",
        r'<mark class="token">\1</mark>',
        escaped,
    )
    return Markup(marked)


def _render_review_page(result: AnonymizationResult, error: str = "") -> str:
    """Сформировать страницу проверки замен."""
    return render_template(
        "review.html",
        spans=result.spans,
        reverse_mapping=result.reverse_mapping,
        original_html=_annotate_original(result.original_text, result.spans),
        anonymized_html=_annotate_anonymized(result.anonymized_text),
        degraded=result.degraded,
        entity_types=[et.value for et in EntityType],
        error=error,
    )


def _compute_approved_text(
    original_text: str,
    spans: list[DetectedSpan],
    reverse_mapping: dict[str, str],
    selected_span_ids: set[str],
    manual_text: str,
    manual_type: str,
) -> str:
    """Пересчитать approved_text на основе выбранных span'ов и ручной замены.

    НИКОГДА не вызывается с логированием аргументов — они могут содержать ПДн.
    """
    selected: list[DetectedSpan] = [
        s for s in spans if s.span_id in selected_span_ids
    ]

    if manual_text and manual_type:
        pos = original_text.find(manual_text)
        if pos >= 0:
            try:
                et = EntityType(manual_type)
                selected.append(
                    DetectedSpan(
                        text=manual_text,
                        entity_type=et,
                        start=pos,
                        end=pos + len(manual_text),
                        source="manual",
                    )
                )
            except ValueError:
                pass  # Неизвестный тип — игнорируем

    resolved = resolve_overlaps(selected)

    approved = original_text
    for span in sorted(resolved, key=lambda s: s.start, reverse=True):
        token = reverse_mapping.get(span.text, f"[{span.entity_type.value}_MANUAL]")
        approved = approved[: span.start] + token + approved[span.end :]

    return approved


# ---------------------------------------------------------------------------
# Flask app factory
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    """Фабрика Flask-приложения."""
    app = Flask(__name__)

    @app.route("/")
    def index() -> str:
        """Экран 1: ввод текста обращения."""
        return render_template("input.html", error="", text_value="")

    @app.route("/anonymize", methods=["POST"])
    def anonymize_view() -> Response:
        """Принять текст, анонимизировать, сохранить сессию, редирект на /review."""
        text = request.form.get("text", "")
        if not text.strip():
            return Response(
                render_template("input.html", error="Введите текст", text_value=text),
                status=200,
            )

        result = anonymize(text)
        data: dict[str, Any] = result.model_dump(mode="json")
        review_id = review_store.create(data)

        resp = redirect("/review")
        resp.set_cookie(
            "review_id",
            review_id,
            httponly=True,
            samesite="Lax",
            max_age=3600,
        )
        return resp

    @app.route("/review")
    def review_view() -> str | Response:
        """Экран 2: проверка замен."""
        review_id = request.cookies.get("review_id")
        if not review_id:
            return redirect("/")

        raw = review_store.get(review_id)
        if raw is None:
            return redirect("/")

        result = AnonymizationResult.model_validate(raw)
        return _render_review_page(result)

    @app.route("/approve", methods=["POST"])
    def approve_view() -> str | Response:
        """Принять одобренные замены, отправить на анализ, редирект на /result."""
        review_id = request.cookies.get("review_id")
        if not review_id:
            return redirect("/")

        raw = review_store.get(review_id)
        if raw is None:
            return redirect("/")

        result = AnonymizationResult.model_validate(raw)

        degraded_confirm = request.form.get("degraded_confirm") is not None
        if result.degraded and not degraded_confirm:
            return _render_review_page(
                result,
                error="Подтвердите проверку замен вручную",
            )

        selected_ids: set[str] = set(request.form.getlist("selected_span_ids"))
        manual_text = request.form.get("manual_text", "") or ""
        manual_type = request.form.get("manual_type", "") or ""

        approved_text = _compute_approved_text(
            original_text=result.original_text,
            spans=result.spans,
            reverse_mapping=result.reverse_mapping,
            selected_span_ids=selected_ids,
            manual_text=manual_text,
            manual_type=manual_type,
        )

        search_results: list[SearchResult] = StubProvider().search(approved_text)

        updated: dict[str, Any] = {
            **raw,
            "approved_text": approved_text,
            "search_results": [r.model_dump(mode="json") for r in search_results],
        }
        review_store.update(review_id, updated)

        return redirect("/result")

    @app.route("/result")
    def result_view() -> str | Response:
        """Экран 3: результат с нормами права."""
        review_id = request.cookies.get("review_id")
        if not review_id:
            return redirect("/")

        raw = review_store.get(review_id)
        if raw is None or "approved_text" not in raw:
            return redirect("/")

        original_text: str = str(raw.get("original_text", ""))
        raw_results: list[Any] = list(raw.get("search_results", []))
        search_results = [SearchResult.model_validate(r) for r in raw_results]

        return render_template(
            "result.html",
            original_text=original_text,
            results=search_results,
        )

    @app.route("/new")
    def new_view() -> Response:
        """Очистить сессию и начать новый запрос."""
        review_id = request.cookies.get("review_id")
        if review_id:
            review_store.delete(review_id)

        resp = redirect("/")
        resp.delete_cookie("review_id")
        return resp

    return app
