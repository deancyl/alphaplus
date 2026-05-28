"""
Performance benchmark for TieredCache L1 optimization.

Tests L1 cache latency with 10,000 requests and verifies p95 < 2ms.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.tiered_cache import TieredCache, LatencyMetrics


def benchmark_l1_cache():
    """
    Benchmark L1 cache performance.
    
    Verifies:
    - p95 latency < 2ms for hot key hits
    - p99 latency < 5ms
    """
    print("=" * 60)
    print("TieredCache L1 Performance Benchmark")
    print("=" * 60)
    
    cache = TieredCache(l1_maxsize=1000, l1_ttl=300)
    
    test_data = {f"test_key_{i}": {"data": f"value_{i}", "index": i} for i in range(100)}
    
    print("\nPhase 1: Populating cache with 100 entries...")
    for key, value in test_data.items():
        cache.set(key, value)
    print(f"  Cached {len(test_data)} entries")
    
    print("\nPhase 2: Running 10,000 L1 cache hits...")
    latencies = []
    num_requests = 10000
    
    keys = list(test_data.keys())
    
    for i in range(num_requests):
        key = keys[i % len(keys)]
        
        start = time.perf_counter()
        result = cache.get(key)
        latency_ms = (time.perf_counter() - start) * 1000
        
        latencies.append(latency_ms)
        
        assert result is not None, f"Cache miss for key {key}"
        assert result["data"] == test_data[key]["data"]
    
    latencies.sort()
    
    def percentile(p: float) -> float:
        idx = int(len(latencies) * p / 100)
        idx = min(idx, len(latencies) - 1)
        return latencies[idx]
    
    p50 = percentile(50)
    p95 = percentile(95)
    p99 = percentile(99)
    avg = sum(latencies) / len(latencies)
    min_lat = latencies[0]
    max_lat = latencies[-1]
    
    print(f"\n{'Metric':<20} {'Value (ms)':<15} {'Target':<15}")
    print("-" * 60)
    print(f"{'Average':<20} {avg:<15.4f} {'-':<15}")
    print(f"{'Min':<20} {min_lat:<15.4f} {'-':<15}")
    print(f"{'Max':<20} {max_lat:<15.4f} {'-':<15}")
    print(f"{'P50 (median)':<20} {p50:<15.4f} {'-':<15}")
    print(f"{'P95':<20} {p95:<15.4f} {'< 2.0 ms':<15}")
    print(f"{'P99':<20} {p99:<15.4f} {'< 5.0 ms':<15}")
    
    stats = cache.stats()
    print(f"\nCache Statistics:")
    print(f"  L1 Size: {stats['l1']['size']}/{stats['l1']['maxsize']}")
    print(f"  L1 Hit Rate: {stats['l1']['hit_rate_pct']}%")
    print(f"  L1 Hits: {stats['l1']['hits']}")
    print(f"  L1 Misses: {stats['l1']['misses']}")
    
    print(f"\nLatency Metrics from cache:")
    latency_stats = stats['latency']
    print(f"  Avg: {latency_stats['avg_ms']:.4f} ms")
    print(f"  P50: {latency_stats['p50_ms']:.4f} ms")
    print(f"  P95: {latency_stats['p95_ms']:.4f} ms")
    print(f"  P99: {latency_stats['p99_ms']:.4f} ms")
    
    print("\n" + "=" * 60)
    if p95 < 2.0:
        print("✅ PASS: P95 latency < 2ms target achieved!")
        print(f"   P95 = {p95:.4f} ms (target: < 2.0 ms)")
    else:
        print("❌ FAIL: P95 latency exceeds 2ms target!")
        print(f"   P95 = {p95:.4f} ms (target: < 2.0 ms)")
    
    if p99 < 5.0:
        print("✅ PASS: P99 latency < 5ms target achieved!")
        print(f"   P99 = {p99:.4f} ms (target: < 5.0 ms)")
    else:
        print("❌ FAIL: P99 latency exceeds 5ms target!")
        print(f"   P99 = {p99:.4f} ms (target: < 5.0 ms)")
    print("=" * 60)
    
    return p95 < 2.0


def benchmark_latency_metrics():
    """Benchmark the LatencyMetrics class."""
    print("\n" + "=" * 60)
    print("LatencyMetrics Unit Test")
    print("=" * 60)
    
    metrics = LatencyMetrics(max_samples=1000)
    
    for i in range(100):
        metrics.record(0.001 * (i + 1))
    
    stats = metrics.get_stats()
    
    assert stats["sample_count"] == 100, f"Expected 100 samples, got {stats['sample_count']}"
    assert stats["min_ms"] == 0.001, f"Expected min 0.001, got {stats['min_ms']}"
    assert stats["max_ms"] == 0.1, f"Expected max 0.1, got {stats['max_ms']}"
    
    print(f"  Sample count: {stats['sample_count']}")
    print(f"  Avg: {stats['avg_ms']:.4f} ms")
    print(f"  Min: {stats['min_ms']:.4f} ms")
    print(f"  Max: {stats['max_ms']:.4f} ms")
    print(f"  P50: {stats['p50_ms']:.4f} ms")
    print(f"  P95: {stats['p95_ms']:.4f} ms")
    print(f"  P99: {stats['p99_ms']:.4f} ms")
    
    print("✅ LatencyMetrics unit test passed!")
    print("=" * 60)
    
    return True


def benchmark_cache_warming():
    """Benchmark cache warming functionality."""
    print("\n" + "=" * 60)
    print("Cache Warming Benchmark")
    print("=" * 60)
    
    cache = TieredCache(l1_maxsize=1000, l1_ttl=300)
    
    for i in range(50):
        key = f"hot_key_{i}"
        value = {"data": f"value_{i}", "index": i}
        cache.set(key, value)
    
    cache.clear()
    
    hot_keys = [f"hot_key_{i}" for i in range(50)]
    
    import asyncio
    
    async def run_warmup():
        start = time.perf_counter()
        warmed_count = await cache.warm_cache(hot_keys=hot_keys)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return warmed_count, elapsed_ms
    
    warmed_count, elapsed_ms = asyncio.run(run_warmup())
    
    print(f"  Keys to warm: {len(hot_keys)}")
    print(f"  Keys warmed: {warmed_count}")
    print(f"  Time: {elapsed_ms:.2f} ms")
    print(f"  Per-key: {elapsed_ms / len(hot_keys):.4f} ms")
    
    print("✅ Cache warming benchmark complete!")
    print("=" * 60)
    
    return True


def main():
    """Run all benchmarks."""
    print("\n" + "=" * 80)
    print("L1 Cache Optimization Benchmark Suite")
    print("=" * 80)
    
    results = []
    
    try:
        results.append(("LatencyMetrics Unit Test", benchmark_latency_metrics()))
    except Exception as e:
        print(f"❌ LatencyMetrics test failed: {e}")
        results.append(("LatencyMetrics Unit Test", False))
    
    try:
        results.append(("L1 Cache Performance", benchmark_l1_cache()))
    except Exception as e:
        print(f"❌ L1 Cache performance test failed: {e}")
        results.append(("L1 Cache Performance", False))
    
    try:
        results.append(("Cache Warming", benchmark_cache_warming()))
    except Exception as e:
        print(f"❌ Cache warming test failed: {e}")
        results.append(("Cache Warming", False))
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
        all_passed = all_passed and passed
    
    print("=" * 80)
    
    if all_passed:
        print("✅ ALL BENCHMARKS PASSED!")
        return 0
    else:
        print("❌ SOME BENCHMARKS FAILED!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
