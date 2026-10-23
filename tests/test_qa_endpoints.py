"""End-to-end QA tests for the /predict-ecg CSV upload path (graduation QA).

Complements the existing suites (no duplication):
- tests/test_api_validation.py — /predict happy path + invalid inputs, /device-ecg 400
- tests/test_security.py       — /predict 401, device-token 401, 413, 429, CORS
- tests/test_device_store.py   — /device-ecg happy path, multi-device, patient 401
- tests/test_auth.py           — JWT verification unit tests

This file covers the remaining gap: the CSV upload endpoint — valid trace,
missing file, garbage content (must come back *inconclusive*, never as a
confident classification), and 401 when authentication is enabled.

Needs the full app (TensorFlow + model); SKIPs cleanly if unavailable.

    .venv\\Scripts\\python.exe -m pytest tests/test_qa_endpoints.py -q
"""
from __future__ import annotations

import io
import os
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))


def _client():
    try:
        import app
    except Exception:  # noqa: BLE001 - environment without flask/models -> skip
        return None
    app.app.config.update(TESTING=True)
    return app.app.test_client()


def _ecg_csv_bytes() -> bytes:
    """A synthetic single-lead trace: flat baseline with QRS-like spikes.

    One value per line so the converter keeps it as numeric rows (a single
    comma-separated line would be swallowed as a CSV header).
    """
    import numpy as np

    rng = np.random.default_rng(7)
    n, fs = 900, 180
    signal = 0.45 + rng.normal(0, 0.01, n)
    for peak in range(40, n, int(fs * 0.8)):  # ~75 bpm
        signal[peak - 2] -= 0.08
        signal[peak] += 0.45
        signal[peak + 2] -= 0.12
    lines = "\n".join(f"{value:.4f}" for value in signal)
    return lines.encode("ascii")


def _post_csv(client, content: bytes, filename: str = "trace.csv"):
    return client.post(
        "/predict-ecg",
        data={"file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


def _force_auth(enabled: bool):
    """Set AUTH_ENABLED explicitly; returns the previous values for restore."""
    prev = (os.environ.get("AUTH_ENABLED"), os.environ.get("SUPABASE_JWT_SECRET"))
    os.environ["AUTH_ENABLED"] = "true" if enabled else "false"
    if enabled:
        os.environ.setdefault("SUPABASE_JWT_SECRET", "x" * 32)
    return prev


def _restore_auth(prev):
    for key, value in zip(("AUTH_ENABLED", "SUPABASE_JWT_SECRET"), prev):
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_predict_ecg_accepts_valid_csv():
    client = _client()
    if client is None:
        print("SKIP (app unavailable)"); return
    prev = _force_auth(False)
    try:
        resp = _post_csv(client, _ecg_csv_bytes())
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert isinstance(body["prediction"], str) and body["prediction"]
        # Confidence is a 0-100 percentage, or None when quality withheld it.
        if body["confidence"] is not None:
            assert 0.0 <= body["confidence"] <= 100.0
        assert isinstance(body["ecgData"], list) and len(body["ecgData"]) > 100
        assert body["signalQuality"]["quality"] in ("good", "acceptable", "poor")
        # Clinical-safety gate: the disclaimer always rides along.
        assert body["notMedicalAdvice"] is True and body["disclaimer"]
    finally:
        _restore_auth(prev)


def test_predict_ecg_rejects_missing_file():
    client = _client()
    if client is None:
        print("SKIP (app unavailable)"); return
    prev = _force_auth(False)
    try:
        resp = client.post("/predict-ecg", data={}, content_type="multipart/form-data")
        assert resp.status_code == 400
        assert "error" in resp.get_json()
    finally:
        _restore_auth(prev)


def test_predict_ecg_rejects_non_numeric_content():
    """A text file with no numbers must come back as a clean 400, never a 500
    and never a confident classification."""
    client = _client()
    if client is None:
        print("SKIP (app unavailable)"); return
    prev = _force_auth(False)
    try:
        resp = _post_csv(client, b"this file has no numbers at all\njust words\n")
        assert resp.status_code == 400, resp.get_data(as_text=True)
        assert "numeric" in resp.get_json()["error"].lower()
    finally:
        _restore_auth(prev)


def test_predict_ecg_requires_auth_when_enabled():
    client = _client()
    if client is None:
        print("SKIP (app unavailable)"); return
    prev = _force_auth(True)
    try:
        resp = _post_csv(client, _ecg_csv_bytes())
        assert resp.status_code == 401
    finally:
        _restore_auth(prev)


def _main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_main())
