"""
Unified response envelope and whitelisted error codes.

Adapted from the `research-terminal` edge-function contract
(`functions/handler.ts: ok() / fail() / safeErrorCode()`):

    { "ok": true,  "action": "...",  "generatedAt": "ISO", ...extra, "data": {...} }
    { "ok": false, "action": "...",  "generatedAt": "ISO", "error": "...", "message": "..." }

Two rules are non-negotiable, because they are what keeps the API honest:

1. Only *known* error codes (or an explicitly allowed prefix) reach the client.
   Everything else is folded into ``runtime_<ErrorName>`` so raw upstream text,
   URLs and stack traces can never leak through the JSON.
2. A failure is declared as a failure. We never substitute fabricated numbers
   for a real upstream value without marking the payload as simulated.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional

logger = logging.getLogger(__name__)

# --- error-code contract -----------------------------------------------------

# Exact codes the API may return to a client.
KNOWN_ERROR_CODES: frozenset[str] = frozenset(
    {
        "no_data",
        "no_bars",
        "insufficient_history",
        "not_found",
        "unknown_action",
        "method_not_allowed",
        "invalid_params",
        "missing_param",
        "rate_limited",
        "unavailable",
        "degraded",
        "conflict",
        "unauthorized",
        "forbidden",
        "internal_error",
    }
)

# Codes that may be prefixed (e.g. ``upstream_timeout``, ``invalid_index_code``).
ALLOWED_PREFIXES: tuple[str, ...] = (
    "upstream",
    "invalid",
    "missing",
    "runtime",
)

_SAFE_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def safe_error_code(error: Any) -> str:
    """Reduce an arbitrary exception/code to a stable, whitelisted error code.

    Mirrors ``safeErrorCode`` in research-terminal's handler: known codes pass
    through, allowed prefixes pass through, everything else becomes
    ``runtime_<ErrorName>`` with no message, URL or stack.
    """
    raw = str(error or "").strip().lower()
    if not raw:
        return "internal_error"

    # Exception class names are not codes; fold them explicitly.
    if not _SAFE_CODE_RE.match(raw):
        return "internal_error"

    if raw in KNOWN_ERROR_CODES:
        return raw
    if any(raw.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        return raw
    return "internal_error"


def classify_exception(exc: BaseException) -> str:
    """Map an unexpected exception to a non-leaking ``runtime_*`` code."""
    name = type(exc).__name__
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    code = f"runtime_{normalized}"
    return code if _SAFE_CODE_RE.match(code) else "internal_error"


# --- envelope ----------------------------------------------------------------

def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def ok(action: str, data: Any = None, **extra: Any) -> dict:
    """Build a success envelope. ``action``'s own fields live inside ``data``."""
    payload: dict[str, Any] = {
        "ok": True,
        "action": action,
        "generatedAt": _generated_at(),
    }
    payload.update({k: v for k, v in extra.items() if v is not None})
    payload["data"] = data
    return payload


def fail(
    action: str,
    error: Any,
    status: int = 502,
    message: Optional[str] = None,
    **extra: Any,
) -> dict:
    """Build a failure envelope with a whitelisted error code.

    The dict intentionally carries an ``http_status`` hint consumed by the
    FastAPI exception handler / endpoint; it is stripped from the body.
    """
    code = safe_error_code(error) if isinstance(error, str) else classify_exception(error)
    payload: dict[str, Any] = {
        "ok": False,
        "action": action,
        "generatedAt": _generated_at(),
        "error": code,
    }
    if message:
        payload["message"] = message[:300]
    payload.update({k: v for k, v in extra.items() if v is not None})
    payload["http_status"] = status
    return payload


def strip_status(payload: Mapping[str, Any]) -> dict:
    """Return the envelope without the internal ``http_status`` hint."""
    return {k: v for k, v in payload.items() if k != "http_status"}


def availability(items: Iterable[tuple[str, bool, Optional[str]]]) -> dict:
    """Summarise which sources were reachable.

    ``items`` is an iterable of ``(name, reachable, error_code)``. Mirrors the
    ``sources`` block research-terminal attaches so the UI can say *which* feed
    was down instead of blanking a whole panel.
    """
    sources: dict[str, dict] = {}
    for name, reachable, error in items:
        sources[name] = {
            "status": "ok" if reachable else "error",
            "error": None if reachable else safe_error_code(error),
        }
    return sources
