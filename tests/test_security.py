"""Security hardening tests for the Cardios backend.

Covers (a) env-driven security helpers in backend/security.py, (b) the device
auth + JWT gates on real endpoints (unauthorized vs authorized), (c) rate
limiting, request-size caps, Swagger gating, and non-leaking errors.

Needs the project's .venv (Flask, PyJWT, flask-limiter, model artifacts). Tests
that require the full app SKIP cleanly if it can't be imported here.

    .venv\\Scripts\\python.exe tests\\test_security.py     # standalone
    .venv\\Scripts\\python.exe -m pytest tests/test_security.py -q
"""
from __future__ import annotations

import contextlib
import os
import pathlib
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

try:
    import jwt
    from flask import Flask, jsonify
    import security
    _DEPS = True
except ImportError:
    _DEPS = False

JWT_SECRET = "test-secret-key-1234567890-abcdefgh"
DEVICE_TOKEN = "super-secret-device-token"

VALID_RISK = {
    "BMI": 28.5, "Smoking": "Yes", "AlcoholDrinking": "No", "Stroke": "No",
    "PhysicalHealth": 5, "MentalHealth": 3, "DiffWalking": "No", "Sex": "Male",
    "AgeCategory": "60-64", "Race": "White", "Diabetic": "Yes",
    "PhysicalActivity": "Yes", "GenHealth": "Fair", "SleepTime": 6,
    "Asthma": "No", "KidneyDisease": "No", "SkinCancer": "No",
}


@contextlib.contextmanager
def env(**values):
    """Temporarily set env vars (None deletes) and restore afterwards."""
    previous = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = str(v)
        yield
    finally:
        for k, old in previous.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old


def _device_token(**overrides):
    payload = {"sub": "user-1", "aud": "authenticated", "exp": int(time.time()) + 3600}
    payload.update(overrides)
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _app_client():
    """Real Flask app test client, or None if it can't be imported here."""
    try:
        import app
    except Exception:  # noqa: BLE001
        return None
    app.app.config.update(TESTING=True)
    return app


# ----------------------- helper unit tests (no full app) -----------------------
def test_allowed_origins_dev_default():
    if not _DEPS:
        print("SKIP (deps unavailable)"); return
    with env(APP_ENV="development", CORS_ALLOWED_ORIGINS=None):
        origins = security.get_allowed_origins()
        assert "http://localhost:5173" in origins or "http://localhost:5176" in origins


def test_allowed_origins_production_empty_without_config():
    if not _DEPS:
        print("SKIP"); return
    with env(APP_ENV="production", CORS_ALLOWED_ORIGINS=None):
        assert security.get_allowed_origins() == []
    with env(APP_ENV="production", CORS_ALLOWED_ORIGINS="https://a.com,https://b.com"):
        assert security.get_allowed_origins() == ["https://a.com", "https://b.com"]


def test_swagger_disabled_in_production():
    if not _DEPS:
        print("SKIP"); return
    with env(APP_ENV="production", SWAGGER_ENABLED=None):
        assert security.swagger_enabled() is False
    with env(APP_ENV="development", SWAGGER_ENABLED=None):
        assert security.swagger_enabled() is True
    with env(APP_ENV="production", SWAGGER_ENABLED="true"):
        assert security.swagger_enabled() is True


def test_max_content_length_from_env():
    if not _DEPS:
        print("SKIP"); return
    with env(MAX_CONTENT_LENGTH_MB="2"):
        assert security.max_content_length_bytes() == 2 * 1024 * 1024


def test_safe_error_hides_detail_in_production():
    if not _DEPS:
        print("SKIP"); return
    app = Flask(__name__)
    with app.test_request_context():
        with env(APP_ENV="production"):
            body, status = security.safe_error_response(ValueError("secret stack detail"))
            data = body.get_json()
            assert status == 500
            assert "secret stack detail" not in str(data)
            assert "detail" not in data
        with env(APP_ENV="development"):
            body, _ = security.safe_error_response(ValueError("dev detail"))
            assert body.get_json().get("detail") == "dev detail"


# ----------------------- device auth decorator -----------------------
def _device_app():
    app = Flask(__name__)

    @app.route("/d", methods=["POST"])
    @security.require_device_auth
    def d():
        return jsonify(ok=True)

    return app.test_client()


