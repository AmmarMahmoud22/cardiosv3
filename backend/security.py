"""Centralised API security helpers for the Cardios backend.

Everything here is ENV-DRIVEN and defaults to dev-friendly values so the local
demo keeps working with zero configuration. Tighten in production via env vars
(documented in .env.example):

  APP_ENV / FLASK_ENV     "production" to enable strict behaviour (default: development)
  CORS_ALLOWED_ORIGINS    comma-separated allowlist (default: localhost dev ports)
  MAX_CONTENT_LENGTH_MB   max request body size in MB (default: 5)
  SWAGGER_ENABLED         "true"/"false" to force docs on/off (default: on in dev only)
  DEVICE_AUTH_ENABLED     "true" to require a device token on /device-ecg (default: off)
  DEVICE_API_TOKEN        the shared device token (required when device auth is on)

Gates are read at REQUEST time where possible so they can be toggled per-test.
"""
from __future__ import annotations

import hmac
import logging
import os
from functools import wraps

from flask import jsonify, request

logger = logging.getLogger(__name__)

_TRUE = {"1", "true", "yes", "on"}


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE


def app_env() -> str:
    return os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).strip().lower()


def is_production() -> bool:
    return app_env() in {"production", "prod"}


# ---------------- CORS ----------------
_DEFAULT_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5176",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5176",
    "https://cardios-hakathon.appwrite.network",
]


def get_allowed_origins() -> list[str]:
    """Explicit allowlist. In production an empty list blocks all cross-origin
    requests (same-origin still works) until CORS_ALLOWED_ORIGINS is set."""
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    if is_production():
        logger.warning("CORS_ALLOWED_ORIGINS is not set in production; blocking all cross-origin requests.")
        return []
    return list(_DEFAULT_DEV_ORIGINS)


# ---------------- request size ----------------
def max_content_length_bytes() -> int:
    try:
        mb = float(os.getenv("MAX_CONTENT_LENGTH_MB", "5"))
    except ValueError:
        mb = 5.0
    return int(mb * 1024 * 1024)


# ---------------- Swagger gating ----------------
def swagger_enabled() -> bool:
    raw = os.getenv("SWAGGER_ENABLED")
    if raw is not None:
        return raw.strip().lower() in _TRUE
    return not is_production()  # docs in dev only, by default


# ---------------- device authentication ----------------
def device_auth_enabled() -> bool:
    return _flag("DEVICE_AUTH_ENABLED", default=False)


def require_device_auth(view):
    """Require a valid device token on the decorated endpoint.

    The ESP32 cannot perform a Supabase login, so /device-ecg is protected with
    a shared secret sent as ``X-Device-Token: <token>`` (or ``Authorization:
    Bearer <token>``). Disabled by default so the local demo works; enable with
    DEVICE_AUTH_ENABLED=true and set DEVICE_API_TOKEN.
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not device_auth_enabled():
            return view(*args, **kwargs)  # development passthrough

        expected = os.getenv("DEVICE_API_TOKEN", "")
        if not expected:
            # Misconfiguration, not the caller's fault.
            return jsonify({"error": "Device authentication is not configured"}), 503

        provided = request.headers.get("X-Device-Token", "")
        if not provided:
            header = request.headers.get("Authorization", "")
            if header.startswith("Bearer "):
                provided = header.split(" ", 1)[1].strip()

        if not provided or not hmac.compare_digest(provided, expected):
            return jsonify({"error": "Invalid or missing device token"}), 401

        return view(*args, **kwargs)

    return wrapper


# ---------------- production-safe errors ----------------
def safe_error_response(exc: Exception, status: int = 500, public_message: str = "Internal server error"):
    """Never leak raw internal exception text in production. In development the
    detail is included to aid debugging.

    HTTP exceptions (413, 429, 404, ...) are returned untouched so Flask's own
    error handlers produce the correct status instead of a generic 500."""
    from werkzeug.exceptions import HTTPException

    if isinstance(exc, HTTPException):
        return exc

    body = {"error": public_message}
    if not is_production():
        body["detail"] = str(exc)
    return jsonify(body), status
