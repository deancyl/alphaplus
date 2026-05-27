"""
Concurrent load test for async blocking verification.
Tests that 10 concurrent requests complete in <3s total.
"""
import pytest
import asyncio
import httpx
import time

BASE_URL = "http://localhost:60200"


@pytest.mark.asyncio
async def test_concurrent_analytics_requests():
    """
    Test that analytics endpoints handle concurrent requests without blocking.
    
    QA Gate: 10 concurrent requests complete in <3s total
    """
    endpoints = [
        "/api/v1/analytics/fear-greed",
        "/api/v1/analytics/erp",
        "/api/v1/analytics/style-strength",
        "/api/v1/analytics/crowding",
        "/api/v1/market/domestic",
        "/api/v1/gold/spot-price",
        "/api/v1/deposit/rates",
        "/api/v1/analytics/fear-greed",
        "/api/v1/analytics/erp",
        "/api/v1/gold/spot-price",
    ]
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        start_time = time.time()
        
        tasks = [client.get(endpoint) for endpoint in endpoints]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        
        successful = sum(1 for r in responses if not isinstance(r, Exception) and hasattr(r, 'status_code') and r.status_code == 200)
        failed = sum(1 for r in responses if isinstance(r, Exception))
        
        print(f"\nConcurrent test results:")
        print(f"  Total requests: {len(endpoints)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Total time: {elapsed:.2f}s")
        print(f"  Avg time per request: {elapsed/len(endpoints):.2f}s")
        
        assert elapsed < 3.0, f"10 concurrent requests took {elapsed:.2f}s (>3s threshold)"
        assert successful >= 8, f"Only {successful}/10 requests succeeded"


@pytest.mark.asyncio
async def test_no_event_loop_blocking():
    """
    Verify that async endpoints don't block the event loop.
    
    This test sends requests while monitoring event loop latency.
    """
    async def monitor_loop_latency():
        latencies = []
        for _ in range(20):
            start = time.time()
            await asyncio.sleep(0.01)
            latencies.append(time.time() - start)
        return latencies
    
    async def make_requests():
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
            tasks = [client.get("/api/v1/analytics/erp") for _ in range(5)]
            return await asyncio.gather(*tasks, return_exceptions=True)
    
    start_time = time.time()
    
    monitor_task = asyncio.create_task(monitor_loop_latency())
    request_task = asyncio.create_task(make_requests())
    
    latencies, responses = await asyncio.gather(monitor_task, request_task)
    
    elapsed = time.time() - start_time
    
    max_latency = max(latencies)
    avg_latency = sum(latencies) / len(latencies)
    
    print(f"\nEvent loop monitoring:")
    print(f"  Max latency: {max_latency:.4f}s")
    print(f"  Avg latency: {avg_latency:.4f}s")
    print(f"  Total time: {elapsed:.2f}s")
    
    assert max_latency < 0.5, f"Event loop blocked for {max_latency:.2f}s"
    assert elapsed < 5.0, f"Total test took {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_thread_pool_timeout():
    """
    Test that thread pool operations timeout correctly.
    """
    from backend.services.async_akshare import AsyncAkShareWrapper, AsyncAkShareTimeoutError
    
    wrapper = AsyncAkShareWrapper(timeout=1.0)
    
    with pytest.raises(AsyncAkShareTimeoutError):
        await wrapper.get_bond_china_yield()
    
    wrapper.close()


@pytest.mark.asyncio
async def test_thread_pool_workers_config():
    """
    Test that thread pool configuration is loaded correctly.
    """
    from backend.core.config import settings
    
    assert settings.thread_pool_workers == 4
    assert settings.async_timeout == 30.0
    
    print(f"\nThread pool config:")
    print(f"  Workers: {settings.thread_pool_workers}")
    print(f"  Timeout: {settings.async_timeout}s")