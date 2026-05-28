"""
L1/L2/L3 Tiered Cache for v0.1.14+.

L1: In-memory TTLCache (cachetools) - fast access, limited size
L2: Parquet files on disk - persistent, larger capacity
L3: Pandas DataFrame LRU cache - for fund data with memory limits

Architecture:
- get(): L1 first, then L2, then L3, then return None
- set(): Write to L1, L2, and optionally L3
- delete(): Remove from all layers
- stats(): Aggregate stats from all layers with combined hit rate
"""
import asyncio
import hashlib
import logging
import pickle
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading

from cachetools import TTLCache
import pyarrow as pa
import pyarrow.parquet as pq

from backend.core.cache_metadata import cache_metadata_manager
from backend.services.parquet_cache import (
    parquet_latency_metrics,
    get_parquet_cache_stats,
    load_holdings_from_parquet,
    export_holdings_to_parquet,
    CACHE_DIR as PARQUET_CACHE_DIR,
)
from backend.services.pandas_cache import GLOBAL_FUND_DF, DataFrameLRUCache

logger = logging.getLogger(__name__)

DEFAULT_L2_DIR = Path(__file__).parent.parent.parent / "data" / "cache"


class LatencyMetrics:
    """
    Thread-safe latency metrics collector.
    
    Tracks latency samples and calculates percentiles.
    Uses a bounded deque to limit memory usage.
    """
    
    def __init__(self, max_samples: int = 10000):
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


