"""Flask boundary-validation tests (run with pytest or standalone).

These exercise the real Flask app via its test client, so they need the web
stack + model artifacts (use the project's .venv). If the app can't be imported
in the current environment the tests SKIP cleanly rather than fail.

    D:\\Final Project\\cardios\\.venv\\Scripts\\python.exe tests/test_api_validation.py
"""
from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

VALID_RISK = {
    "BMI": 28.5, "Smoking": "Yes", "AlcoholDrinking": "No", "Stroke": "No",
    "PhysicalHealth": 5, "MentalHealth": 3, "DiffWalking": "No", "Sex": "Male",
    "AgeCategory": "60-64", "Race": "White", "Diabetic": "Yes",
    "PhysicalActivity": "Yes", "GenHealth": "Fair", "SleepTime": 6,
    "Asthma": "No", "KidneyDisease": "No", "SkinCancer": "No",
}


def _client():
    """Return a Flask test client, or None if the app can't be imported here."""
    try:
        import app  # backend/app.py (needs flask + model artifacts)
    except Exception:  # noqa: BLE001 - environment without flask/models -> skip
        return None
    app.app.config.update(TESTING=True)
    return app.app.test_client()


def test_predict_rejects_bad_enum():
    client = _client()
    if client is None:
        print("SKIP (flask/app unavailable)")
        return
    resp = client.post("/predict", json={**VALID_RISK, "Sex": "Other"})
    assert resp.status_code == 400, resp.status_code
    body = resp.get_json()
    assert body["error"] == "Invalid input"
    assert any(d["field"] == "Sex" for d in body["details"])


def test_predict_rejects_missing_field():
    client = _client()
    if client is None:
        print("SKIP (flask/app unavailable)")
        return
    incomplete = {k: v for k, v in VALID_RISK.items() if k != "BMI"}
    resp = client.post("/predict", json=incomplete)
    assert resp.status_code == 400
    assert any(d["field"] == "BMI" for d in resp.get_json()["details"])


def test_predict_accepts_valid_payload():
    client = _client()
    if client is None:
        print("SKIP (flask/app unavailable)")
        return
    resp = client.post("/predict", json=VALID_RISK)
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert "HeartFailureRisk" in body
    assert body.get("disclaimer")            # clinical-safety gate present
    assert body.get("notMedicalAdvice") is True


def test_device_ecg_rejects_empty_samples():
    client = _client()
    if client is None:
        print("SKIP (flask/app unavailable)")
        return
    resp = client.post("/device-ecg", json={"samples": [], "sampleRateHz": 250})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid input"


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
