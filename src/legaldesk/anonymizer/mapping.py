"""Хранение и обратная подстановка токенов анонимизации."""

from __future__ import annotations


class TokenMapping:
    """Двунаправленный маппинг: оригинал ↔ токен-заменитель."""

    def __init__(self) -> None:
        self._forward: dict[str, str] = {}
        self._reverse: dict[str, str] = {}
        self._counter: int = 0

    def add(self, original: str, category: str) -> str:
        """Добавить значение и вернуть токен-заменитель."""
        if original in self._forward:
            return self._forward[original]
        self._counter += 1
        token = f"[{category}_{self._counter}]"
        self._forward[original] = token
        self._reverse[token] = original
        return token

    def restore(self, text: str) -> str:
        """Заменить все токены обратно на оригинальные значения."""
        result = text
        for token, original in self._reverse.items():
            result = result.replace(token, original)
        return result

    @property
    def entries(self) -> dict[str, str]:
        """Копия маппинга оригинал → токен."""
        return dict(self._forward)
