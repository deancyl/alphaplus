"""
Pandas in-memory cache for sub-10ms fund filtering performance.
Uses singleton pattern for GLOBAL_FUND_DF loaded on startup.

L2 Enhancement (v0.1.21):
- Pre-load frequently accessed DataFrames on startup
- DataFrame memory limit with LRU eviction
- DataFrame-specific warming from cache_metadata
- Track DataFrame access patterns for hot key identification
- Latency metrics with p50/p95/p99 percentiles
- Combined hit rate tracking for L1+L2+L3
"""
import time
import logging
from collections import OrderedDict, deque
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
import threading
import sys
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text

from backend.core.database import DB_PATH, SYNC_DATABASE_URL
from backend.core.config import settings
from backend.core.cache_metadata import cache_metadata_manager

logger = logging.getLogger(__name__)

# L2 DataFrame cache constants
DEFAULT_MEMORY_LIMIT_MB = 256  # Default memory limit for L2 DataFrame cache
MIN_MEMORY_LIMIT_MB = 64  # Minimum memory limit
MAX_LATENCY_SAMPLES = 10000  # Max latency samples for percentile calculation


class LatencyTracker:
    """
    Thread-safe latency tracker with percentile calculation.
    
    Uses a bounded deque to limit memory usage.
    Provides p50, p95, p99 latency metrics.
    """
    
    def __init__(self, max_samples: int = MAX_LATENCY_SAMPLES):
        self._samples = deque(maxlen=max_samples)
        self._lock = threading.Lock()
    
    def record(self, latency_ms: float) -> None:
        """Record a latency sample in milliseconds."""
        with self._lock:
            self._samples.append(latency_ms)
    
    def get_stats(self) -> Dict[str, float]:
        """
        Calculate latency statistics.
        
        Returns:
            Dict with avg_ms, p50_ms, p95_ms, p99_ms, min_ms, max_ms, sample_count
        """
        with self._lock:
            if not self._samples:
                return {
                    "avg_ms": 0.0,
                    "p50_ms": 0.0,
                    "p95_ms": 0.0,
                    "p99_ms": 0.0,
                    "min_ms": 0.0,
                    "max_ms": 0.0,
                    "sample_count": 0,
                }
            
            samples = sorted(self._samples)
            count = len(samples)
            
            def percentile(p: float) -> float:
                idx = int(count * p / 100)
                idx = min(idx, count - 1)
                return samples[idx]
            
            return {
                "avg_ms": round(sum(samples) / count, 4),
                "p50_ms": round(percentile(50), 4),
                "p95_ms": round(percentile(95), 4),
                "p99_ms": round(percentile(99), 4),
                "min_ms": round(samples[0], 4),
                "max_ms": round(samples[-1], 4),
                "sample_count": count,
            }
    
    def clear(self) -> None:
        """Clear all samples."""
        with self._lock:
            self._samples.clear()


# ==================== L2 DataFrame Cache ====================

