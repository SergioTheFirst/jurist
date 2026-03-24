"""Server-side in-memory session store. ПДн хранятся на сервере, в cookie — только opaque id."""

from __future__ import annotations

import time
import uuid
from typing import Any


class SessionStore:
    """In-memory хранилище сессий с TTL. Только для локального MVP.

    Персональные данные НИКОГДА не покидают этот объект в сеть (Статья 2 CONSTITUTION).
    """

    def __init__(self, ttl: float = 3600.0) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self.ttl = ttl

    def create(self, data: Any) -> str:
        """Сохранить данные и вернуть непрозрачный идентификатор сессии."""
        self.cleanup()
        session_id = str(uuid.uuid4())
        expires_at = time.time() + self.ttl
        self._store[session_id] = (data, expires_at)
        return session_id

    def get(self, session_id: str) -> Any | None:
        """Получить данные сессии или None если не найдено / TTL истёк."""
        entry = self._store.get(session_id)
        if entry is None:
            return None
        data, expires_at = entry
        if time.time() > expires_at:
            del self._store[session_id]
            return None
        return data

    def update(self, session_id: str, data: Any) -> bool:
        """Обновить данные существующей сессии. Возвращает False если сессия не найдена."""
        entry = self._store.get(session_id)
        if entry is None:
            return False
        _, expires_at = entry
        if time.time() > expires_at:
            del self._store[session_id]
            return False
        self._store[session_id] = (data, expires_at)
        return True

    def delete(self, session_id: str) -> None:
        """Удалить сессию."""
        self._store.pop(session_id, None)

    def cleanup(self) -> None:
        """Удалить все истёкшие сессии."""
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]


# Singleton для использования во Flask-приложении
review_store = SessionStore()