class TieredCache:
    """
    Two-tier cache with L1 (memory) and L2 (Parquet) storage.
    
    Thread-safe via asyncio locks for L1 and metadata operations.
    L2 uses atomic writes to prevent corruption.
    """
    
    def __init__(
        self,
        l1_maxsize: int = 1000,
        l1_ttl: int = 300,
        l2_dir: Optional[str] = None,
        l2_ttl: int = 3600,
    ):
        """
        Initialize tiered cache.
        
        Args:
            l1_maxsize: Maximum number of entries in L1 cache
            l1_ttl: TTL for L1 cache entries in seconds (default: 5 min)
            l2_dir: Directory for L2 Parquet cache files
            l2_ttl: TTL for L2 cache entries in seconds (default: 1 hour)
        """
        self.l1_maxsize = l1_maxsize
        self.l1_ttl = l1_ttl
        self.l2_ttl = l2_ttl
        
        # L1: In-memory TTL cache
        self._l1_cache = TTLCache(maxsize=l1_maxsize, ttl=l1_ttl)
        self._l1_lock = threading.Lock()
        
        # L2: Parquet cache directory
        self.l2_dir = Path(l2_dir or DEFAULT_L2_DIR)
        self.l2_dir.mkdir(parents=True, exist_ok=True)
        
        # Stats tracking
        self._stats = {
            "l1_hits": 0,
            "l1_misses": 0,
            "l2_hits": 0,
            "l2_misses": 0,
            "l2_evictions": 0,
            "l3_hits": 0,
            "l3_misses": 0,
        }
        self._stats_lock = threading.Lock()
        
        self._latency_metrics = LatencyMetrics()
        
        self.metadata = cache_metadata_manager
        
        # L3: DataFrame LRU cache (via FundCache singleton)
        self._l3_cache = GLOBAL_FUND_DF
        
        logger.info(
            f"Initialized TieredCache: L1(maxsize={l1_maxsize}, ttl={l1_ttl}s), "
            f"L2(dir={self.l2_dir}, ttl={l2_ttl}s), "
            f"L3(DataFrame LRU cache)"
        )
    
    def _key_to_path(self, key: str) -> Path:
        """
        Convert cache key to Parquet file path.
        
        Uses SHA256 hash to avoid invalid characters in filenames.
        
        Args:
            key: Cache key string
        
        Returns:
            Path object for L2 cache file
        """
        # Hash key for safe filename
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.l2_dir / f"{key_hash}.parquet"
    
    # ==================== L1 Operations ====================
    
    def _l1_get(self, key: str) -> Optional[Any]:
        """
        Get value from L1 cache.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found
        """
        with self._l1_lock:
            try:
                value = self._l1_cache.get(key)
                if value is not None:
                    with self._stats_lock:
                        self._stats["l1_hits"] += 1
                    return value
            except KeyError:
                pass
        
        with self._stats_lock:
            self._stats["l1_misses"] += 1
        return None
    
    def _l1_set(self, key: str, value: Any) -> None:
        """
        Set value in L1 cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self._l1_lock:
            self._l1_cache[key] = value
    
    def _l1_delete(self, key: str) -> bool:
        """
        Delete value from L1 cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if deleted, False if not found
        """
        with self._l1_lock:
            try:
                del self._l1_cache[key]
                return True
            except KeyError:
                return False
    
    # ==================== L2 Operations ====================
    
    def _l2_get(self, key: str) -> Optional[Any]:
        """
        Get value from L2 Parquet cache.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found/expired
        """
        # Check metadata first
        meta = self.metadata.get(key)
        if meta is None:
            with self._stats_lock:
                self._stats["l2_misses"] += 1
            return None
        
        # Check expiration
        expires_at = datetime.fromisoformat(meta["expires_at"])
        if datetime.now() > expires_at:
            # Entry expired, clean up
            self._l2_delete(key)
            with self._stats_lock:
                self._stats["l2_evictions"] += 1
                self._stats["l2_misses"] += 1
            return None
        
        # Read from Parquet file
        path = Path(meta["path"])
        if not path.exists():
            self.metadata.delete(key)
            with self._stats_lock:
                self._stats["l2_misses"] += 1
            return None
        
        try:
            table = pq.read_table(path)
            # First row contains the value
            df = table.to_pandas()
            if df.empty:
                return None
            
            # Deserialize value (stored as pickled bytes)
            value_bytes = df.iloc[0]["value"]
            value = pickle.loads(value_bytes)
            
            with self._stats_lock:
                self._stats["l2_hits"] += 1
            
            return value
            
        except Exception as e:
            logger.error(f"Failed to read L2 cache for key {key}: {e}")
            self.metadata.delete(key)
            with self._stats_lock:
                self._stats["l2_misses"] += 1
            return None
    
    def _l2_set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Write value to L2 Parquet cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses l2_ttl if None)
        """
        ttl = ttl or self.l2_ttl
        path = self._key_to_path(key)
        
        try:
            # Serialize value to bytes
            value_bytes = pickle.dumps(value)
            
            # Create PyArrow table
            df = pa.table({
                "key": [key],
                "value": [value_bytes],
                "timestamp": [datetime.now().isoformat()],
            })
            
            # Write to temp file first for atomic write
            temp_path = path.with_suffix(".tmp")
            pq.write_table(df, temp_path, compression="snappy")
            
            # Atomic rename
            temp_path.rename(path)
            
            # Update metadata
            size_bytes = path.stat().st_size
            self.metadata.insert(
                key=key,
                path=str(path),
                ttl_seconds=ttl,
                size_bytes=size_bytes,
            )
            
        except Exception as e:
            logger.error(f"Failed to write L2 cache for key {key}: {e}")
            # Clean up temp file if exists
            temp_path = path.with_suffix(".tmp")
            if temp_path.exists():
                temp_path.unlink()
    
    def _l2_delete(self, key: str) -> bool:
        """
        Delete value from L2 Parquet cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if deleted, False if not found
        """
        meta = self.metadata.get(key)
        if meta is None:
            return False
        
        # Delete Parquet file
        path = Path(meta["path"])
        if path.exists():
            try:
                path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete L2 cache file {path}: {e}")
        
        # Delete metadata
        self.metadata.delete(key)
        return True
    
    # ==================== L3 Operations ====================
    
    def _l3_get_dataframe(self, key: str) -> Optional[Any]:
        """
        Get DataFrame from L3 cache (FundCache LRU).
        
        Args:
            key: Cache key
        
        Returns:
            Cached DataFrame or None if not found
        """
        if self._l3_cache and self._l3_cache._lru_cache:
            df = self._l3_cache.get_dataframe(key)
            if df is not None:
                with self._stats_lock:
                    self._stats["l3_hits"] += 1
                return df
        
        with self._stats_lock:
            self._stats["l3_misses"] += 1
        return None
    
    def _l3_set_dataframe(self, key: str, df: Any) -> None:
        """
        Set DataFrame in L3 cache (FundCache LRU).
        
        Args:
            key: Cache key
            df: DataFrame to cache
        """
        if self._l3_cache and self._l3_cache._lru_cache:
            self._l3_cache.set_dataframe(key, df)
    
    # ==================== Public API ====================
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from tiered cache (L1 first, then L2, then L3).
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found
        """
        start = time.perf_counter()
        
        # Try L1 first (fastest)
        value = self._l1_get(key)
        if value is not None:
            latency_ms = (time.perf_counter() - start) * 1000
            self._latency_metrics.record(latency_ms)
            return value
        
        # Try L2 (Parquet files)
        value = self._l2_get(key)
        if value is not None:
            self._l1_set(key, value)  # Promote to L1
            latency_ms = (time.perf_counter() - start) * 1000
            self._latency_metrics.record(latency_ms)
            return value
        
        # Try L3 (DataFrame LRU) for DataFrame keys
        if key.startswith("dataframe:") or key.startswith("fund_"):
            value = self._l3_get_dataframe(key)
            if value is not None:
                self._l1_set(key, value)  # Promote to L1
                latency_ms = (time.perf_counter() - start) * 1000
                self._latency_metrics.record(latency_ms)
                return value
        
        latency_ms = (time.perf_counter() - start) * 1000
        self._latency_metrics.record(latency_ms)
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache layers based on value type.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses defaults if None)
        """
        # Always set in L1 (uses l1_ttl)
        self._l1_set(key, value)
        
        # Set in L2 (uses l2_ttl or provided ttl)
        self._l2_set(key, value, ttl)
        
        # Set in L3 for DataFrames
        if key.startswith("dataframe:") or key.startswith("fund_"):
            try:
                import pandas as pd
                if isinstance(value, pd.DataFrame):
                    self._l3_set_dataframe(key, value)
            except ImportError:
                pass
    
    def delete(self, key: str) -> bool:
        """
        Delete value from all cache layers.
        
        Args:
            key: Cache key
        
        Returns:
            True if deleted from any layer
        """
        l1_deleted = self._l1_delete(key)
        l2_deleted = self._l2_delete(key)
        
        # Delete from L3 if DataFrame key
        l3_deleted = False
        if key.startswith("dataframe:") or key.startswith("fund_"):
            if self._l3_cache and self._l3_cache._lru_cache:
                l3_deleted = self._l3_cache._lru_cache.delete(key)
        
        return l1_deleted or l2_deleted or l3_deleted
    
    def clear(self) -> None:
        """
        Clear both L1 and L2 cache.
        """
        # Clear L1
        with self._l1_lock:
            self._l1_cache.clear()
        
        # Clear L2 files
        for cache_file in self.l2_dir.glob("*.parquet"):
            try:
                cache_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete L2 cache file {cache_file}: {e}")
        
        # Clear metadata
        self.metadata.clear()
        
        with self._stats_lock:
            self._stats = {
                "l1_hits": 0,
                "l1_misses": 0,
                "l2_hits": 0,
                "l2_misses": 0,
                "l2_evictions": 0,
                "l3_hits": 0,
                "l3_misses": 0,
            }
        
        self._latency_metrics.clear()
        
        logger.info("Cleared all cache layers")
    
    def stats(self) -> Dict[str, Any]:
        """
        Get aggregated cache statistics from all layers.
        
        Returns:
            Dict with:
            - l1: L1 cache stats (size, maxsize, hits, misses, hit_rate)
            - l2: L2 cache stats (total_entries, size_bytes, hits, misses)
            - l3: L3 Parquet stats (file_count, partitions, latency)
            - combined: Combined hit rate across all layers
            - latency: Latency metrics (avg_ms, p50_ms, p95_ms, p99_ms)
            - metadata: Metadata stats from SQLite
        """
        with self._l1_lock:
            l1_size = len(self._l1_cache)
        
        with self._stats_lock:
            l1_hits = self._stats["l1_hits"]
            l1_misses = self._stats["l1_misses"]
            l2_hits = self._stats["l2_hits"]
            l2_misses = self._stats["l2_misses"]
            l2_evictions = self._stats["l2_evictions"]
            l3_hits = self._stats["l3_hits"]
            l3_misses = self._stats["l3_misses"]
        
        l1_total = l1_hits + l1_misses
        l1_hit_rate = (l1_hits / l1_total * 100) if l1_total > 0 else 0.0
        
        l2_total = l2_hits + l2_misses
        l2_hit_rate = (l2_hits / l2_total * 100) if l2_total > 0 else 0.0
        
        l3_total = l3_hits + l3_misses
        l3_hit_rate = (l3_hits / l3_total * 100) if l3_total > 0 else 0.0
        
        total_requests = l1_total + l2_total + l3_total
        total_hits = l1_hits + l2_hits + l3_hits
        combined_hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0.0
        
        meta_stats = self.metadata.get_stats()
        latency_stats = self._latency_metrics.get_stats()
        l3_parquet_stats = get_parquet_cache_stats()
        
        # Get DataFrame LRU stats from FundCache
        l3_dataframe_stats = {}
        if self._l3_cache:
            fund_cache_stats = self._l3_cache.get_cache_stats()
            l3_dataframe_stats = {
                "status": fund_cache_stats.get("status", "unknown"),
                "row_count": fund_cache_stats.get("row_count", 0),
                "memory_mb": fund_cache_stats.get("memory_mb", 0),
                "access_count": fund_cache_stats.get("access_count", 0),
                "latency": fund_cache_stats.get("latency", {}),
            }
            if fund_cache_stats.get("lru_cache"):
                l3_dataframe_stats["lru_cache"] = fund_cache_stats["lru_cache"]
        
        return {
            "l1": {
                "size": l1_size,
                "maxsize": self.l1_maxsize,
                "ttl_seconds": self.l1_ttl,
                "hits": l1_hits,
                "misses": l1_misses,
                "hit_rate_pct": round(l1_hit_rate, 2),
            },
            "l2": {
                "hits": l2_hits,
                "misses": l2_misses,
                "evictions": l2_evictions,
                "hit_rate_pct": round(l2_hit_rate, 2),
                "total_entries": meta_stats["total_entries"],
                "total_size_bytes": meta_stats["total_size_bytes"],
                "expired_count": meta_stats["expired_count"],
            },
            "l3": {
                "hits": l3_hits,
                "misses": l3_misses,
                "hit_rate_pct": round(l3_hit_rate, 2),
                "parquet": {
                    "file_count": l3_parquet_stats["file_count"],
                    "total_size_mb": l3_parquet_stats.get("total_size_mb", 0),
                    "partitions": l3_parquet_stats.get("partitions", []),
                    "latency": l3_parquet_stats.get("latency", {}),
                },
                "dataframe": l3_dataframe_stats,
            },
            "combined": {
                "total_requests": total_requests,
                "total_hits": total_hits,
                "hit_rate_pct": round(combined_hit_rate, 2),
                "target_hit_rate_pct": 90.0,
                "target_achieved": combined_hit_rate >= 90.0,
            },
            "latency": latency_stats,
            "metadata": meta_stats,
        }
    
    def cleanup_expired(self, max_entries: int = 100) -> int:
        """
        Clean up expired L2 cache entries.
        
        Args:
            max_entries: Maximum number of entries to cleanup
        
        Returns:
            Number of entries cleaned up
        """
        expired = self.metadata.get_expired_entries()
        if not expired:
            return 0
        
        count = 0
        for entry in expired[:max_entries]:
            key = entry["key"]
            path = Path(entry["path"])
            
            # Delete file
            if path.exists():
                try:
                    path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete expired cache file {path}: {e}")
                    continue
            
            # Delete metadata
            self.metadata.delete(key)
            count += 1
            
            with self._stats_lock:
                self._stats["l2_evictions"] += 1
        
        logger.info(f"Cleaned up {count} expired L2 cache entries")
        return count
    
    async def warm_cache(self, hot_keys: Optional[List[str]] = None, top_n: int = 100) -> int:
        """
        Warm L1 cache with hot keys on startup.
        
        Loads frequently accessed keys from L2 to L1 to reduce
        initial latency for common queries.
        
        Args:
            hot_keys: Optional list of keys to warm (uses metadata if None)
            top_n: Number of top hot keys to warm from metadata
        
        Returns:
            Number of keys successfully warmed
        """
        if hot_keys is None:
            meta_stats = self.metadata.get_stats()
            hot_keys = [entry["key"] for entry in meta_stats.get("hot_keys", [])[:top_n]]
        
        if not hot_keys:
            logger.info("No hot keys available for cache warming")
            return 0
        
        warmed_count = 0
        for key in hot_keys:
            try:
                value = self._l2_get(key)
                if value is not None:
                    self._l1_set(key, value)
                    warmed_count += 1
            except Exception as e:
                logger.warning(f"Failed to warm cache for key {key}: {e}")
        
        logger.info(f"Warmed {warmed_count}/{len(hot_keys)} hot keys into L1 cache")
        return warmed_count
    
    def resize_l1(self, new_maxsize: int) -> None:
        """
        Resize L1 cache capacity.
        
        Creates a new TTLCache with updated maxsize while preserving
        existing entries that haven't expired.
        
        Args:
            new_maxsize: New maximum size for L1 cache
        """
        if new_maxsize <= 0:
            logger.warning(f"Invalid L1 maxsize {new_maxsize}, keeping current size {self.l1_maxsize}")
            return
        
        with self._l1_lock:
            old_cache = self._l1_cache
            self._l1_cache = TTLCache(maxsize=new_maxsize, ttl=self.l1_ttl)
            
            for key, value in list(old_cache.items()):
                try:
                    self._l1_cache[key] = value
                except ValueError:
                    break
        
        self.l1_maxsize = new_maxsize
        logger.info(f"Resized L1 cache from {old_cache.maxsize} to {new_maxsize}")


# Global tiered cache instance
tiered_cache = TieredCache()