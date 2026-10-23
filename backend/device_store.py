"""Per-device ECG reading store with durable metadata history.

Replaces the single in-process ``latest_device_reading`` global so the backend
can serve many devices and patients. Design goals (without overbuilding):

* **Per-device latest** — each ``deviceId`` keeps its own latest reading.
* **Ownership** — readings carry an optional ``userId`` (patient) for safe,
  scoped retrieval.
* **Durability** — metadata history and the per-device latest survive a process
  restart, backed by **SQLite** (Python stdlib, zero extra infrastructure). An
  in-memory cache fronts it for fast ``/latest`` reads.

For larger scale the same interface can be re-pointed at Postgres/Supabase or
Redis without changing callers (see ``docs/SCALING.md``).
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Metadata fields persisted per reading (the raw waveform is NOT persisted to
# history — only a short preview — to keep the history table small).
PREVIEW_SAMPLES = 50
# Cap the in-memory latest cache so a flood of unique deviceIds can't grow it
# without bound; SQLite remains the source of truth.
MAX_CACHED_DEVICES = 2000


def _default_db_path() -> str:
    env = os.getenv("ECG_STORE_PATH")
    if env:
        return env
    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / "ecg_history.db")


class EcgStore:
    """Thread-safe per-device store backed by SQLite."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_db_path()
        self._lock = threading.RLock()
        self._latest_cache: dict[str, dict] = {}
        # check_same_thread=False + our own lock: safe under Flask's threaded server.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS ecg_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    user_id TEXT,
                    received_at TEXT NOT NULL,
                    prediction TEXT,
                    confidence REAL,
                    heart_rate_bpm REAL,
                    lead_off INTEGER,
                    quality TEXT,
                    quality_ok INTEGER,
                    sample_rate_hz INTEGER,
                    num_samples INTEGER,
                    signal_preview TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_readings_device ON ecg_readings(device_id, received_at DESC);
                CREATE INDEX IF NOT EXISTS idx_readings_user ON ecg_readings(user_id, received_at DESC);

                CREATE TABLE IF NOT EXISTS device_latest (
                    device_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    received_at TEXT NOT NULL,
                    reading_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_latest_received ON device_latest(received_at DESC);
                CREATE INDEX IF NOT EXISTS idx_latest_user ON device_latest(user_id);
                """
            )
            self._conn.commit()

    # ---------------- writes ----------------
    def record_reading(self, reading: dict, user_id: Optional[str] = None) -> None:
        """Persist a reading: append metadata history + upsert the device latest."""
        device_id = str(reading.get("deviceId") or "unknown")
        received_at = reading.get("receivedAt") or datetime.now(timezone.utc).isoformat()
        quality = (reading.get("signalQuality") or {}).get("quality")
        ecg_data = reading.get("ecgData") or []
        preview = ecg_data[:PREVIEW_SAMPLES]

        stored = {**reading, "connected": True, "userId": user_id}

        with self._lock:
            self._conn.execute(
                """INSERT INTO ecg_readings
                   (device_id, user_id, received_at, prediction, confidence, heart_rate_bpm,
                    lead_off, quality, quality_ok, sample_rate_hz, num_samples, signal_preview)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    device_id, user_id, received_at,
                    reading.get("prediction"),
                    reading.get("confidence"),
                    reading.get("heartRateBpm"),
                    1 if reading.get("leadOff") else 0,
                    quality,
                    1 if reading.get("qualityOk") else 0,
                    reading.get("sampleRateHz"),
                    len(ecg_data),
                    json.dumps(preview),
                ),
            )
            self._conn.execute(
                """INSERT INTO device_latest (device_id, user_id, received_at, reading_json)
                   VALUES (?,?,?,?)
                   ON CONFLICT(device_id) DO UPDATE SET
                     user_id=excluded.user_id,
                     received_at=excluded.received_at,
                     reading_json=excluded.reading_json""",
                (device_id, user_id, received_at, json.dumps(stored)),
            )
            self._conn.commit()

            # refresh in-memory cache (bounded)
            self._latest_cache[device_id] = stored
            if len(self._latest_cache) > MAX_CACHED_DEVICES:
                oldest = min(self._latest_cache,
                             key=lambda d: self._latest_cache[d].get("receivedAt") or "")
                self._latest_cache.pop(oldest, None)

    # ---------------- reads ----------------
    def latest_by_device(self, device_id: str) -> Optional[dict]:
        cached = self._latest_cache.get(device_id)
        if cached is not None:
            return cached
        with self._lock:
            row = self._conn.execute(
                "SELECT reading_json FROM device_latest WHERE device_id=?", (device_id,)
            ).fetchone()
        return json.loads(row["reading_json"]) if row else None

    def latest_overall(self) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT reading_json FROM device_latest ORDER BY received_at DESC LIMIT 1"
            ).fetchone()
        return json.loads(row["reading_json"]) if row else None

    def latest_by_user(self, user_id: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT reading_json FROM device_latest WHERE user_id=? ORDER BY received_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return json.loads(row["reading_json"]) if row else None

    def list_devices(self, user_id: Optional[str] = None) -> list[dict]:
        where = " WHERE user_id=?" if user_id else ""
        params = (user_id,) if user_id else ()
        with self._lock:
            rows = self._conn.execute(
                f"SELECT device_id, received_at FROM device_latest{where} "
                "ORDER BY received_at DESC",
                params,
            ).fetchall()

        now = datetime.now(timezone.utc)
        return [self._device_summary(row, now) for row in rows]

    @staticmethod
    def _device_summary(row, now: datetime) -> dict:
        received_at = row["received_at"]
        packet_age = (now - datetime.fromisoformat(received_at)).total_seconds()
        return {
            "deviceId": row["device_id"],
            "receivedAt": received_at,
            "connected": 0 <= packet_age <= 15,
        }

    def history(self, device_id: Optional[str] = None, user_id: Optional[str] = None,
                limit: int = 50) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        clauses, params = [], []
        if device_id:
            clauses.append("device_id=?"); params.append(device_id)
        if user_id:
            clauses.append("user_id=?"); params.append(user_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"""SELECT device_id, user_id, received_at, prediction, confidence,
                           heart_rate_bpm, lead_off, quality, quality_ok, sample_rate_hz,
                           num_samples, signal_preview
                    FROM ecg_readings{where}
                    ORDER BY received_at DESC LIMIT ?""",
                (*params, limit),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["leadOff"] = bool(d.pop("lead_off"))
            d["qualityOk"] = bool(d.pop("quality_ok"))
            d["deviceId"] = d.pop("device_id")
            d["userId"] = d.pop("user_id")
            d["receivedAt"] = d.pop("received_at")
            d["heartRateBpm"] = d.pop("heart_rate_bpm")
            d["sampleRateHz"] = d.pop("sample_rate_hz")
            d["numSamples"] = d.pop("num_samples")
            try:
                d["signalPreview"] = json.loads(d.pop("signal_preview") or "[]")
            except (ValueError, TypeError):
                d["signalPreview"] = []
            out.append(d)
        return out

    def stats(self) -> dict:
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) AS c FROM ecg_readings").fetchone()["c"]
            devices = self._conn.execute("SELECT COUNT(*) AS c FROM device_latest").fetchone()["c"]
        return {"totalReadings": total, "devices": devices, "cachedDevices": len(self._latest_cache)}

    def healthcheck(self) -> bool:
        try:
            with self._lock:
                self._conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False
