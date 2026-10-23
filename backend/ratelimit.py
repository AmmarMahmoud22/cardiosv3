"""Rate limiting for the Cardios API (flask-limiter, deferred init).

The ``limiter`` is created without an app so blueprint routes can be decorated
at import time; ``limiter.init_app(app)`` is called from app.py. If flask-limiter
is not installed the module degrades gracefully: ``limiter`` is ``None`` and the
``rate_limit`` decorator becomes a no-op, so the API still runs (without limits).

Env vars:
  RATE_LIMIT_ENABLED       "false" to turn limiting off (default: on)
  RATE_LIMIT_DEFAULT       global default, e.g. "200 per minute" (default)
  RATE_LIMIT_STORAGE_URI   limiter backend, e.g. "redis://..." (default: memory://)
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_TRUE = {"1", "true", "yes", "on"}


def rate_limit_enabled() -> bool:
    return os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower() in _TRUE


try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[os.getenv("RATE_LIMIT_DEFAULT", "200 per minute")],
        storage_uri=os.getenv("RATE_LIMIT_STORAGE_URI", "memory://"),
        headers_enabled=True,
    )
except ImportError:  # pragma: no cover - optional dependency
    limiter = None
    logger.warning("flask-limiter not installed; API rate limiting is disabled.")


def rate_limit(spec: str):
    """Per-route limit decorator that is a no-op when the limiter is unavailable."""
    def decorator(view):
        if limiter is None:
            return view
        return limiter.limit(spec)(view)

    return decorator