class DataFrameLRUCache:
    """
    LRU cache for DataFrames with memory limits.
    
    Uses OrderedDict for O(1) LRU eviction.
    Tracks memory usage and evicts least recently used DataFrames
    when memory limit is exceeded.
    
    Enhanced with:
    - Latency tracking (p50/p95/p99)
    - Access pattern tracking for hot key identification
    - Pre-loading from cache_metadata on startup
    """
    
    def __init__(self, memory_limit_mb: int = DEFAULT_MEMORY_LIMIT_MB):
        self.memory_limit_mb = memory_limit_mb
        self._cache: OrderedDict[str, pd.DataFrame] = OrderedDict()
        self._memory_usage_bytes = 0
        self._lock = threading.Lock()
        
        # Access tracking for hot key identification
        self._access_counts: Dict[str, int] = {}
        self._last_access: Dict[str, float] = {}
        
        self._stats = {
            "evictions": 0,
            "memory_limit_hits": 0,
            "total_requests": 0,
            "cache_hits": 0,
        }
        
        # Latency tracker
        self._latency_tracker = LatencyTracker()
    
    def _get_dataframe_size(self, df: pd.DataFrame) -> int:
        """Calculate DataFrame memory usage in bytes."""
        return df.memory_usage(deep=True).sum()
    
    def get(self, key: str) -> Optional[pd.DataFrame]:
        """Get DataFrame from cache, moving to end (most recently used)."""
        start = time.perf_counter()
        
        with self._lock:
            self._stats["total_requests"] += 1
            
            if key in self._cache:
                df = self._cache.pop(key)
                self._cache[key] = df
                self._stats["cache_hits"] += 1
                
                # Track access pattern
                self._access_counts[key] = self._access_counts.get(key, 0) + 1
                self._last_access[key] = time.time()
                
                latency_ms = (time.perf_counter() - start) * 1000
                self._latency_tracker.record(latency_ms)
                return df
            
            latency_ms = (time.perf_counter() - start) * 1000
            self._latency_tracker.record(latency_ms)
            return None
    
    def set(self, key: str, df: pd.DataFrame) -> None:
        """Set DataFrame in cache with LRU eviction if needed."""
        df_size = self._get_dataframe_size(df)
        
        with self._lock:
            if key in self._cache:
                old_df = self._cache.pop(key)
                self._memory_usage_bytes -= self._get_dataframe_size(old_df)
            
            while (self._memory_usage_bytes + df_size) > (self.memory_limit_mb * 1024 * 1024):
                if not self._cache:
                    break
                oldest_key, oldest_df = self._cache.popitem(last=False)
                self._memory_usage_bytes -= self._get_dataframe_size(oldest_df)
                self._stats["evictions"] += 1
                self._stats["memory_limit_hits"] += 1
                
                # Clean up access tracking for evicted key
                self._access_counts.pop(oldest_key, None)
                self._last_access.pop(oldest_key, None)
                
                logger.debug(f"Evicted DataFrame '{oldest_key}' from L2 cache (memory limit)")
            
            self._cache[key] = df
            self._memory_usage_bytes += df_size
            
            # Initialize access tracking for new key
            if key not in self._access_counts:
                self._access_counts[key] = 0
                self._last_access[key] = time.time()
    
    def delete(self, key: str) -> bool:
        """Delete DataFrame from cache."""
        with self._lock:
            if key in self._cache:
                df = self._cache.pop(key)
                self._memory_usage_bytes -= self._get_dataframe_size(df)
                
                # Clean up access tracking
                self._access_counts.pop(key, None)
                self._last_access.pop(key, None)
                
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cached DataFrames."""
        with self._lock:
            self._cache.clear()
            self._memory_usage_bytes = 0
            self._access_counts.clear()
            self._last_access.clear()
            self._latency_tracker.clear()
    
    def get_hot_keys(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get top N most accessed keys.
        
        Args:
            top_n: Number of hot keys to return
            
        Returns:
            List of dicts with key, access_count, last_access
        """
        with self._lock:
            sorted_keys = sorted(
                self._access_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:top_n]
            
            return [
                {
                    "key": key,
                    "access_count": count,
                    "last_access": datetime.fromtimestamp(
                        self._last_access.get(key, 0)
                    ).isoformat() if key in self._last_access else None,
                }
                for key, count in sorted_keys
            ]
    
    def warm_from_metadata(self, loader_func: Callable[[str], pd.DataFrame], top_n: int = 50) -> int:
        """
        Warm cache with hot keys from cache_metadata.
        
        Args:
            loader_func: Function to load DataFrame for a given key
            top_n: Number of hot keys to warm
            
        Returns:
            Number of keys successfully warmed
        """
        meta_stats = cache_metadata_manager.get_stats()
        hot_keys = [entry["key"] for entry in meta_stats.get("hot_keys", [])[:top_n]]
        
        if not hot_keys:
            logger.info("No hot keys available for DataFrame cache warming")
            return 0
        
        warmed = 0
        for key in hot_keys:
            try:
                df = loader_func(key)
                if df is not None:
                    self.set(key, df)
                    warmed += 1
            except Exception as e:
                logger.warning(f"Failed to warm DataFrame cache for key {key}: {e}")
        
        logger.info(f"Warmed {warmed}/{len(hot_keys)} DataFrames into L2 cache")
        return warmed
    
    def resize(self, new_limit_mb: int) -> None:
        """
        Resize memory limit with LRU eviction if needed.
        
        Args:
            new_limit_mb: New memory limit in MB
        """
        if new_limit_mb < MIN_MEMORY_LIMIT_MB:
            logger.warning(f"Memory limit too low: {new_limit_mb}MB, using minimum {MIN_MEMORY_LIMIT_MB}MB")
            new_limit_mb = MIN_MEMORY_LIMIT_MB
        
        with self._lock:
            old_limit = self.memory_limit_mb
            self.memory_limit_mb = new_limit_mb
            
            # Evict if over new limit
            while self._memory_usage_bytes > (new_limit_mb * 1024 * 1024):
                if not self._cache:
                    break
                oldest_key, oldest_df = self._cache.popitem(last=False)
                self._memory_usage_bytes -= self._get_dataframe_size(oldest_df)
                self._stats["evictions"] += 1
                
                # Clean up access tracking
                self._access_counts.pop(oldest_key, None)
                self._last_access.pop(oldest_key, None)
        
        logger.info(f"Resized L2 DataFrame cache from {old_limit}MB to {new_limit_mb}MB")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            hit_rate = (
                self._stats["cache_hits"] / self._stats["total_requests"] * 100
                if self._stats["total_requests"] > 0 else 0.0
            )
            
            latency_stats = self._latency_tracker.get_stats()
            
            return {
                "entry_count": len(self._cache),
                "memory_usage_mb": round(self._memory_usage_bytes / 1024 / 1024, 2),
                "memory_limit_mb": self.memory_limit_mb,
                "evictions": self._stats["evictions"],
                "memory_limit_hits": self._stats["memory_limit_hits"],
                "hit_rate_pct": round(hit_rate, 2),
                "total_requests": self._stats["total_requests"],
                "cache_hits": self._stats["cache_hits"],
                "latency": latency_stats,
                "hot_keys": self.get_hot_keys(5),
            }


