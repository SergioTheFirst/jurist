"""Тесты модуля правового поиска."""

from __future__ import annotations

import pytest

from legaldesk.legal_engine.consultant_plus import ConsultantPlusProvider
from legaldesk.legal_engine.provider import SearchResult


def test_search_result_model() -> None:
    """SearchResult создаётся из словаря."""
    r = SearchResult(title="Статья 1", snippet="Текст статьи")
    assert r.title == "Статья 1"
    assert r.url == ""


def test_consultant_plus_not_implemented() -> None:
    """ConsultantPlusProvider.search выбрасывает NotImplementedError."""
    provider = ConsultantPlusProvider()
    with pytest.raises(NotImplementedError):
        provider.search("тест")
