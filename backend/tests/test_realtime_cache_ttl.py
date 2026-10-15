"""Regression: RealtimeCache must honor per-key ttl_seconds.

set(key, value, ttl_seconds=N) used to store the TTL in _cache[f"{key}_ttl"]
which get() never read, so every caller's explicit TTL was silently replaced
by the global default (30s). Consequences in production: gold (60s) refetched
the 9s upstream every 30s, deposit (900s) never cached at all.
"""
import asyncio
from datetime import datetime, timedelta

import pytest

from backend.services.cache import RealtimeCache


@pytest.mark.asyncio
async def test_per_key_ttl_is_honored(monkeypatch):
    cache = RealtimeCache(ttl_seconds=30)

    await cache.set("a", {"v": 1}, ttl_seconds=900)
    await cache.set("b", {"v": 2})  # no override -> global 30s

    # Pretend both were written 5 minutes ago: "a" (900s) must still be
    # fresh, "b" (30s) must have aged out of the fresh window.
    old = datetime.now() - timedelta(seconds=300)
    cache._timestamps["a"] = old
    cache._timestamps["b"] = old

    a = await cache.get("a")
    b = await cache.get("b")

    assert a == {"v": 1}, "per-key TTL 900s ignored — value expired at global 30s"
    assert b is None or (isinstance(b, dict) and "_stale" in b), \
        "global-TTL key must NOT be fresh after 300s"


@pytest.mark.asyncio
async def test_fresh_value_returned_as_is():
    cache = RealtimeCache(ttl_seconds=30)
    await cache.set("k", {"v": 1}, ttl_seconds=60)
    assert await cache.get("k") == {"v": 1}


@pytest.mark.asyncio
async def test_clear_removes_ttl_overrides():
    cache = RealtimeCache(ttl_seconds=30)
    await cache.set("k", {"v": 1}, ttl_seconds=900)
    await cache.clear()
    await cache.set("k", {"v": 2})
    assert "k" not in cache._per_key_ttl, "stale per-key TTL survived clear()"


@pytest.mark.asyncio
async def test_ttl_entry_does_not_pollute_cache_keys():
    """set(..., ttl_seconds) must not create a phantom "{key}_ttl" entry."""
    cache = RealtimeCache(ttl_seconds=30)
    await cache.set("k", {"v": 1}, ttl_seconds=900)
    assert "k_ttl" not in cache._cache
    assert cache._cache["k"] == {"v": 1}
