"""Тесты StubProvider для правового поиска."""

from __future__ import annotations

from legaldesk.legal_engine.stub_provider import StubProvider


def test_returns_list() -> None:
    """StubProvider.search() возвращает непустой список."""
    provider = StubProvider()
    results = provider.search("тест")
    assert isinstance(results, list)
    assert len(results) > 0


def test_results_have_title_and_snippet() -> None:
    """Каждый результат имеет title и snippet."""
    provider = StubProvider()
    results = provider.search("тест")
    for r in results:
        assert r.title
        assert r.snippet
