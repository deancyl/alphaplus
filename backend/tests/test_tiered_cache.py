"""
Tests for TieredCache L1/L2 implementation.
"""
import tempfile
import time
from pathlib import Path
from datetime import datetime, timedelta

import pytest

from backend.services.tiered_cache import TieredCache
from backend.core.cache_metadata import CacheMetadataManager


class TestTieredCache:
    """Tests for TieredCache class."""
    
    @pytest.fixture
    def temp_cache_dir(self, tmp_path):
        return str(tmp_path / "cache")
    
    @pytest.fixture
    def temp_metadata_db(self, tmp_path):
        return str(tmp_path / "metadata.db")
    
    @pytest.fixture
    def tiered_cache(self, temp_cache_dir, temp_metadata_db):
        cache = TieredCache(
            l1_maxsize=10,
            l1_ttl=2,
            l2_dir=temp_cache_dir,
            l2_ttl=5,
        )
        cache.metadata = CacheMetadataManager(temp_metadata_db)
        yield cache
        cache.clear()
    
    def test_l1_set_and_get(self, tiered_cache):
        tiered_cache._l1_set("test_key", {"data": "value"})
        
        result = tiered_cache._l1_get("test_key")
        
        assert result == {"data": "value"}
    
    def test_l1_get_missing_key(self, tiered_cache):
        result = tiered_cache._l1_get("nonexistent")
        
        assert result is None
    
    def test_l1_ttl_expiration(self, tiered_cache):
        tiered_cache._l1_set("expire_key", "value")
        
        time.sleep(2.1)
        
        result = tiered_cache._l1_get("expire_key")
        
        assert result is None
    
    def test_l1_delete(self, tiered_cache):
        tiered_cache._l1_set("delete_key", "value")
        
        deleted = tiered_cache._l1_delete("delete_key")
        
        assert deleted is True
        assert tiered_cache._l1_get("delete_key") is None
    
    def test_l1_delete_missing_key(self, tiered_cache):
        deleted = tiered_cache._l1_delete("nonexistent")
        
        assert deleted is False
    
    def test_l2_set_and_get(self, tiered_cache):
        tiered_cache._l2_set("l2_key", {"nested": "data"})
        
        result = tiered_cache._l2_get("l2_key")
        
        assert result == {"nested": "data"}
    
    def test_l2_get_missing_key(self, tiered_cache):
        result = tiered_cache._l2_get("nonexistent_l2")
        
        assert result is None
    
    def test_l2_ttl_expiration(self, tiered_cache):
        tiered_cache._l2_set("expire_l2", "value", ttl=1)
        
        time.sleep(1.1)
        
        result = tiered_cache._l2_get("expire_l2")
        
        assert result is None
    
    def test_l2_delete(self, tiered_cache):
        tiered_cache._l2_set("delete_l2", "value")
        
        deleted = tiered_cache._l2_delete("delete_l2")
        
        assert deleted is True
        assert tiered_cache._l2_get("delete_l2") is None
    
    def test_get_l1_hit(self, tiered_cache):
        tiered_cache._l1_set("hit_key", "l1_value")
        
        result = tiered_cache.get("hit_key")
        
        assert result == "l1_value"
        stats = tiered_cache.stats()
        assert stats["l1"]["hits"] == 1
        assert stats["l2"]["hits"] == 0
    
    def test_get_l2_hit_and_promotion(self, tiered_cache):
        tiered_cache._l2_set("promote_key", "l2_value")
        tiered_cache._l1_delete("promote_key")
        
        result = tiered_cache.get("promote_key")
        
        assert result == "l2_value"
        stats = tiered_cache.stats()
        assert stats["l2"]["hits"] == 1
        
        assert tiered_cache._l1_get("promote_key") == "l2_value"
    
    def test_get_complete_miss(self, tiered_cache):
        result = tiered_cache.get("complete_miss")
        
        assert result is None
        stats = tiered_cache.stats()
        assert stats["l1"]["misses"] == 1
        assert stats["l2"]["misses"] == 1
    
    def test_set_writes_to_both_layers(self, tiered_cache):
        tiered_cache.set("both_key", "value")
        
        assert tiered_cache._l1_get("both_key") == "value"
        assert tiered_cache._l2_get("both_key") == "value"
    
    def test_delete_removes_from_both_layers(self, tiered_cache):
        tiered_cache.set("delete_both", "value")
        
        tiered_cache.delete("delete_both")
        
        assert tiered_cache._l1_get("delete_both") is None
        assert tiered_cache._l2_get("delete_both") is None
    
    def test_clear_removes_all_entries(self, tiered_cache):
        tiered_cache.set("key1", "value1")
        tiered_cache.set("key2", "value2")
        tiered_cache.set("key3", "value3")
        
        tiered_cache.clear()
        
        assert tiered_cache.get("key1") is None
        assert tiered_cache.get("key2") is None
        assert tiered_cache.get("key3") is None
    
    def test_stats_aggregation(self, tiered_cache):
        tiered_cache.set("stat1", "value1")
        tiered_cache.get("stat1")  # L1 hit
        tiered_cache._l1_delete("stat1")
        tiered_cache.get("stat1")  # L2 hit
        tiered_cache.get("missing")  # Miss
        
        stats = tiered_cache.stats()
        
        assert stats["l1"]["hits"] == 1
        assert stats["l1"]["misses"] == 2
        assert stats["l2"]["hits"] == 1
        assert stats["l2"]["misses"] == 1
    
    def test_complex_data_types(self, tiered_cache):
        complex_data = {
            "string": "value",
            "int": 42,
            "float": 3.14,
            "list": [1, 2, 3],
            "nested": {"a": 1, "b": 2},
        }
        
        tiered_cache.set("complex", complex_data)
        result = tiered_cache.get("complex")
        
        assert result == complex_data
    
    def test_large_data(self, tiered_cache):
        large_list = list(range(10000))
        
        tiered_cache.set("large", large_list)
        result = tiered_cache.get("large")
        
        assert result == large_list
    
    def test_l1_maxsize_eviction(self, temp_cache_dir, temp_metadata_db):
        cache = TieredCache(
            l1_maxsize=3,
            l1_ttl=100,
            l2_dir=temp_cache_dir,
        )
        cache.metadata = CacheMetadataManager(temp_metadata_db)
        
        cache._l1_set("key1", "v1")
        cache._l1_set("key2", "v2")
        cache._l1_set("key3", "v3")
        cache._l1_set("key4", "v4")
        
        assert cache._l1_get("key1") is None or cache._l1_get("key2") is None
        cache.clear()


