"""Реализация LegalSearchProvider для КонсультантПлюс API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from legaldesk.legal_engine.provider import SearchResult


class ConsultantPlusProvider:
    """Клиент API КонсультантПлюс."""

    def __init__(self, base_url: str = "", api_key: str = "") -> None:
        self._base_url = base_url
        self._api_key = api_key

    def search(self, query: str) -> list[SearchResult]:
        """Выполнить поиск по API КонсультантПлюс."""
        _ = query
        raise NotImplementedError("Интеграция с КонсультантПлюс ещё не реализована")
