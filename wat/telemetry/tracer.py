"""Minimal structured tracer: one JSONL span file per run.

The system prompt asks for traceable executions (latency, retries, failures,
path). This is the smallest concrete sink that delivers that without pulling in
OpenTelemetry: append-only JSON lines under ``wat/telemetry/spans/<run_id>.jsonl``.
"""
from __future__ import annotations

import json
import time

from ..paths import TELEMETRY_DIR


class Tracer:
    def __init__(self, run_id: str):
        self.run_id = run_id
        TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
        self.path = TELEMETRY_DIR / f"{run_id}.jsonl"

    def emit(self, span: dict) -> None:
        record = {"runId": self.run_id, "ts": round(time.time(), 3), **span}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
