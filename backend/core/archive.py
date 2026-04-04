"""SQLite archive storage for LegalDesk."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from backend.runtime_paths import archive_db_path

DB_PATH = archive_db_path()


class ArchiveManager:
    """Stores processed cases in a local SQLite archive."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def save_case(
        self,
        *,
        filename: str,
        original_text: str = "",
        anonymized_text: str,
        entities_found: dict[str, list[str]],
        legal_result: Any,
        total_replacements: int,
        input_type: str = "file",
    ) -> int:
        payload = self._serialize_legal_result(legal_result)
        created_at = datetime.now().isoformat(timespec="seconds")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO cases (
                    created_at,
                    filename,
                    input_type,
                    status,
                    original_text,
                    anonymized_text,
                    entities_found,
                    legal_summary,
                    relevant_laws,
                    court_practice,
                    recommendations,
                    source,
                    total_replacements
                ) VALUES (?, ?, ?, 'processed', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    filename,
                    input_type,
                    original_text,
                    anonymized_text,
                    json.dumps(entities_found, ensure_ascii=False),
                    payload["summary"],
                    json.dumps(payload["relevant_laws"], ensure_ascii=False),
                    json.dumps(payload["court_practice"], ensure_ascii=False),
                    payload["recommendations"],
                    payload["source"],
                    total_replacements,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def get_all(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT id, created_at, filename, input_type, status, total_replacements
                FROM cases
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_case(self, case_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT
                    id,
                    created_at,
                    filename,
                    input_type,
                    status,
                    original_text,
                    anonymized_text,
                    entities_found,
                    legal_summary,
                    relevant_laws,
                    court_practice,
                    recommendations,
                    source,
                    total_replacements
                FROM cases
                WHERE id = ?
                """,
                (case_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._deserialize_case(dict(row))

    def mark_reviewed(self, case_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE cases SET status = 'reviewed' WHERE id = ?",
                (case_id,),
            )
            connection.commit()
            return cursor.rowcount > 0

    def delete_case(self, case_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM cases WHERE id = ?", (case_id,))
            connection.commit()
            return cursor.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    input_type TEXT NOT NULL DEFAULT 'file',
                    status TEXT NOT NULL DEFAULT 'processed',
                    original_text TEXT NOT NULL DEFAULT '',
                    anonymized_text TEXT NOT NULL,
                    entities_found TEXT NOT NULL DEFAULT '{}',
                    legal_summary TEXT NOT NULL DEFAULT '',
                    relevant_laws TEXT NOT NULL DEFAULT '[]',
                    court_practice TEXT NOT NULL DEFAULT '[]',
                    recommendations TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT '',
                    total_replacements INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            self._ensure_column(connection, "input_type", "TEXT NOT NULL DEFAULT 'file'")
            self._ensure_column(connection, "original_text", "TEXT NOT NULL DEFAULT ''")
            connection.commit()

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, name: str, definition: str) -> None:
        cursor = connection.execute("PRAGMA table_info(cases)")
        columns = {row["name"] for row in cursor.fetchall()}
        if name not in columns:
            connection.execute(f"ALTER TABLE cases ADD COLUMN {name} {definition}")

    @staticmethod
    def _serialize_legal_result(legal_result: Any) -> dict[str, Any]:
        if is_dataclass(legal_result):
            payload = asdict(legal_result)
        elif isinstance(legal_result, dict):
            payload = dict(legal_result)
        else:
            payload = {
                "summary": getattr(legal_result, "summary", ""),
                "relevant_laws": getattr(legal_result, "relevant_laws", []),
                "court_practice": getattr(legal_result, "court_practice", []),
                "recommendations": getattr(legal_result, "recommendations", ""),
                "source": getattr(legal_result, "source", ""),
            }
        payload.setdefault("summary", "")
        payload.setdefault("relevant_laws", [])
        payload.setdefault("court_practice", [])
        payload.setdefault("recommendations", "")
        payload.setdefault("source", "")
        return payload

    @staticmethod
    def _deserialize_case(payload: dict[str, Any]) -> dict[str, Any]:
        payload["entities_found"] = json.loads(payload.get("entities_found") or "{}")
        payload["relevant_laws"] = json.loads(payload.get("relevant_laws") or "[]")
        payload["court_practice"] = json.loads(payload.get("court_practice") or "[]")
        return payload


ArchiveStore = ArchiveManager

archive = ArchiveManager(DB_PATH)
