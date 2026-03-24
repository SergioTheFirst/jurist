"""Тесты in-memory хранилища сессий."""

from __future__ import annotations

import time

from legaldesk.web.session_store import SessionStore


def test_create_and_get() -> None:
    """Создание сессии и получение данных по id."""
    store = SessionStore(ttl=60.0)
    data = {"key": "value"}
    sid = store.create(data)
    assert store.get(sid) == data


def test_expired_returns_none() -> None:
    """Истёкшая сессия возвращает None."""
    store = SessionStore(ttl=0.01)
    sid = store.create({"x": 1})
    time.sleep(0.02)
    assert store.get(sid) is None


def test_delete() -> None:
    """Удалённая сессия возвращает None."""
    store = SessionStore(ttl=60.0)
    sid = store.create({"a": "b"})
    store.delete(sid)
    assert store.get(sid) is None


def test_update() -> None:
    """Обновление данных существующей сессии."""
    store = SessionStore(ttl=60.0)
    sid = store.create({"v": 1})
    assert store.update(sid, {"v": 2}) is True
    assert store.get(sid) == {"v": 2}


def test_update_nonexistent_returns_false() -> None:
    """Обновление несуществующей сессии возвращает False."""
    store = SessionStore(ttl=60.0)
    assert store.update("fake-id", {}) is False


def test_update_expired_returns_false() -> None:
    """Обновление истёкшей сессии возвращает False."""
    store = SessionStore(ttl=0.01)
    sid = store.create({"x": 1})
    time.sleep(0.02)
    assert store.update(sid, {"x": 2}) is False


def test_cleanup_removes_expired() -> None:
    """cleanup() удаляет истёкшие записи."""
    store = SessionStore(ttl=0.01)
    sid = store.create({"old": True})
    time.sleep(0.02)
    store.cleanup()
    assert sid not in store._store
