"""Structured logging for the Cardios backend.

Emits one JSON object per log line (timestamp, level, logger, message, plus any
structured ``extra`` fields such as requestId / deviceId / status / durationMs).
JSON logs are machine-parseable for aggregation at scale; set ``LOG_FORMAT=text``
for human-readable local development.

Usage:
    from logging_config import configure_logging
    configure_logging()
    logger.info("device batch", extra={"deviceId": dev, "status": 200})
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

# Standard LogRecord attributes we should not duplicate into the JSON payload.
_RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Merge structured extras passed via logger.info(..., extra={...}).
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging() -> None:
    """Configure the root logger once, honoring LOG_LEVEL and LOG_FORMAT env vars."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    fmt = os.getenv("LOG_FORMAT", "text").lower()

    # Make the stream UTF-8 tolerant so non-ASCII log messages (e.g. Arabic) don't
    # raise UnicodeEncodeError on a Windows cp1252 console.
    stream = sys.stdout
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")  # py3.7+ real stdout
    except (AttributeError, ValueError):
        pass  # captured/non-reconfigurable stream (e.g. pytest) — leave as-is

    handler = logging.StreamHandler(stream)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.handlers.clear()           # replace any basicConfig handlers
    root.addHandler(handler)
    root.setLevel(getattr(logging, level, logging.INFO))