def test_device_auth_passthrough_when_disabled():
    if not _DEPS:
        print("SKIP"); return
    with env(DEVICE_AUTH_ENABLED="false"):
        assert _device_app().post("/d").status_code == 200


def test_device_auth_rejects_without_token():
    if not _DEPS:
        print("SKIP"); return
    with env(DEVICE_AUTH_ENABLED="true", DEVICE_API_TOKEN=DEVICE_TOKEN):
        assert _device_app().post("/d").status_code == 401


def test_device_auth_rejects_wrong_token():
    if not _DEPS:
        print("SKIP"); return
    with env(DEVICE_AUTH_ENABLED="true", DEVICE_API_TOKEN=DEVICE_TOKEN):
        r = _device_app().post("/d", headers={"X-Device-Token": "nope"})
        assert r.status_code == 401


def test_device_auth_accepts_valid_token():
    if not _DEPS:
        print("SKIP"); return
    with env(DEVICE_AUTH_ENABLED="true", DEVICE_API_TOKEN=DEVICE_TOKEN):
        r = _device_app().post("/d", headers={"X-Device-Token": DEVICE_TOKEN})
        assert r.status_code == 200


def test_device_auth_503_when_token_unset():
    if not _DEPS:
        print("SKIP"); return
    with env(DEVICE_AUTH_ENABLED="true", DEVICE_API_TOKEN=None):
        assert _device_app().post("/d", headers={"X-Device-Token": "x"}).status_code == 503


# ----------------------- rate limiting (isolated app) -----------------------
def test_rate_limit_returns_429():
    if not _DEPS:
        print("SKIP"); return
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
    except ImportError:
        print("SKIP (flask-limiter unavailable)"); return

    app = Flask(__name__)
    limiter = Limiter(key_func=get_remote_address, app=app,
                      default_limits=["3 per minute"], storage_uri="memory://")
    assert limiter is not None

    @app.route("/x")
    def x():
        return jsonify(ok=True)

    client = app.test_client()
    codes = [client.get("/x").status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200], codes
    assert codes[3] == 429, codes


# ----------------------- real-app integration: authz on endpoints -----------------------
def test_predict_requires_jwt_when_auth_enabled():
    app = _app_client()
    if app is None:
        print("SKIP (app unavailable)"); return
    client = app.app.test_client()
    with env(AUTH_ENABLED="true", SUPABASE_JWT_SECRET=JWT_SECRET):
        unauth = client.post("/predict", json=VALID_RISK)
        assert unauth.status_code == 401, unauth.status_code

        token = _device_token()
        ok = client.post("/predict", json=VALID_RISK,
                         headers={"Authorization": f"Bearer {token}"})
        assert ok.status_code == 200, ok.get_json()
        assert "HeartFailureRisk" in ok.get_json()


def test_device_ecg_requires_device_token_when_enabled():
    app = _app_client()
    if app is None:
        print("SKIP (app unavailable)"); return
    client = app.app.test_client()
    samples = [round(0.5, 4)] * 250
    body = {"deviceId": "t", "sampleRateHz": 250, "samples": samples, "leadOff": False}
    with env(DEVICE_AUTH_ENABLED="true", DEVICE_API_TOKEN=DEVICE_TOKEN):
        unauth = client.post("/device-ecg", json=body)
        assert unauth.status_code == 401, unauth.status_code

        ok = client.post("/device-ecg", json=body, headers={"X-Device-Token": DEVICE_TOKEN})
        assert ok.status_code == 200, ok.get_json()


def test_request_size_limit_returns_413():
    app = _app_client()
    if app is None:
        print("SKIP (app unavailable)"); return
    # Shrink the cap at runtime and post a body above it.
    original = app.app.config.get("MAX_CONTENT_LENGTH")
    app.app.config["MAX_CONTENT_LENGTH"] = 1024
    try:
        client = app.app.test_client()
        big = {"deviceId": "t", "sampleRateHz": 250, "samples": list(range(5000))}
        r = client.post("/device-ecg", json=big)
        assert r.status_code == 413, r.status_code
        assert r.get_json().get("error") == "Request payload too large"
    finally:
        app.app.config["MAX_CONTENT_LENGTH"] = original


def _main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_main())
