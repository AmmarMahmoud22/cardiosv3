"""Tests for backend/auth.py — the Supabase JWT gate.

Needs Flask + PyJWT (the project's .venv). Runs with pytest or standalone:
    .venv\\Scripts\\python.exe tests\\test_auth.py
"""
from __future__ import annotations

import os
import pathlib
import sys
import time

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

try:
    import jwt
    from flask import Flask, jsonify
    import auth
    _DEPS = True
except ImportError:
    _DEPS = False

pytestmark = pytest.mark.skipif(
    not _DEPS,
    reason="Flask + PyJWT are required for backend auth tests",
)

SECRET = "test-secret-1234567890"


def _make_client():
    app = Flask(__name__)

    @app.route("/protected")
    @auth.require_auth
    def protected():
        return jsonify({"ok": True})

    return app.test_client()


def _token(**overrides):
    payload = {"sub": "user-123", "aud": "authenticated", "exp": int(time.time()) + 3600}
    payload.update(overrides)
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _enable():
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["SUPABASE_JWT_SECRET"] = SECRET


def test_passthrough_when_disabled():
    os.environ.pop("AUTH_ENABLED", None)
    assert _make_client().get("/protected").status_code == 200


def test_rejects_missing_header():
    _enable()
    assert _make_client().get("/protected").status_code == 401


def test_rejects_invalid_token():
    _enable()
    r = _make_client().get("/protected", headers={"Authorization": "Bearer garbage.token.here"})
    assert r.status_code == 401


def test_rejects_expired_token():
    _enable()
    tok = _token(exp=int(time.time()) - 10)
    r = _make_client().get("/protected", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 401


def test_accepts_valid_token():
    _enable()
    tok = _token()
    r = _make_client().get("/protected", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200


def test_503_when_secret_missing():
    os.environ["AUTH_ENABLED"] = "true"
    os.environ.pop("SUPABASE_JWT_SECRET", None)
    tok = jwt.encode({"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 60},
                     SECRET, algorithm="HS256")
    r = _make_client().get("/protected", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 503


def _main():
    if not _DEPS:
        print("SKIP test_auth — needs Flask + PyJWT (run with the .venv interpreter)")
        return 0
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
