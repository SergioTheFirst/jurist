"""Тесты Web UI с Review Gate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from legaldesk.anonymizer.models import AnonymizationResult, DetectedSpan, EntityType
from legaldesk.web.app import create_app
from legaldesk.web.session_store import review_store

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient


@pytest.fixture()
def app() -> Flask:
    """Создать тестовое Flask-приложение."""
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    """Тестовый клиент Flask."""
    return app.test_client()


# Фикстуры данных
_SAMPLE_TEXT = "Иванов Иван, ИНН 123456789012"

_SAMPLE_RESULT = AnonymizationResult(
    original_text=_SAMPLE_TEXT,
    anonymized_text="[PERSON_001], ИНН [INN_001]",
    spans=[
        DetectedSpan(
            text="Иванов Иван",
            entity_type=EntityType.PERSON,
            start=0,
            end=11,
            source="llm",
        ),
        DetectedSpan(
            text="123456789012",
            entity_type=EntityType.INN,
            start=17,
            end=29,
            source="regex",
        ),
    ],
    mapping={"[PERSON_001]": "Иванов Иван", "[INN_001]": "123456789012"},
    reverse_mapping={"Иванов Иван": "[PERSON_001]", "123456789012": "[INN_001]"},
    degraded=False,
)

_DEGRADED_RESULT = _SAMPLE_RESULT.model_copy(update={"degraded": True})


def _store_and_set_cookie(
    client: FlaskClient, result: AnonymizationResult
) -> str:
    """Сохранить результат в store и вернуть review_id."""
    data: dict[str, Any] = result.model_dump(mode="json")
    review_id = review_store.create(data)
    client.set_cookie("review_id", review_id, domain="localhost")
    return review_id


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------

def test_index_returns_200(client: FlaskClient) -> None:
    """GET / возвращает 200 и форму ввода."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<textarea" in resp.data


def test_anonymize_empty_text(client: FlaskClient) -> None:
    """POST /anonymize с пустым текстом показывает ошибку."""
    resp = client.post("/anonymize", data={"text": ""})
    assert resp.status_code == 200
    assert "Введите текст".encode() in resp.data


def test_anonymize_redirects_to_review(client: FlaskClient) -> None:
    """POST /anonymize с текстом — редирект на /review."""
    with patch("legaldesk.web.app.anonymize", return_value=_SAMPLE_RESULT):
        resp = client.post(
            "/anonymize",
            data={"text": _SAMPLE_TEXT},
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert "/review" in (resp.headers.get("Location") or "")


def test_review_without_cookie_redirects(client: FlaskClient) -> None:
    """GET /review без cookie → редирект на /."""
    resp = client.get("/review", follow_redirects=False)
    assert resp.status_code == 302


def test_review_shows_spans(client: FlaskClient) -> None:
    """GET /review показывает таблицу с найденными span'ами."""
    _store_and_set_cookie(client, _SAMPLE_RESULT)
    resp = client.get("/review")
    assert resp.status_code == 200
    assert "Иванов Иван".encode() in resp.data
    assert b"PERSON" in resp.data
    assert b"INN" in resp.data


def test_approve_redirects_to_result(client: FlaskClient) -> None:
    """POST /approve → редирект на /result."""
    _store_and_set_cookie(client, _SAMPLE_RESULT)
    span_ids = [s.span_id for s in _SAMPLE_RESULT.spans]
    resp = client.post(
        "/approve",
        data={"selected_span_ids": span_ids},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/result" in (resp.headers.get("Location") or "")


def test_result_shows_search_results(client: FlaskClient) -> None:
    """GET /result показывает карточки результатов."""
    _store_and_set_cookie(client, _SAMPLE_RESULT)
    # Имитируем прохождение через approve
    span_ids = [s.span_id for s in _SAMPLE_RESULT.spans]
    client.post("/approve", data={"selected_span_ids": span_ids})
    resp = client.get("/result")
    assert resp.status_code == 200
    assert b"1079" in resp.data


def test_degraded_requires_confirm(client: FlaskClient) -> None:
    """POST /approve без degraded_confirm при degraded → ошибка."""
    _store_and_set_cookie(client, _DEGRADED_RESULT)
    resp = client.post(
        "/approve",
        data={"selected_span_ids": []},
    )
    assert resp.status_code == 200
    assert "Подтвердите".encode() in resp.data


def test_degraded_with_confirm_ok(client: FlaskClient) -> None:
    """POST /approve с degraded_confirm при degraded → редирект."""
    _store_and_set_cookie(client, _DEGRADED_RESULT)
    resp = client.post(
        "/approve",
        data={"selected_span_ids": [], "degraded_confirm": "on"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


def test_cookie_does_not_contain_pii(client: FlaskClient) -> None:
    """Cookie review_id не содержит ПДн — только UUID."""
    with patch("legaldesk.web.app.anonymize", return_value=_SAMPLE_RESULT):
        resp = client.post(
            "/anonymize",
            data={"text": _SAMPLE_TEXT},
            follow_redirects=False,
        )
    cookie_header = resp.headers.get("Set-Cookie", "")
    assert "Иванов" not in cookie_header
    assert "123456789012" not in cookie_header


def test_no_cdn_in_html(client: FlaskClient) -> None:
    """HTML не содержит ссылок на CDN (Статья 4.3 CONSTITUTION)."""
    resp = client.get("/")
    html = resp.data.decode()
    assert "cdn" not in html.lower()
    assert "unpkg" not in html.lower()
    assert "jsdelivr" not in html.lower()


def test_new_clears_session(client: FlaskClient) -> None:
    """GET /new удаляет сессию и cookie."""
    review_id = _store_and_set_cookie(client, _SAMPLE_RESULT)
    resp = client.get("/new", follow_redirects=False)
    assert resp.status_code == 302
    assert review_store.get(review_id) is None


def test_full_cycle(client: FlaskClient) -> None:
    """Полный цикл: ввод → анонимизация → проверка → одобрение → результат."""
    with patch("legaldesk.web.app.anonymize", return_value=_SAMPLE_RESULT):
        resp = client.post(
            "/anonymize",
            data={"text": _SAMPLE_TEXT},
            follow_redirects=False,
        )
    assert resp.status_code == 302

    resp = client.get("/review")
    assert resp.status_code == 200

    span_ids = [s.span_id for s in _SAMPLE_RESULT.spans]
    resp = client.post(
        "/approve",
        data={"selected_span_ids": span_ids},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    resp = client.get("/result")
    assert resp.status_code == 200
    assert b"1079" in resp.data
