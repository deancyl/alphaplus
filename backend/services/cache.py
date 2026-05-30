"""
Real-time data cache with TTL for pseudo-real-time updates.
Implements 5-second shared memory cache for index quotes.
"""
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import json

from backend.core import settings


class RealtimeCache:
    """
    Global memory cache for real-time market data.
    TTL-based refresh to avoid hitting free data sources too frequently.
    """
    
    def __init__(self, ttl_seconds: int = 5, stale_ttl: int = 300):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._ttl = ttl_seconds
        self._stale_ttl = stale_ttl  # Stale data TTL (default 5 minutes)
        self._stale_data: Dict[str, Any] = {}  # Preserve expired data for stale-while-revalidate
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """Initialize cache with empty values - no fake zero data."""
        # Empty initialization - will be populated with real data on first fetch
        async with self._lock:
            self._cache["indices"] = {}  # Empty, not zeros
            self._timestamps["indices"] = datetime.now()
            self._initialized = True
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache with stale-while-revalidate support.
        
        Returns:
            - Fresh data (within TTL) as-is
            - Stale data (within stale TTL) with metadata: {"_stale": True, "age_seconds": N, "data": ...}
            - None if beyond stale TTL
        """
        async with self._lock:
            if key not in self._cache:
                if key in self._stale_data:
                    timestamp = self._timestamps.get(key)
                    if timestamp:
                        elapsed = (datetime.now() - timestamp).total_seconds()
                        if elapsed <= self._stale_ttl:
                            return {
                                "_stale": True,
                                "age_seconds": int(elapsed),
                                "data": self._stale_data[key]
                            }
                return None
            
            timestamp = self._timestamps.get(key)
            if not timestamp:
                return None
            
            elapsed = (datetime.now() - timestamp).total_seconds()
            
            if elapsed <= self._ttl:
                return self._cache[key]
            
            if elapsed <= self._stale_ttl:
                self._stale_data[key] = self._cache[key]
                return {
                    "_stale": True,
                    "age_seconds": int(elapsed),
                    "data": self._cache[key]
                }
            
            return None
    
    async def get_stale(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Explicitly get stale data regardless of TTL status.
        
        Returns:
            Dict with stale metadata: {"_stale": True, "age_seconds": N, "data": ...}
            None if no stale data exists or beyond stale TTL
        """
        async with self._lock:
            if key in self._stale_data:
                timestamp = self._timestamps.get(key)
                if timestamp:
                    elapsed = (datetime.now() - timestamp).total_seconds()
                    if elapsed <= self._stale_ttl:
                        return {
                            "_stale": True,
                            "age_seconds": int(elapsed),
                            "data": self._stale_data[key]
                        }
            return None
    
    async def get_age(self, key: str) -> Optional[int]:
        """
        Get the age of cached data in seconds.
        
        Returns:
            Age in seconds if key exists, None otherwise
        """
        async with self._lock:
            timestamp = self._timestamps.get(key)
            if timestamp:
                return int((datetime.now() - timestamp).total_seconds())
            return None
    
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Set value in cache with current timestamp, preserving previous data as stale."""
        async with self._lock:
            if key in self._cache:
                self._stale_data[key] = self._cache[key]
            self._cache[key] = value
            self._timestamps[key] = datetime.now()
            if ttl_seconds is not None:
                self._cache[f"{key}_ttl"] = ttl_seconds
    
    async def get_or_refresh(self, key: str, refresh_func, ttl_seconds: Optional[int] = None) -> Any:
        """
        Get value from cache, refresh if expired.
        refresh_func is an async function that returns the fresh value.
        """
        cached = await self.get(key)
        if cached is not None:
            return cached
        
        fresh_value = await refresh_func()
        await self.set(key, fresh_value, ttl_seconds=ttl_seconds)
        return fresh_value
    
    async def clear(self):
        """Clear all cache including stale data."""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            self._stale_data.clear()
            self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized


class CorrelationCache:
    """
    Cache for correlation matrix results with 1-hour TTL.
    Keys are sorted comma-separated fund codes.
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, dict] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
    
    @staticmethod
    def make_cache_key(fund_codes: list[str]) -> str:
        """Create cache key from sorted fund codes."""
        return ",".join(sorted(fund_codes))
    
    async def get(self, fund_codes: list[str]) -> Optional[dict]:
        """Get cached correlation result."""
        key = self.make_cache_key(fund_codes)
        async with self._lock:
            if key not in self._cache:
                return None
            
            timestamp = self._timestamps.get(key)
            if not timestamp:
                return None
            
            elapsed = (datetime.now() - timestamp).total_seconds()
            if elapsed > self._ttl:
                return None
            
            return self._cache[key]
    
    async def set(self, fund_codes: list[str], result: dict):
        """Cache correlation result."""
        key = self.make_cache_key(fund_codes)
        async with self._lock:
            self._cache[key] = result
            self._timestamps[key] = datetime.now()
    
    async def clear(self):
        """Clear all cached correlations."""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()


realtime_cache = RealtimeCache(ttl_seconds=settings.cache_ttl_seconds)
correlation_cache = CorrelationCache(ttl_seconds=3600)
