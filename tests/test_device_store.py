"""Tests for the per-device ECG store and the multi-device/patient endpoints.

EcgStore unit tests need only the stdlib. Endpoint tests need the full app
(TensorFlow + model) and SKIP cleanly if unavailable.

    .venv\\Scripts\\python.exe -m pytest tests/test_device_store.py -q
"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

try:
    from device_store import EcgStore
    _DEPS = True
except ImportError:
    _DEPS = False


def _reading(device_id, user_id=None, prediction="Normal", confidence=92.0, received_at="2026-01-01T00:00:00Z"):
    return {
        "deviceId": device_id,
        "receivedAt": received_at,
        "prediction": prediction,
        "confidence": confidence,
        "heartRateBpm": 75.0,
        "leadOff": False,
        "qualityOk": True,
        "signalQuality": {"quality": "good"},
        "sampleRateHz": 250,
        "ecgData": [float(i % 10) for i in range(750)],
    }


# ---------------- EcgStore unit tests ----------------
def test_per_device_latest_is_isolated():
    if not _DEPS:
        print("SKIP"); return
    s = EcgStore(":memory:")
    s.record_reading(_reading("devA", received_at="2026-01-01T00:00:01Z"))
    s.record_reading(_reading("devB", prediction="PVC", received_at="2026-01-01T00:00:02Z"))
    assert s.latest_by_device("devA")["deviceId"] == "devA"
    assert s.latest_by_device("devB")["prediction"] == "PVC"
    assert s.latest_by_device("missing") is None
    # overall = most recent across devices
    assert s.latest_overall()["deviceId"] == "devB"


def test_ownership_scoped_lookup():
    if not _DEPS:
        print("SKIP"); return
    s = EcgStore(":memory:")
    s.record_reading(_reading("devA", received_at="2026-01-01T00:00:01Z"), user_id="p1")
    s.record_reading(_reading("devB", received_at="2026-01-01T00:00:02Z"), user_id="p2")
    assert s.latest_by_user("p1")["deviceId"] == "devA"
    assert s.latest_by_user("p2")["deviceId"] == "devB"
    assert s.latest_by_user("nobody") is None


def test_history_filters_and_orders():
    if not _DEPS:
        print("SKIP"); return
    s = EcgStore(":memory:")
    for i in range(3):
        s.record_reading(_reading("devA", received_at=f"2026-01-01T00:00:0{i}Z"), user_id="p1")
    s.record_reading(_reading("devB", received_at="2026-01-01T00:00:09Z"), user_id="p2")
    hist_a = s.history(device_id="devA")
    assert len(hist_a) == 3
    assert hist_a[0]["receivedAt"] >= hist_a[-1]["receivedAt"]  # DESC
    assert s.history(user_id="p2")[0]["deviceId"] == "devB"
    assert len(s.history(device_id="devA", limit=2)) == 2
    # metadata-only: history rows expose a preview, not the full waveform
    assert "signalPreview" in hist_a[0] and len(hist_a[0]["signalPreview"]) <= 50


def test_durability_across_reopen(tmp_path):
    if not _DEPS:
        print("SKIP"); return
    db = str(tmp_path / "ecg.db")
    s1 = EcgStore(db)
    s1.record_reading(_reading("devA"), user_id="p1")
    # New store instance on the same file == process restart.
    s2 = EcgStore(db)
    assert s2.latest_by_device("devA")["deviceId"] == "devA"
    assert s2.latest_by_user("p1")["deviceId"] == "devA"
    assert s2.stats()["totalReadings"] == 1


def test_stats_and_healthcheck():
    if not _DEPS:
        print("SKIP"); return
    s = EcgStore(":memory:")
    s.record_reading(_reading("devA"))
    st = s.stats()
    assert st["totalReadings"] == 1 and st["devices"] == 1
    assert s.healthcheck() is True


# ---------------- endpoint integration tests ----------------
def _client():
    try:
        import app
    except Exception:  # noqa: BLE001
        return None
    app.app.config.update(TESTING=True)
    return app


def _post(client, device_id, user_id):
    import numpy as np
    samples = (np.sin(np.linspace(0, 20 * np.pi, 500)) * 0.4 + 0.5).round(4).tolist()
    return client.post("/device-ecg", json={
        "deviceId": device_id, "sampleRateHz": 250, "samples": samples,
        "leadOff": False, "userId": user_id,
    })


def test_endpoints_multi_device_and_health():
    app = _client()
    if app is None:
        print("SKIP (app unavailable)"); return
    c = app.app.test_client()

    # This test exercises DEV behaviour (auth-protected reads pass through).
    # Force the auth gate off explicitly so it's independent of ambient env left
    # by other test modules; restore afterwards.
    import os
    prev_auth = os.environ.get("AUTH_ENABLED")
    os.environ["AUTH_ENABLED"] = "false"
    try:
        assert _post(c, "devA", "patient-1").status_code == 200
        assert _post(c, "devB", "patient-2").status_code == 200

        assert c.get("/device-ecg/latest?deviceId=devA").get_json()["deviceId"] == "devA"
        assert c.get("/device-ecg/latest?deviceId=devB").get_json()["deviceId"] == "devB"
        assert c.get("/patients/patient-2/ecg/latest").get_json()["deviceId"] == "devB"
        assert len(c.get("/device-ecg/history?deviceId=devA").get_json()["items"]) >= 1

        health = c.get("/health")
        assert health.status_code == 200 and health.get_json()["status"] == "ok"
        ready = c.get("/health/ready")
        assert ready.status_code == 200 and all(ready.get_json()["checks"].values())
    finally:
        if prev_auth is None:
            os.environ.pop("AUTH_ENABLED", None)
        else:
            os.environ["AUTH_ENABLED"] = prev_auth


def test_patient_endpoint_is_auth_protected():
    """When AUTH is enabled, scoped reads require a token (no cross-patient leak)."""
    app = _client()
    if app is None:
        print("SKIP (app unavailable)"); return
    import os
    prev = os.environ.get("AUTH_ENABLED")
    os.environ["AUTH_ENABLED"] = "true"
    os.environ.setdefault("SUPABASE_JWT_SECRET", "x" * 32)
    try:
        c = app.app.test_client()
        assert c.get("/patients/p1/ecg/latest").status_code == 401
        assert c.get("/device-ecg/history?userId=p1").status_code == 401
    finally:
        if prev is None:
            os.environ.pop("AUTH_ENABLED", None)
        else:
            os.environ["AUTH_ENABLED"] = prev


def _main():
    import inspect
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fails = 0
    for t in tests:
        try:
            t() if "tmp_path" not in inspect.signature(t).parameters else t(REPO / "_tmp_store")
            print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            fails += 1; print(f"FAIL {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - fails}/{len(tests)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(_main())
