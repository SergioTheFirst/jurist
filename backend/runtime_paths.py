"""Runtime path helpers for development and frozen desktop builds."""

from __future__ import annotations

import os
from pathlib import Path
import sys


APP_NAME = "LegalDesk"


def is_frozen() -> bool:
    """Return True when the application runs from a frozen bundle."""

    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """Return the repository root in development mode."""

    return Path(__file__).resolve().parents[1]


def resource_root() -> Path:
    """Return the directory that contains bundled read-only resources."""

    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return project_root()


def static_dir() -> Path:
    """Return the directory with frontend static assets."""

    candidates = (
        resource_root() / "frontend" / "static",
        project_root() / "frontend" / "static",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def runtime_data_root() -> Path:
    """Return writable runtime storage for DBs, uploads, and caches."""

    configured = os.getenv("LEGALDESK_DATA_DIR", "").strip()
    if configured:
        root = Path(configured)
    elif is_frozen():
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            root = Path(local_app_data) / APP_NAME
        else:
            root = Path.home() / "AppData" / "Local" / APP_NAME
    else:
        root = project_root() / "data"

    root.mkdir(parents=True, exist_ok=True)
    return root


def uploads_dir() -> Path:
    """Return writable directory for temporary uploaded files."""

    path = runtime_data_root() / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def archive_db_path() -> Path:
    """Return the writable SQLite path for archived cases."""

    path = runtime_data_root() / "archive" / "cases.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def audit_db_path() -> Path:
    """Return the writable SQLite path for compliance audit events."""

    path = runtime_data_root() / "archive" / "audit.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def kp_pattern_cache_path() -> Path:
    """Return the writable ConsultantPlus pattern-cache path."""

    path = runtime_data_root() / "cache" / "kp_pattern.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
