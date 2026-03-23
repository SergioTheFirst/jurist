"""Protocol для провайдеров правового поиска."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class SearchResult(BaseModel):
    """Результат поиска по правовой базе."""

    title: str
    snippet: str
    url: str = ""


class LegalSearchProvider(Protocol):
    """Интерфейс провайдера правового поиска."""

    def search(self, query: str) -> list[SearchResult]:
        """Выполнить поиск по правовой базе."""
        ...
