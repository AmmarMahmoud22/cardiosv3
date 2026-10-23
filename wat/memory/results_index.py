"""Long-term memory — STUB, intentionally minimal.

The critique flagged the 4-type memory model (short/long/semantic/episodic) as
overengineering for this project. So memory here is exactly one thing the app
actually needs: an append-only index of produced results
(``wat/memory/results.jsonl``). Semantic/episodic retrieval is deferred until a
real retrieval use case exists.
"""
from __future__ import annotations

import json
import time

from ..paths import MEMORY_FILE


def record_result(record: dict) -> dict:
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = {"ts": round(time.time(), 3), **record}
    with MEMORY_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line
