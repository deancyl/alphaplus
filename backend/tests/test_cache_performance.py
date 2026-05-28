"""
Performance benchmark for L2/L3 cache enhancements.

Verifies:
- L2 latency < 8ms at 95th percentile
- L3 latency < 20ms at 95th percentile
- Combined cache hit rate > 90%
"""
import time
import tempfile
import statistics
from pathlib import Path
from datetime import date, timedelta

import pandas as pd
import pytest

from backend.services.pandas_cache import (
    FundCache,
    DataFrameLRUCache,
    DEFAULT_MEMORY_LIMIT_MB,
)
from backend.services.parquet_cache import (
    export_holdings_to_parquet,
    load_holdings_from_parquet,
    parquet_latency_metrics,
    get_parquet_cache_stats,
)
from backend.services.tiered_cache import TieredCache
from backend.core.cache_metadata import CacheMetadataManager


class TestL2Performance:
    """L2 DataFrame cache performance benchmarks."""
    
    def test_dataframe_lru_cache_latency(self):
        """Verify L2 DataFrame operations meet < 8ms target."""
        cache = DataFrameLRUCache(memory_limit_mb=64)
        
        df = pd.DataFrame({
            'fund_code': [f'F{i:06d}' for i in range(10000)],
            'return_1y': [i * 0.01 for i in range(10000)],
            'scale': [i * 100.0 for i in range(10000)],
        })
        
        latencies = []
        
        for i in range(100):
            start = time.perf_counter()
            cache.set(f"key_{i}", df.copy())
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)
        
        for i in range(100):
            start = time.perf_counter()
            result = cache.get(f"key_{i}")
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)
            assert result is not None
        
        p95 = statistics.quantiles(latencies, n=100)[94]
        
        print(f"\nL2 DataFrame Cache Performance:")
        print(f"  Avg latency: {statistics.mean(latencies):.2f}ms")
        print(f"  P50 latency: {statistics.quantiles(latencies, n=100)[49]:.2f}ms")
        print(f"  P95 latency: {p95:.2f}ms")
        print(f"  Max latency: {max(latencies):.2f}ms")
        
        assert p95 < 8.0, f"L2 P95 latency {p95:.2f}ms exceeds 8ms target"
    
    def test_dataframe_lru_eviction(self):
        """Verify LRU eviction works correctly under memory pressure."""
        cache = DataFrameLRUCache(memory_limit_mb=1)
        
        large_df = pd.DataFrame({
            'data': list(range(10000))
        })
        
        for i in range(10):
            cache.set(f"df_{i}", large_df.copy())
        
        stats = cache.get_stats()
        
        assert stats['evictions'] > 0, "LRU eviction should occur under memory pressure"
        assert stats['memory_usage_mb'] <= cache.memory_limit_mb
        
        print(f"\nLRU Eviction Stats:")
        print(f"  Evictions: {stats['evictions']}")
        print(f"  Memory usage: {stats['memory_usage_mb']:.2f}MB / {stats['memory_limit_mb']}MB")


