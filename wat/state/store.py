"""Single checkpoint store: one JSON file per run holding the full step context.

This is the consolidated "state" the critique asked for — no overlap with
telemetry (which is the append-only trace) or memory (the long-term results
index). A checkpoint is the latest known state of a run and is overwritten as
the run progresses, enabling inspection and (future) resume.
"""
from __future__ import annotations

import json
import time

from ..paths import STATE_DIR


def save_checkpoint(run_id: str, data: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"{run_id}.json"
    payload = {"runId": run_id, "updatedAt": round(time.time(), 3), **data}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_checkpoint(run_id: str):
    path = STATE_DIR / f"{run_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None
