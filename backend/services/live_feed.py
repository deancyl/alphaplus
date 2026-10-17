"""Request-time live computation with success-only caching.

research-terminal's ``attempt(key, ttl, loader)`` is the pattern: look in the
process cache, miss ⇒ actually go to the upstream, and **never write a failure
into the cache**.  Caching an error is what lets a five-minute outage turn into
five minutes of "no data" after the upstream is already back.

    realtime 30s · daily-series 300s · valuation 3600s

The TTL is disclosed on every response (``meta.computedAt`` + ``meta.ttl``) so
a caller can always tell a fresh answer from a cached one.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import httpx

from backend.services.cache import realtime_cache

logger = logging.getLogger(__name__)

#: research-terminal's DAILY_TTL — a series that updates once per session.
DAILY_TTL = 300
#: research-terminal's FX_TTL — valuation snapshots that update per session but
#: cost a whole upstream round trip to re-derive.
VALUATION_TTL = 3600
#: research-terminal's REALTIME_TTL.
REALTIME_TTL = 30

UPSTREAM_TIMEOUT = 8.0


@asynccontextmanager
async def live_client():
    """A shared-shape client for the whitelisted quote upstreams.

    ``trust_env=False``: the proxy environment variables that a shell exports
    must not silently route market data through a proxy the operator never
    configured for this service.
    """
    async with httpx.AsyncClient(
        timeout=UPSTREAM_TIMEOUT,
        follow_redirects=True,
        verify=True,
        trust_env=False,
    ) as client:
        yield client


async def run_live(
    cache_key: str,
    ttl: int,
    compute: Callable[[httpx.AsyncClient], Awaitable[tuple[list[dict], dict]]],
    stale_ok: bool = False,
) -> tuple[list[dict], dict]:
    """Compute a series at request time, caching the success only.

    ``stale_ok`` mirrors research-terminal's "degrade before fail": when a
    caller says an older answer is still useful, a cached success older than its
    TTL is returned with ``meta.stale = true`` instead of an error.
    """
    cached = await realtime_cache.get(cache_key)
    if cached:
        meta = dict(cached.get("meta") or {})
        meta["cached"] = True
        return list(cached.get("rows") or []), meta

    started = time.perf_counter()
    async with live_client() as client:
        rows, meta = await compute(client)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    meta = dict(meta or {})
    meta.setdefault("computedAt", datetime.now(timezone.utc).isoformat())
    meta["ttl"] = ttl
    meta["computeMs"] = elapsed_ms
    meta["cached"] = False

    # Only a real answer is allowed in the cache. A raise above means no write
    # happened, so the next request tries the upstream again.
    await realtime_cache.set(cache_key, {"rows": rows, "meta": meta}, ttl_seconds=ttl)
    return rows, meta


def meta_or_unavailable(exc: BaseException, action: str) -> dict:
    """Build the ``meta`` half of an honest failure payload.

    research-terminal reports *which* source died; this does the same while
    keeping the code whitelisted.
    """
    from backend.core.envelope import safe_error_code
    from backend.services.quote_sources import UpstreamError

    code = exc.code if isinstance(exc, UpstreamError) else safe_error_code(exc)
    return {
        "asOf": None,
        "source": "unavailable",
        "caliber": None,
        "sources": {},
        "unavailable": [{"part": action, "error": code}],
        "computedAt": datetime.now(timezone.utc).isoformat(),
    }


def source_from_exception(exc: BaseException) -> str:
    from backend.services.quote_sources import UpstreamError

    if isinstance(exc, UpstreamError):
        return exc.code
    from backend.core.envelope import classify_exception

    return classify_exception(exc)