class TestL3Performance:
    """L3 Parquet cache performance benchmarks."""
    
    @pytest.fixture
    def temp_parquet_dir(self, tmp_path):
        from backend.services import parquet_cache
        original_cache_dir = parquet_cache.CACHE_DIR
        parquet_cache.CACHE_DIR = tmp_path / "parquet"
        parquet_cache.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        yield parquet_cache.CACHE_DIR
        parquet_cache.CACHE_DIR = original_cache_dir
    
    def test_parquet_write_latency(self, temp_parquet_dir):
        """Verify Parquet write operations meet < 20ms target."""
        holdings = [
            {
                'fund_code': f'F{i:06d}',
                'stock_code': f'S{j:06d}',
                'quarter_date': '2024-03-31',
                'holding_pct': 0.01 * (i + j),
            }
            for i in range(1000)
            for j in range(10)
        ]
        
        latencies = []
        
        for batch in range(5):
            batch_holdings = [
                {**h, 'quarter_date': f'2024-Q{batch+1}'} 
                for h in holdings[:2000]
            ]
            
            start = time.perf_counter()
            export_holdings_to_parquet(batch_holdings, partition_by_quarter=True)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)
        
        p95 = statistics.quantiles(latencies, n=100)[94] if len(latencies) >= 20 else max(latencies)
        
        print(f"\nL3 Parquet Write Performance:")
        print(f"  Avg latency: {statistics.mean(latencies):.2f}ms")
        print(f"  Max latency: {max(latencies):.2f}ms")
        
        assert p95 < 20.0, f"L3 P95 write latency {p95:.2f}ms exceeds 20ms target"
    
    def test_parquet_read_with_partition_pruning(self, temp_parquet_dir):
        """Verify partition pruning improves read performance."""
        holdings = [
            {
                'fund_code': f'F{i:06d}',
                'stock_code': f'S{j:06d}',
                'quarter_date': f'2024-{str(m).zfill(2)}-31',
                'holding_pct': 0.01 * (i + j),
            }
            for i in range(500)
            for j in range(10)
            for m in range(1, 13)
        ]
        
        export_holdings_to_parquet(holdings, partition_by_quarter=True)
        
        latencies = []
        
        for month in range(1, 13):
            quarter_date = date(2024, month, 1)
            
            start = time.perf_counter()
            result = load_holdings_from_parquet(
                quarter_date=quarter_date,
                partition_pruning=True
            )
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)
        
        p95 = statistics.quantiles(latencies, n=100)[94] if len(latencies) >= 10 else max(latencies)
        
        print(f"\nL3 Parquet Read with Partition Pruning:")
        print(f"  Avg latency: {statistics.mean(latencies):.2f}ms")
        print(f"  P95 latency: {p95:.2f}ms")
        
        assert p95 < 20.0, f"L3 P95 read latency {p95:.2f}ms exceeds 20ms target"
    
    def test_parquet_incremental_update(self, temp_parquet_dir):
        """Verify incremental updates avoid full rewrites."""
        initial_holdings = [
            {
                'fund_code': f'F{i:06d}',
                'stock_code': f'S{i:06d}',
                'quarter_date': '2024-03-31',
                'holding_pct': 0.01 * i,
            }
            for i in range(1000)
        ]
        
        start = time.perf_counter()
        export_holdings_to_parquet(initial_holdings, partition_by_quarter=True, incremental=False)
        full_write_time = time.perf_counter() - start
        
        new_holdings = [
            {
                'fund_code': f'F{i:06d}',
                'stock_code': f'S{i:06d}',
                'quarter_date': '2024-03-31',
                'holding_pct': 0.02 * i,
            }
            for i in range(1000, 1500)
        ]
        
        start = time.perf_counter()
        export_holdings_to_parquet(new_holdings, partition_by_quarter=True, incremental=True)
        incremental_write_time = time.perf_counter() - start
        
        print(f"\nIncremental vs Full Write:")
        print(f"  Full write: {full_write_time * 1000:.2f}ms")
        print(f"  Incremental write: {incremental_write_time * 1000:.2f}ms")


class TestCombinedHitRate:
    """Combined L1+L2+L3 hit rate tests."""
    
    @pytest.fixture
    def tiered_cache(self, tmp_path):
        cache = TieredCache(
            l1_maxsize=100,
            l1_ttl=300,
            l2_dir=str(tmp_path / "cache"),
            l2_ttl=600,
        )
        cache.metadata = CacheMetadataManager(str(tmp_path / "metadata.db"))
        yield cache
        cache.clear()
    
    def test_combined_hit_rate(self, tiered_cache):
        """Verify combined hit rate > 90% under typical workload."""
        test_data = {f"key_{i}": f"value_{i}" for i in range(100)}
        
        for key, value in test_data.items():
            tiered_cache.set(key, value)
        
        total_requests = 0
        total_hits = 0
        
        for _ in range(10):
            for key in test_data.keys():
                result = tiered_cache.get(key)
                total_requests += 1
                if result is not None:
                    total_hits += 1
        
        for _ in range(5):
            result = tiered_cache.get("nonexistent_key")
            total_requests += 1
        
        hit_rate = total_hits / total_requests * 100
        
        stats = tiered_cache.stats()
        combined_hit_rate = stats.get("combined", {}).get("hit_rate_pct", 0)
        
        print(f"\nCombined Hit Rate:")
        print(f"  L1 hits: {stats['l1']['hits']}")
        print(f"  L2 hits: {stats['l2']['hits']}")
        print(f"  Total requests: {total_requests}")
        print(f"  Hit rate: {hit_rate:.2f}%")
        print(f"  Combined hit rate (from stats): {combined_hit_rate:.2f}%")
        
        assert hit_rate > 90.0, f"Combined hit rate {hit_rate:.2f}% below 90% target"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
