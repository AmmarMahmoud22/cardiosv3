"""Supabase JWT verification for protected Flask endpoints.

Opt-in via ``AUTH_ENABLED=true`` (default OFF, so local development keeps working
unchanged). When enabled, a valid Supabase access token — HS256, signed with the
project's JWT secret — must be sent as ``Authorization: Bearer <token>``. The
verified user id is attached to ``flask.g.user_id``.

Environment variables:
  AUTH_ENABLED         "true"/"1"/"yes"/"on" to enforce (default: off)
  SUPABASE_JWT_SECRET  the project's JWT secret (Supabase → Settings → API → JWT Secret)

Note: device ingestion (POST /device-ecg) is NOT covered here — the ESP32 cannot
perform a Supabase login. Protect that endpoint with a separate device key.
"""
from __future__ import annotations

import os
from functools import wraps

from flask import g, jsonify, request

try:
    import jwt  # PyJWT
except ImportError:  # pragma: no cover
    jwt = None


def auth_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def verify_token(token: str) -> dict:
    """Verify a Supabase access token and return its claims.

    Raises RuntimeError on misconfiguration, or a jwt exception on a bad token.
    """
    if jwt is None:
        raise RuntimeError("PyJWT is not installed")
    secret = os.getenv("SUPABASE_JWT_SECRET")
    if not secret:
        raise RuntimeError("SUPABASE_JWT_SECRET is not configured")
    return jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")


def require_auth(view):
    """Decorator enforcing a valid Supabase JWT when AUTH_ENABLED is on."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not auth_enabled():
            return view(*args, **kwargs)  # development passthrough

        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header"}), 401

        token = header.split(" ", 1)[1].strip()
        try:
            claims = verify_token(token)
        except RuntimeError as exc:
            # Server-side misconfiguration, not the caller's fault.
            return jsonify({"error": f"Auth not configured: {exc}"}), 503
        except Exception:  # noqa: BLE001 - PyJWT InvalidTokenError family
            return jsonify({"error": "Invalid or expired token"}), 401

        g.user_id = claims.get("sub")
        return view(*args, **kwargs)

    return wrapper