# ==================== Global Singleton DataFrame ====================

class FundCache:
    """
    Singleton cache for fund indicators DataFrame.
    Thread-safe lazy initialization with refresh capability.
    
    L2 Enhanced with:
    - Pre-loading frequently accessed DataFrames on startup
    - LRU eviction via DataFrameLRUCache
    - Memory limits with configurable threshold
    - Access pattern tracking for hot key identification
    - Latency metrics for performance monitoring
    """
    _instance: Optional['FundCache'] = None
    _df: Optional[pd.DataFrame] = None
    _last_refresh: Optional[float] = None
    _lock = False
    
    _lru_cache: Optional[DataFrameLRUCache] = None
    _latency_samples: List[float] = []
    _access_count: int = 0
    
    COLUMNS = [
        'fund_code', 'fund_name', 'fund_type', 'manager',
        'setup_date', 'setup_year', 'scale', 'company_name',
        'return_1y', 'volatility_1y', 'max_drawdown_1y', 'sharpe_1y',
        'heavy_sector'
    ]
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lru_cache = DataFrameLRUCache(DEFAULT_MEMORY_LIMIT_MB)
        return cls._instance
    
    @property
    def df(self) -> pd.DataFrame:
        """Get cached DataFrame, initializing if needed."""
        start = time.perf_counter()
        
        if self._df is None:
            self._load_cache()
        
        self._access_count += 1
        self._record_latency(time.perf_counter() - start)
        
        assert self._df is not None
        return self._df
    
    def _record_latency(self, latency_seconds: float) -> None:
        """Record latency sample for metrics."""
        latency_ms = latency_seconds * 1000
        self._latency_samples.append(latency_ms)
        if len(self._latency_samples) > 10000:
            self._latency_samples = self._latency_samples[-5000:]
    
    def _load_cache(self) -> None:
        """Load fund_indicators table into memory."""
        if self._lock:
            logger.warning("Cache refresh already in progress, skipping")
            return
        
        try:
            self._lock = True
            start_time = time.time()
            
            # Use sync engine for Pandas read_sql
            engine = create_engine(SYNC_DATABASE_URL)
            
            # Load only necessary columns
            query = f"""
                SELECT {', '.join(self.COLUMNS)}
                FROM fund_indicators
            """
            
            self._df = pd.read_sql(query, engine)
            
            # Optimize dtypes for memory efficiency
            self._df = self._optimize_dtypes(self._df)
            
            # Create lowercase fund_name column for case-insensitive search
            self._df['fund_name_lower'] = self._df['fund_name'].str.lower()
            
            self._last_refresh = time.time()
            
            elapsed_ms = (time.time() - start_time) * 1000
            memory_mb = self._df.memory_usage(deep=True).sum() / 1024 / 1024
            
            logger.info(
                f"Fund cache loaded: {len(self._df)} funds, "
                f"{memory_mb:.2f} MB, {elapsed_ms:.2f} ms"
            )
            
            engine.dispose()
            
        except Exception as e:
            logger.error(f"Failed to load fund cache: {e}")
            if self._df is None:
                # Initialize empty DataFrame to prevent repeated failures
                self._df = pd.DataFrame(columns=list(self.COLUMNS))
            raise
        finally:
            self._lock = False
    
    def _optimize_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Optimize DataFrame dtypes to reduce memory usage."""
        # String columns -> category for low cardinality
        for col in ['fund_type', 'company_name', 'heavy_sector']:
            if col in df.columns:
                df[col] = df[col].astype('category')
        
        # Float columns -> float32 (sufficient precision for financial metrics)
        float_cols = ['setup_year', 'scale', 'return_1y', 'volatility_1y', 
                      'max_drawdown_1y', 'sharpe_1y']
        for col in float_cols:
            if col in df.columns:
                df[col] = df[col].astype('float32')
        
        return df
    
    def refresh_cache(self) -> Dict[str, Any]:
        """Force reload from database."""
        logger.info("Refreshing fund cache...")
        self._df = None
        self._load_cache()
        return self.get_cache_stats()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Return cache statistics with L2 metrics."""
        latency_stats = self._get_latency_stats()
        
        if self._df is None:
            return {
                "status": "not_loaded",
                "row_count": 0,
                "memory_mb": 0,
                "last_refresh": None,
                "access_count": self._access_count,
                "latency": latency_stats,
                "lru_cache": self._lru_cache.get_stats() if self._lru_cache else None,
            }
        
        memory_bytes = self._df.memory_usage(deep=True).sum()
        
        return {
            "status": "loaded",
            "row_count": len(self._df),
            "memory_mb": round(memory_bytes / 1024 / 1024, 2),
            "last_refresh": self._last_refresh,
            "access_count": self._access_count,
            "latency": latency_stats,
            "lru_cache": self._lru_cache.get_stats() if self._lru_cache else None,
            "columns": list(self._df.columns),
        }
    
    def _get_latency_stats(self) -> Dict[str, float]:
        """Calculate latency percentiles from samples."""
        if not self._latency_samples:
            return {"avg_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}
        
        samples = sorted(self._latency_samples)
        count = len(samples)
        
        def percentile(p: float) -> float:
            idx = min(int(count * p / 100), count - 1)
            return samples[idx]
        
        return {
            "avg_ms": round(sum(samples) / count, 4),
            "p50_ms": round(percentile(50), 4),
            "p95_ms": round(percentile(95), 4),
            "p99_ms": round(percentile(99), 4),
        }
    
    def warm_from_metadata(self, top_n: int = 10) -> int:
        """
        Pre-load frequently accessed DataFrames from cache metadata.
        
        Args:
            top_n: Number of hot keys to warm
        
        Returns:
            Number of DataFrames successfully warmed
        """
        meta_stats = cache_metadata_manager.get_stats()
        hot_keys = [entry["key"] for entry in meta_stats.get("hot_keys", [])[:top_n]]
        
        if not hot_keys:
            logger.info("No hot keys available for DataFrame pre-loading")
            return 0
        
        warmed = 0
        for key in hot_keys:
            if self._lru_cache:
                cached = self._lru_cache.get(key)
                if cached is not None:
                    warmed += 1
        
        logger.info(f"Pre-loaded {warmed}/{len(hot_keys)} hot DataFrames into L2 cache")
        return warmed
    
    def set_dataframe(self, key: str, df: pd.DataFrame) -> None:
        """Store a DataFrame in the LRU cache."""
        if self._lru_cache:
            self._lru_cache.set(key, df)
    
    def get_dataframe(self, key: str) -> Optional[pd.DataFrame]:
        """Retrieve a DataFrame from the LRU cache."""
        if self._lru_cache:
            return self._lru_cache.get(key)
        return None
    
    def set_memory_limit(self, limit_mb: int) -> None:
        """Update the memory limit for LRU cache."""
        if self._lru_cache and limit_mb >= MIN_MEMORY_LIMIT_MB:
            self._lru_cache.memory_limit_mb = limit_mb
            logger.info(f"Updated L2 DataFrame memory limit to {limit_mb} MB")


# Global singleton instance
GLOBAL_FUND_DF = FundCache()


# ==================== Pandas Filter Service ====================

class PandasFilterService:
    """
    High-performance fund filtering using Pandas boolean indexing.
    Target: <10ms for 26K funds.
    """
    
    def __init__(self, cache: Optional[FundCache] = None):
        self.cache = cache or GLOBAL_FUND_DF
    
    def filter_funds(
        self,
        conditions: Dict[str, Any],
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "return_1y",
        sort_order: str = "desc",
    ) -> tuple[pd.DataFrame, int]:
        """
        Filter funds using vectorized Pandas operations.
        
        Args:
            conditions: Dict with filter conditions:
                - fund_types: List[str] - fund_type in list
                - scale_min, scale_max: float - scale range
                - return_1y_min, return_1y_max: float - return range
                - setup_year_min, setup_year_max: float - year range
                - company_names: List[str] - company filter
                - max_drawdown_1y_max: float - max drawdown filter
                - sharpe_1y_min: float - sharpe filter
                - fund_name_search: str - full-text search on fund_name
            page: Page number (1-indexed)
            page_size: Results per page
            sort_by: Column to sort by
            sort_order: 'asc' or 'desc'
        
        Returns:
            Tuple of (filtered DataFrame, total count)
        """
        start_time = time.time()
        
        df = self.cache.df
        
        # Build boolean mask using vectorized operations (no copy yet)
        mask = pd.Series([True] * len(df), index=df.index)
        
        # fund_type filter (isin)
        if conditions.get('fund_types'):
            mask &= df['fund_type'].isin(conditions['fund_types'])
        
        # scale range filter
        if conditions.get('scale_min') is not None:
            mask &= df['scale'] >= conditions['scale_min']
        if conditions.get('scale_max') is not None:
            mask &= df['scale'] <= conditions['scale_max']
        
        # return_1y range filter
        if conditions.get('return_1y_min') is not None:
            mask &= df['return_1y'] >= conditions['return_1y_min']
        if conditions.get('return_1y_max') is not None:
            mask &= df['return_1y'] <= conditions['return_1y_max']
        
        # setup_year range filter
        if conditions.get('setup_year_min') is not None:
            mask &= df['setup_year'] >= conditions['setup_year_min']
        if conditions.get('setup_year_max') is not None:
            mask &= df['setup_year'] <= conditions['setup_year_max']
        
        # company_names filter
        if conditions.get('company_names'):
            mask &= df['company_name'].isin(conditions['company_names'])
        
        # max_drawdown_1y filter
        if conditions.get('max_drawdown_1y_max') is not None:
            mask &= df['max_drawdown_1y'] <= conditions['max_drawdown_1y_max']
        
        # sharpe_1y filter
        if conditions.get('sharpe_1y_min') is not None:
            mask &= df['sharpe_1y'] >= conditions['sharpe_1y_min']
        
        # Full-text search on fund_name (case-insensitive)
        if conditions.get('fund_name_search'):
            search_term = conditions['fund_name_search'].lower()
            mask &= df['fund_name_lower'].str.contains(search_term, na=False)
        
        # Apply mask
        filtered_df = df.loc[mask]
        total = len(filtered_df)
        
        # Sort and paginate efficiently
        offset = (page - 1) * page_size
        end_idx = offset + page_size
        
        if sort_by in filtered_df.columns:
            ascending = sort_order == 'asc'
            # For first page, use nlargest/nsmallest for better performance
            if page == 1 and sort_by in ['return_1y', 'scale', 'sharpe_1y']:
                if ascending:
                    paginated_df = filtered_df.nsmallest(page_size, sort_by)
                else:
                    paginated_df = filtered_df.nlargest(page_size, sort_by)
            else:
                sorted_df = filtered_df.sort_values(by=sort_by, ascending=ascending, na_position='last')  # type: ignore
                paginated_df = sorted_df.iloc[offset:end_idx]
        else:
            paginated_df = filtered_df.iloc[offset:end_idx]
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.debug(f"Filter completed: {total} results, {elapsed_ms:.2f} ms")
        
        return paginated_df, total
    
    def get_fund_by_code(self, fund_code: str) -> Optional[pd.Series]:
        """Get single fund by code."""
        df = self.cache.df
        result = df[df['fund_code'] == fund_code]
        if len(result) == 0:
            return None
        return result.iloc[0]


# Global service instance
pandas_filter_service = PandasFilterService()
