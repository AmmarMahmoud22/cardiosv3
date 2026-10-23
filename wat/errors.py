"""Error taxonomy for WAT.

The system prompt's "Fail Intelligently" rule lists error classes but gives no
code path. This module gives them one: a single exception type carrying a
``category``, plus a classifier that maps arbitrary exceptions onto the taxonomy.
The engine uses the category to decide retry vs. abort.
"""
from __future__ import annotations

VALID_CATEGORIES = (
    "transient",    # network blip, port busy — safe to retry
    "auth",         # bad/expired credentials — do not blind-retry
    "schema",       # input/output failed contract validation
    "rate_limit",   # throttled — retry with backoff
    "dependency",   # missing package, model artifact, or downstream service
    "parsing",      # malformed data that passed schema but failed in logic
    "unknown",
)


class WatError(Exception):
    """A categorized failure. Tools raise this so the engine can act on it."""

    def __init__(self, message: str, category: str = "unknown", *, cause: BaseException | None = None):
        super().__init__(message)
        self.category = category if category in VALID_CATEGORIES else "unknown"
        self.cause = cause


def classify_exception(exc: BaseException) -> str:
    """Map any exception onto the taxonomy."""
    if isinstance(exc, WatError):
        return exc.category
    # pydantic raises ValidationError (named, but avoid importing pydantic here)
    if type(exc).__name__ == "ValidationError":
        return "schema"
    if isinstance(exc, (ModuleNotFoundError, ImportError, FileNotFoundError)):
        return "dependency"
    if isinstance(exc, (TimeoutError, ConnectionError, InterruptedError)):
        return "transient"
    if isinstance(exc, (ValueError, KeyError, TypeError, IndexError)):
        return "parsing"
    return "unknown"
