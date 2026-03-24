"""Flask application factory for LegalDesk."""

from __future__ import annotations

import logging
import os
import secrets
from typing import TYPE_CHECKING, Any

import httpx
from flask import Flask, jsonify, redirect, render_template, request

if TYPE_CHECKING:
    from werkzeug.wrappers import Response

from legaldesk.anonymizer.anonymizer import anonymize
from legaldesk.anonymizer.config import AnonymizerConfig
from legaldesk.anonymizer.models import AnonymizationResult, DetectedSpan, EntityType
from legaldesk.anonymizer.resolver import resolve_overlaps
from legaldesk.legal_engine.provider import SearchResult
from legaldesk.legal_engine.stub_provider import StubProvider
from legaldesk.logging_config import setup_logging
from legaldesk.web.helpers import highlight_spans, highlight_tokens
from legaldesk.web.session_store import review_store

logger = logging.getLogger("legaldesk.web")

_MAX_TEXT_LENGTH = 50_000


# ---------------------------------------------------------------------------
# Internal helpers (never log PII — security contract)
# ---------------------------------------------------------------------------


def _render_review_page(result: AnonymizationResult, error: str = "") -> str:
    """Render the review gate page with annotated text and span table."""
    highlighted_original = highlight_spans(result.original_text, result.spans)
    highlighted_anonymized = highlight_tokens(result.anonymized_text)

    regex_count = sum(1 for s in result.spans if s.source == "regex")
    llm_count = sum(1 for s in result.spans if s.source == "llm")

    return render_template(
        "review.html",
        spans=result.spans,
        reverse_mapping=result.reverse_mapping,
        highlighted_original=highlighted_original,
        highlighted_anonymized=highlighted_anonymized,
        degraded=result.degraded,
        entity_types=[et.value for et in EntityType],
        error=error,
        regex_count=regex_count,
        llm_count=llm_count,
    )


def _compute_approved_text(
    original_text: str,
    spans: list[DetectedSpan],
    reverse_mapping: dict[str, str],
    selected_span_ids: set[str],
    manual_text: str,
    manual_type: str,
) -> str:
    """Rebuild approved text from selected spans and optional manual replacement.

    NEVER called with argument logging — may contain PII.
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
                pass

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
    """Create and configure the Flask application."""
    setup_logging()

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024

    secret_key = os.environ.get("LEGALDESK_SECRET_KEY")
    if secret_key:
        app.secret_key = secret_key
    else:
        app.secret_key = secrets.token_hex(32)
        logger.warning(
            "Using generated secret key, sessions will not persist across restarts. "
            "Set LEGALDESK_SECRET_KEY env variable to fix this."
        )

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.route("/")
    def index() -> str:
        """Screen 1: text input."""
        return render_template("input.html", error="", text_value="")

    @app.route("/anonymize", methods=["POST"])
    def anonymize_view() -> str | Response:
        """Receive text, anonymise, store session, redirect to /review."""
        text = request.form.get("text", "")

        if not text.strip():
            return render_template("input.html", error="Введите текст обращения", text_value=text)

        if len(text) > _MAX_TEXT_LENGTH:
            return render_template(
                "input.html",
                error=f"Текст слишком длинный (максимум {_MAX_TEXT_LENGTH:,} символов)",
                text_value=text,
            )

        try:
            result = anonymize(text)
        except Exception:
            logger.exception("anonymize() failed (span count unknown)")
            return render_template(
                "input.html",
                error="Ошибка при анонимизации текста. Попробуйте ещё раз.",
                text_value=text,
            )

        logger.info("anonymize: spans_found=%d degraded=%s", len(result.spans), result.degraded)

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
        """Screen 2: review detected spans."""
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
        """Accept approved replacements, run search, redirect to /result."""
        review_id = request.cookies.get("review_id")
        if not review_id:
            return redirect("/")

        raw = review_store.get(review_id)
        if raw is None:
            return redirect("/")

        result = AnonymizationResult.model_validate(raw)

        degraded_confirm = request.form.get("degraded_confirm") is not None
        if result.degraded and not degraded_confirm:
            return _render_review_page(result, error="Подтвердите проверку замен вручную")

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

        try:
            search_results: list[SearchResult] = StubProvider().search(approved_text)
        except Exception:
            logger.exception("search() failed")
            return _render_review_page(
                result, error="Ошибка при поиске норм права. Попробуйте ещё раз."
            )

        logger.info("search: results_count=%d", len(search_results))

        updated: dict[str, Any] = {
            **raw,
            "approved_text": approved_text,
            "search_results": [r.model_dump(mode="json") for r in search_results],
        }
        review_store.update(review_id, updated)

        return redirect("/result")

    @app.route("/result")
    def result_view() -> str | Response:
        """Screen 3: legal search results with PII restored."""
        review_id = request.cookies.get("review_id")
        if not review_id:
            return redirect("/")

        raw = review_store.get(review_id)
        if raw is None or "approved_text" not in raw:
            return redirect("/")

        original_text: str = str(raw.get("original_text", ""))
        raw_results: list[Any] = list(raw.get("search_results", []))
        search_results = [SearchResult.model_validate(r) for r in raw_results]

        logger.info("result: results_count=%d", len(search_results))

        return render_template(
            "result.html",
            original_text=original_text,
            results=search_results,
        )

    @app.route("/new")
    def new_view() -> Response:
        """Clear session and start a new request."""
        review_id = request.cookies.get("review_id")
        if review_id:
            review_store.delete(review_id)

        resp = redirect("/")
        resp.delete_cookie("review_id")
        return resp

    @app.route("/health")
    def health_view() -> str | Response:
        """System health check endpoint."""
        config = AnonymizerConfig()
        model_name = config.ollama_model

        ollama_available = False
        ollama_model_loaded = False
        try:
            r = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
            if r.status_code == 200:
                ollama_available = True
                data = r.json()
                loaded_models: list[str] = [
                    m.get("name", "") for m in data.get("models", [])
                ]
                ollama_model_loaded = any(
                    m == model_name or m.startswith(model_name.split(":")[0])
                    for m in loaded_models
                )
        except Exception:
            pass

        degraded = not ollama_model_loaded
        logger.info(
            "health: ollama_available=%s ollama_model_loaded=%s degraded=%s",
            ollama_available,
            ollama_model_loaded,
            degraded,
        )

        payload: dict[str, object] = {
            "status": "ok",
            "version": "0.2.0",
            "ollama_available": ollama_available,
            "ollama_model_loaded": ollama_model_loaded,
            "configured_model": model_name,
            "degraded_mode": degraded,
            "note": "Без Ollama приложение работает в regex-only режиме",
        }
        resp: Response = jsonify(payload)
        return resp

    # ------------------------------------------------------------------
    # Error handlers
    # ------------------------------------------------------------------

    @app.errorhandler(404)
    def not_found(e: Any) -> tuple[str, int]:
        """404 handler."""
        return render_template("error.html", code=404, message="Страница не найдена"), 404

    @app.errorhandler(500)
    def internal_error(e: Any) -> tuple[str, int]:
        """500 handler."""
        return render_template("error.html", code=500, message="Внутренняя ошибка"), 500

    return app
