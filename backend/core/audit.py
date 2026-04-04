"""Local compliance audit log for LegalDesk."""

from __future__ import annotations

from datetime import datetime
import json
import os
import sqlite3
from typing import Any

from backend.runtime_paths import audit_db_path

DB_PATH = audit_db_path()


class AuditLogManager:
    """Persist local audit events for compliance and traceability."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def log_event(
        self,
        *,
        action: str,
        subject: str,
        case_id: int | None = None,
        actor: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        """Store one audit event and return its identifier."""

        created_at = datetime.now().isoformat(timespec="seconds")
        resolved_actor = (actor or self._default_actor()).strip() or "local-lawyer"
        payload = json.dumps(details or {}, ensure_ascii=False)

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO audit_log (
                    created_at,
                    actor,
                    action,
                    case_id,
                    subject,
                    details
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (created_at, resolved_actor, action, case_id, subject, payload),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def list_entries(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        case_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return audit entries ordered from newest to oldest."""

        query = """
            SELECT id, created_at, actor, action, case_id, subject, details
            FROM audit_log
        """
        parameters: list[Any] = []
        if case_id is not None:
            query += " WHERE case_id = ?"
            parameters.append(case_id)
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        parameters.extend([limit, offset])

        with self._connect() as connection:
            cursor = connection.execute(query, tuple(parameters))
            return [self._deserialize_entry(dict(row)) for row in cursor.fetchall()]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    case_id INTEGER,
                    subject TEXT NOT NULL DEFAULT '',
                    details TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            connection.commit()

    @staticmethod
    def _deserialize_entry(payload: dict[str, Any]) -> dict[str, Any]:
        payload["details"] = json.loads(payload.get("details") or "{}")
        return payload

    @staticmethod
    def _default_actor() -> str:
        return (
            os.getenv("LEGALDESK_ACTOR")
            or os.getenv("USERNAME")
            or os.getenv("USER")
            or "local-lawyer"
        )


audit_log = AuditLogManager(DB_PATH)
