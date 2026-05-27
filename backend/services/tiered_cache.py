"""
L1/L2 Tiered Cache for v0.1.14.

L1: In-memory TTLCache (cachetools) - fast access, limited size
L2: Parquet files on disk - persistent, larger capacity

Architecture:
- get(): L1 first, then L2, then return None
- set(): Write to L1 and L2 asynchronously
- delete(): Remove from both layers
- stats(): Aggregate stats from L1, L2, and metadata
"""
import asyncio
import hashlib
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import threading

from cachetools import TTLCache
import pyarrow as pa
import pyarrow.parquet as pq

from backend.core.cache_metadata import cache_metadata_manager

logger = logging.getLogger(__name__)

# Default L2 cache directory
DEFAULT_L2_DIR = Path(__file__).parent.parent.parent / "data" / "cache"


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
        l2_dir: str = None,
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
        }
        self._stats_lock = threading.Lock()
        
        # Metadata manager
        self.metadata = cache_metadata_manager
        
        logger.info(
            f"Initialized TieredCache: L1(maxsize={l1_maxsize}, ttl={l1_ttl}s), "
            f"L2(dir={self.l2_dir}, ttl={l2_ttl}s)"
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
    
    def _l2_set(self, key: str, value: Any, ttl: int = None) -> None:
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
    
    # ==================== Public API ====================
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from tiered cache (L1 first, then L2).
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found
        """
        # Try L1 first
        value = self._l1_get(key)
        if value is not None:
            return value
        
        # Try L2
        value = self._l2_get(key)
        if value is not None:
            # Promote to L1
            self._l1_set(key, value)
            return value
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> None:
        """
        Set value in both L1 and L2 cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses defaults if None)
        """
        # Set in L1 (uses l1_ttl)
        self._l1_set(key, value)
        
        # Set in L2 (uses l2_ttl or provided ttl)
        self._l2_set(key, value, ttl)
    
    def delete(self, key: str) -> bool:
        """
        Delete value from both L1 and L2 cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if deleted from either layer
        """
        l1_deleted = self._l1_delete(key)
        l2_deleted = self._l2_delete(key)
        return l1_deleted or l2_deleted
    
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
        
        # Reset stats
        with self._stats_lock:
            self._stats = {
                "l1_hits": 0,
                "l1_misses": 0,
                "l2_hits": 0,
                "l2_misses": 0,
                "l2_evictions": 0,
            }
        
        logger.info("Cleared all cache layers")
    
    def stats(self) -> Dict[str, Any]:
        """
        Get aggregated cache statistics.
        
        Returns:
            Dict with:
            - l1: L1 cache stats (size, maxsize, hits, misses, hit_rate)
            - l2: L2 cache stats (total_entries, size_bytes, hits, misses)
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
        
        # Calculate hit rates
        l1_total = l1_hits + l1_misses
        l1_hit_rate = (l1_hits / l1_total * 100) if l1_total > 0 else 0.0
        
        l2_total = l2_hits + l2_misses
        l2_hit_rate = (l2_hits / l2_total * 100) if l2_total > 0 else 0.0
        
        # Get metadata stats
        meta_stats = self.metadata.get_stats()
        
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


# Global tiered cache instance
tiered_cache = TieredCache()