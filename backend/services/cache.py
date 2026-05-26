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
    
    def __init__(self, ttl_seconds: int = 5):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """Initialize cache with default values."""
        default_indices = {
            "000001": {"name": "上证指数", "price": 0, "change": 0, "change_pct": 0},
            "399001": {"name": "深证成指", "price": 0, "change": 0, "change_pct": 0},
            "000300": {"name": "沪深300", "price": 0, "change": 0, "change_pct": 0},
            "000016": {"name": "上证50", "price": 0, "change": 0, "change_pct": 0},
            "000905": {"name": "中证500", "price": 0, "change": 0, "change_pct": 0},
            "399006": {"name": "创业板指", "price": 0, "change": 0, "change_pct": 0},
            "000688": {"name": "科创50", "price": 0, "change": 0, "change_pct": 0},
            "HSI": {"name": "恒生指数", "price": 0, "change": 0, "change_pct": 0},
        }
        
        async with self._lock:
            self._cache["indices"] = default_indices
            self._timestamps["indices"] = datetime.now()
            self._initialized = True
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
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
    
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Set value in cache with current timestamp."""
        async with self._lock:
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
        """Clear all cache."""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()
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
