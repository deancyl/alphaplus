"""
SQLite-based cache metadata manager for TieredCache.
Tracks cache entries with key, path, timestamps, and size.
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import threading

logger = logging.getLogger(__name__)

# Default metadata database path
DEFAULT_METADATA_DB = Path(__file__).parent.parent.parent / "data" / "cache_metadata.db"


class CacheMetadataManager:
    """
    SQLite-based manager for cache metadata.
    
    Tracks:
    - Cache key and associated file path
    - Created and expires timestamps
    - Entry size in bytes
    - Access count and last access time
    
    Thread-safe via connection-per-thread pattern.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize metadata manager.
        
        Args:
            db_path: Path to SQLite metadata database
        """
        self.db_path = Path(db_path or DEFAULT_METADATA_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local SQLite connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for concurrent access
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn
    
    def _init_schema(self):
        """Initialize database schema."""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_metadata (
                key TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                size_bytes INTEGER DEFAULT 0,
                access_count INTEGER DEFAULT 0,
                last_access_at TEXT,
                metadata_json TEXT
            )
        """"")
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires_at 
            ON cache_metadata(expires_at)
        """"")
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_path 
            ON cache_metadata(path)
        """"")
        conn.commit()
        logger.info(f"Initialized cache metadata database at {self.db_path}")
    
    def insert(
        self,
        key: str,
        path: str,
        ttl_seconds: int = 300,
        size_bytes: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Insert a new cache entry metadata.
        
        Args:
            key: Cache key
            path: File path for L2 cache entry
            ttl_seconds: Time-to-live in seconds
            size_bytes: Entry size in bytes
            metadata: Optional additional metadata
        
        Returns:
            True if inserted successfully
        """
        conn = self._get_connection()
        now = datetime.now()
        expires_at = now + timedelta(seconds=ttl_seconds)
        
        try:
            conn.execute("""
                INSERT OR REPLACE INTO cache_metadata 
                (key, path, created_at, expires_at, size_bytes, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                key,
                path,
                now.isoformat(),
                expires_at.isoformat(),
                size_bytes,
                json.dumps(metadata) if metadata else None,
            ))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to insert cache metadata for {key}: {e}")
            return False
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cache entry metadata by key.
        
        Args:
            key: Cache key
        
        Returns:
            Dict with metadata or None if not found
        """
        conn = self._get_connection()
        try:
            result = conn.execute("""
                SELECT * FROM cache_metadata WHERE key = ?
            """, (key,)).fetchone()
            
            if result:
                # Update access count and last access time
                conn.execute("""
                    UPDATE cache_metadata 
                    SET access_count = access_count + 1,
                        last_access_at = ?
                    WHERE key = ?
                """, (datetime.now().isoformat(), key))
                conn.commit()
                
                return {
                    "key": result["key"],
                    "path": result["path"],
                    "created_at": result["created_at"],
                    "expires_at": result["expires_at"],
                    "size_bytes": result["size_bytes"],
                    "access_count": result["access_count"],
                    "last_access_at": result["last_access_at"],
                    "metadata": json.loads(result["metadata_json"]) if result["metadata_json"] else None,
                }
            return None
        except sqlite3.Error as e:
            logger.error(f"Failed to get cache metadata for {key}: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """
        Delete cache entry metadata by key.
        
        Args:
            key: Cache key
        
        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        try:
            result = conn.execute("""
                DELETE FROM cache_metadata WHERE key = ?
            """, (key,))
            conn.commit()
            return result.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to delete cache metadata for {key}: {e}")
            return False
    
    def delete_by_path(self, path: str) -> int:
        """
        Delete cache entries by path prefix.
        
        Args:
            path: Path prefix to match
        
        Returns:
            Number of entries deleted
        """
        conn = self._get_connection()
        try:
            result = conn.execute("""
                DELETE FROM cache_metadata WHERE path LIKE ?
            """, (f"{path}%",))
            conn.commit()
            return result.rowcount
        except sqlite3.Error as e:
            logger.error(f"Failed to delete cache metadata by path {path}: {e}")
            return 0
    
    def get_expired_entries(self) -> List[Dict[str, Any]]:
        """
        Get all expired cache entries.
        
        Returns:
            List of expired entry metadata dicts
        """
        conn = self._get_connection()
        now = datetime.now()
        
        try:
            results = conn.execute("""
                SELECT * FROM cache_metadata 
                WHERE expires_at < ?
            """, (now.isoformat(),)).fetchall()
            
            return [
                {
                    "key": r["key"],
                    "path": r["path"],
                    "expires_at": r["expires_at"],
                }
                for r in results
            ]
        except sqlite3.Error as e:
            logger.error(f"Failed to get expired entries: {e}")
            return []
    
    def cleanup_expired(self, max_entries: int = 100) -> int:
        """
        Remove expired entries from metadata database.
        
        Args:
            max_entries: Maximum number of entries to cleanup
        
        Returns:
            Number of entries removed
        """
        expired = self.get_expired_entries()
        if not expired:
            return 0
        
        # Limit cleanup to avoid long transactions
        to_cleanup = expired[:max_entries]
        count = 0
        
        for entry in to_cleanup:
            if self.delete(entry["key"]):
                count += 1
        
        logger.info(f"Cleaned up {count} expired cache metadata entries")
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache metadata statistics.
        
        Returns:
            Dict with:
            - total_entries: Total number of cached entries
            - total_size_bytes: Total size in bytes
            - expired_count: Number of expired entries
            - avg_access_count: Average access count
            - hot_keys: Top 10 most accessed keys
        """
        conn = self._get_connection()
        now = datetime.now()
        
        try:
            # Total entries and size
            total_result = conn.execute("""
                SELECT 
                    COUNT(*) as total_entries,
                    SUM(size_bytes) as total_size_bytes,
                    AVG(access_count) as avg_access_count
                FROM cache_metadata
            """).fetchone()
            
            # Expired count
            expired_count = conn.execute("""
                SELECT COUNT(*) as count
                FROM cache_metadata
                WHERE expires_at < ?
            """, (now.isoformat(),)).fetchone()["count"]
            
            # Hot keys (top 10 by access count)
            hot_keys = conn.execute("""
                SELECT key, access_count, last_access_at
                FROM cache_metadata
                ORDER BY access_count DESC
                LIMIT 10
            """).fetchall()
            
            return {
                "total_entries": total_result["total_entries"] or 0,
                "total_size_bytes": total_result["total_size_bytes"] or 0,
                "expired_count": expired_count,
                "avg_access_count": round(total_result["avg_access_count"] or 0, 2),
                "hot_keys": [
                    {
                        "key": r["key"],
                        "access_count": r["access_count"],
                        "last_access_at": r["last_access_at"],
                    }
                    for r in hot_keys
                ],
            }
        except sqlite3.Error as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "total_entries": 0,
                "total_size_bytes": 0,
                "expired_count": 0,
                "avg_access_count": 0,
                "hot_keys": [],
            }
    
    def clear(self) -> int:
        """
        Clear all cache metadata.
        
        Returns:
            Number of entries removed
        """
        conn = self._get_connection()
        try:
            result = conn.execute("DELETE FROM cache_metadata")
            conn.commit()
            count = result.rowcount
            logger.info(f"Cleared {count} cache metadata entries")
            return count
        except sqlite3.Error as e:
            logger.error(f"Failed to clear cache metadata: {e}")
            return 0
    
    def close(self):
        """Close thread-local connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# Global instance
cache_metadata_manager = CacheMetadataManager()