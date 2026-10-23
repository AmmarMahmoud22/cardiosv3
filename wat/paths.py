"""Canonical filesystem locations for the WAT framework.

Everything is namespaced under ``wat/`` so it never collides with the existing
top-level ``tools/`` folder (which vendors ``arduino-cli.exe``).
"""
from __future__ import annotations

import sys
from pathlib import Path

WAT_DIR = Path(__file__).resolve().parent
REPO_ROOT = WAT_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"

STATE_DIR = WAT_DIR / "state" / "runs"
TELEMETRY_DIR = WAT_DIR / "telemetry" / "spans"
MEMORY_FILE = WAT_DIR / "memory" / "results.jsonl"


def ensure_backend_on_path() -> None:
    """Put the cardios ``backend/`` dir on sys.path so tools can import the
    existing modules (``ecg_service``, ``csv_converter``, ``risk_model``,
    ``chatbot_logic``) which use bare, sibling-relative imports."""
    p = str(BACKEND_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


def resolve_repo_path(path: str) -> Path:
    """Resolve a possibly-relative path against the repo root."""
    p = Path(path)
    return p if p.is_absolute() else (REPO_ROOT / path)
