"""
Risk-free rate lookup service with caching.

Provides functions to fetch:
- 10-year Treasury yield (国债)
- 10-year CDB yield (国开债)
- DR007 rate (银行间存款类金融机构7天期质押式回购利率)
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import akshare as ak

logger = logging.getLogger(__name__)


class RiskFreeRateCache:
    """
    Cache for risk-free rates with 1-hour TTL.
    Thread-safe async implementation.
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
    
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
    
    async def set(self, key: str, value: Any):
        """Set value in cache with current timestamp."""
        async with self._lock:
            self._cache[key] = value
            self._timestamps[key] = datetime.now()
    
    async def clear(self):
        """Clear all cached rates."""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()


# Global cache instance with 1-hour TTL
_rate_cache = RiskFreeRateCache(ttl_seconds=3600)


async def get_treasury_yield_10y() -> float:
    """
    Fetch 10-year Treasury yield from AkShare.
    
    Returns:
        float: 10-year Treasury yield as percentage (e.g., 2.5 for 2.5%)
    """
    cache_key = "treasury_10y"
    cached = await _rate_cache.get(cache_key)
    if cached is not None:
        return cached
    
    try:
        df = ak.bond_china_yield(start_date=datetime.now().strftime("%Y%m%d"))
        # Filter for 国债 type
        treasury_df = df[df['债券类型'] == '国债']
        if not treasury_df.empty:
            # Try to get 10年期 column first
            if '10年期' in treasury_df.columns:
                yield_10y = float(treasury_df['10年期'].iloc[0])
            elif '收益率' in treasury_df.columns:
                yield_10y = float(treasury_df['收益率'].iloc[0])
            else:
                raise ValueError("No yield column found")
            
            await _rate_cache.set(cache_key, yield_10y)
            return yield_10y
    except Exception as e:
        logger.warning(f"Failed to fetch treasury yield: {e}")
    
    # Fallback value
    return 2.5


async def get_cdb_yield_10y() -> float:
    """
    Fetch 10-year CDB (国开债) yield from AkShare.
    
    Returns:
        float: 10-year CDB yield as percentage (e.g., 2.6 for 2.6%)
    """
    cache_key = "cdb_10y"
    cached = await _rate_cache.get(cache_key)
    if cached is not None:
        return cached
    
    try:
        df = ak.bond_china_yield(start_date=datetime.now().strftime("%Y%m%d"))
        # Filter for 国开债 type
        cdb_df = df[df['债券类型'] == '国开债']
        if not cdb_df.empty:
            # Try to get 10年期 column first
            if '10年期' in cdb_df.columns:
                yield_10y = float(cdb_df['10年期'].iloc[0])
            elif '收益率' in cdb_df.columns:
                yield_10y = float(cdb_df['收益率'].iloc[0])
            else:
                raise ValueError("No yield column found")
            
            await _rate_cache.set(cache_key, yield_10y)
            return yield_10y
    except Exception as e:
        logger.warning(f"Failed to fetch CDB yield: {e}")
    
    # Fallback value
    return 2.6


async def get_dr007_rate() -> float:
    """
    Fetch DR007 rate from AkShare and annualize it.
    
    DR007 is a 7-day rate, so we annualize it by multiplying by 52.
    
    Returns:
        float: Annualized DR007 rate as percentage (e.g., 2.0 for 2.0%)
    """
    cache_key = "dr007"
    cached = await _rate_cache.get(cache_key)
    if cached is not None:
        return cached
    
    try:
        df = ak.rate_interbank()
        # Filter for DR007
        dr007_df = df[df['利率类型'] == 'DR007']
        if not dr007_df.empty:
            # Get the rate (7-day rate)
            rate_7d = float(dr007_df['利率'].iloc[0])
            # Annualize: multiply by 52 weeks
            annualized = rate_7d * 52
            
            await _rate_cache.set(cache_key, annualized)
            return annualized
    except Exception as e:
        logger.warning(f"Failed to fetch DR007: {e}")
    
    # Fallback value
    return 2.0


async def get_risk_free_rate(rate_type: str) -> float:
    """
    Get risk-free rate by type.
    
    Args:
        rate_type: "treasury_10y", "cdb_10y", or "dr007"
    
    Returns:
        float: Annual risk-free rate as percentage (e.g., 2.5 for 2.5%)
    
    Raises:
        ValueError: If rate_type is not recognized
    """
    if rate_type == "treasury_10y":
        return await get_treasury_yield_10y()
    elif rate_type == "cdb_10y":
        return await get_cdb_yield_10y()
    elif rate_type == "dr007":
        return await get_dr007_rate()
    else:
        raise ValueError(f"Unknown rate_type: {rate_type}. Must be one of: treasury_10y, cdb_10y, dr007")