class TestCacheMetadataManager:
    """Tests for CacheMetadataManager class."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        return str(tmp_path / "test_metadata.db")
    
    @pytest.fixture
    def metadata_manager(self, temp_db):
        manager = CacheMetadataManager(temp_db)
        yield manager
        manager.close()
    
    def test_insert_and_get(self, metadata_manager):
        metadata_manager.insert(
            key="test_key",
            path="/cache/test.parquet",
            ttl_seconds=300,
            size_bytes=1024,
        )
        
        result = metadata_manager.get("test_key")
        
        assert result is not None
        assert result["key"] == "test_key"
        assert result["path"] == "/cache/test.parquet"
        assert result["size_bytes"] == 1024
    
    def test_get_missing_key(self, metadata_manager):
        result = metadata_manager.get("nonexistent")
        
        assert result is None
    
    def test_delete(self, metadata_manager):
        metadata_manager.insert("delete_key", "/path", 300)
        
        deleted = metadata_manager.delete("delete_key")
        
        assert deleted is True
        assert metadata_manager.get("delete_key") is None
    
    def test_delete_missing_key(self, metadata_manager):
        deleted = metadata_manager.delete("nonexistent")
        
        assert deleted is False
    
    def test_get_expired_entries(self, metadata_manager):
        metadata_manager.insert("expired", "/path1", ttl_seconds=0)
        metadata_manager.insert("valid", "/path2", ttl_seconds=3600)
        
        time.sleep(0.1)
        
        expired = metadata_manager.get_expired_entries()
        
        assert len(expired) == 1
        assert expired[0]["key"] == "expired"
    
    def test_cleanup_expired(self, metadata_manager):
        metadata_manager.insert("expired1", "/path1", ttl_seconds=0)
        metadata_manager.insert("expired2", "/path2", ttl_seconds=0)
        metadata_manager.insert("valid", "/path3", ttl_seconds=3600)
        
        time.sleep(0.1)
        
        cleaned = metadata_manager.cleanup_expired()
        
        assert cleaned == 2
        assert metadata_manager.get("valid") is not None
    
    def test_get_stats(self, metadata_manager):
        metadata_manager.insert("key1", "/path1", ttl_seconds=3600, size_bytes=100)
        metadata_manager.insert("key2", "/path2", ttl_seconds=3600, size_bytes=200)
        
        metadata_manager.get("key1")
        metadata_manager.get("key1")
        metadata_manager.get("key2")
        
        stats = metadata_manager.get_stats()
        
        assert stats["total_entries"] == 2
        assert stats["total_size_bytes"] == 300
        assert len(stats["hot_keys"]) == 2
    
    def test_clear(self, metadata_manager):
        metadata_manager.insert("key1", "/path1", 300)
        metadata_manager.insert("key2", "/path2", 300)
        
        cleared = metadata_manager.clear()
        
        assert cleared == 2
        assert metadata_manager.get("key1") is None
    
    def test_access_count_increment(self, metadata_manager):
        metadata_manager.insert("accessed", "/path", 300)
        
        metadata_manager.get("accessed")
        metadata_manager.get("accessed")
        metadata_manager.get("accessed")
        
        result = metadata_manager.get("accessed")
        
        assert result["access_count"] >= 3
    
    def test_metadata_json(self, metadata_manager):
        extra_data = {"source": "api", "version": "1.0"}
        
        metadata_manager.insert(
            "with_meta",
            "/path",
            300,
            metadata=extra_data,
        )
        
        result = metadata_manager.get("with_meta")
        
        assert result["metadata"] == extra_data
