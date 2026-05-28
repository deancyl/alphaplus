"""
Memory Leak Audit Tests for ECharts Components
Uses Playwright CDP (Chrome DevTools Protocol) to detect memory leaks.

Verification Standards:
- JSHeap delta < 50KB after GC
- DOM nodes delta ≤ 0
- Documents delta ≤ 0
- JSEventListeners delta ≤ 0
"""
import asyncio
import pytest
from dataclasses import dataclass
from typing import Dict, Optional
from playwright.async_api import async_playwright, Page, BrowserContext, CDPSession


@dataclass
class MemorySnapshot:
    """Memory snapshot data structure."""
    js_heap_used_size: int  # bytes
    nodes: int
    documents: int
    js_event_listeners: int
    label: str


class MemoryProfiler:
    """CDP Memory Profiler for detecting memory leaks in ECharts components."""
    
    def __init__(self, page: Page):
        self.page = page
        self.cdp_session: Optional[CDPSession] = None
    
    async def initialize(self) -> None:
        """Initialize CDP session and enable Performance domain."""
        self.cdp_session = await self.page.context.new_cdp_session(self.page)
        await self.cdp_session.send("Performance.enable")
    
    async def force_gc(self) -> None:
        """Force garbage collection via CDP."""
        if self.cdp_session is None:
            raise RuntimeError("CDP session not initialized. Call initialize() first.")
        
        # Force GC multiple times to ensure thorough collection
        for _ in range(3):
            await self.cdp_session.send("HeapProfiler.collectGarbage")
            await asyncio.sleep(0.1)  # Small delay between GC cycles
    
    async def measure(self, label: str) -> MemorySnapshot:
        """
        Get memory snapshot via CDP Performance.getMetrics.
        
        Metrics captured:
        - JSHeapUsedSize: JavaScript heap memory used
        - Nodes: DOM nodes count
        - Documents: Document count
        - JSEventListeners: Event listeners count
        """
        if self.cdp_session is None:
            raise RuntimeError("CDP session not initialized. Call initialize() first.")
        
        # Force GC before measurement
        await self.force_gc()
        
        # Small delay to let metrics stabilize
        await asyncio.sleep(0.2)
        
        # Get performance metrics
        result = await self.cdp_session.send("Performance.getMetrics")
        metrics = {m["name"]: m["value"] for m in result.get("metrics", [])}
        
        return MemorySnapshot(
            js_heap_used_size=int(metrics.get("JSHeapUsedSize", 0)),
            nodes=int(metrics.get("Nodes", 0)),
            documents=int(metrics.get("Documents", 0)),
            js_event_listeners=int(metrics.get("JSEventListeners", 0)),
            label=label
        )
    
    def analyze(self, baseline: MemorySnapshot, final: MemorySnapshot) -> Dict:
        """
        Analyze memory growth between two snapshots.
        
        Returns dict with:
        - js_heap_delta: bytes difference
        - nodes_delta: DOM nodes difference
        - documents_delta: Documents difference
        - event_listeners_delta: Event listeners difference
        - is_leaking: bool indicating if memory leak detected
        - report: human-readable report
        """
        js_heap_delta = final.js_heap_used_size - baseline.js_heap_used_size
        nodes_delta = final.nodes - baseline.nodes
        documents_delta = final.documents - baseline.documents
        event_listeners_delta = final.js_event_listeners - baseline.js_event_listeners
        
        # Thresholds (50KB = 51200 bytes)
        JS_HEAP_THRESHOLD = 51200  # 50KB
        NODES_THRESHOLD = 0
        DOCUMENTS_THRESHOLD = 0
        EVENT_LISTENERS_THRESHOLD = 0
        
        is_leaking = (
            js_heap_delta > JS_HEAP_THRESHOLD or
            nodes_delta > NODES_THRESHOLD or
            documents_delta > DOCUMENTS_THRESHOLD or
            event_listeners_delta > EVENT_LISTENERS_THRESHOLD
        )
        
        report_lines = [
            f"\n{'='*60}",
            f"Memory Leak Analysis Report",
            f"{'='*60}",
            f"Baseline: {baseline.label}",
            f"Final: {final.label}",
            f"{'-'*60}",
            f"JS Heap Used: {baseline.js_heap_used_size:,} → {final.js_heap_used_size:,} bytes",
            f"  Delta: {js_heap_delta:,} bytes ({js_heap_delta/1024:.2f} KB)",
            f"  Threshold: {JS_HEAP_THRESHOLD:,} bytes ({JS_HEAP_THRESHOLD/1024:.2f} KB)",
            f"  Status: {'❌ LEAK' if js_heap_delta > JS_HEAP_THRESHOLD else '✅ OK'}",
            f"{'-'*60}",
            f"DOM Nodes: {baseline.nodes:,} → {final.nodes:,}",
            f"  Delta: {nodes_delta:,}",
            f"  Threshold: {NODES_THRESHOLD:,}",
            f"  Status: {'❌ LEAK' if nodes_delta > NODES_THRESHOLD else '✅ OK'}",
            f"{'-'*60}",
            f"Documents: {baseline.documents:,} → {final.documents:,}",
            f"  Delta: {documents_delta:,}",
            f"  Threshold: {DOCUMENTS_THRESHOLD:,}",
            f"  Status: {'❌ LEAK' if documents_delta > DOCUMENTS_THRESHOLD else '✅ OK'}",
            f"{'-'*60}",
            f"JS Event Listeners: {baseline.js_event_listeners:,} → {final.js_event_listeners:,}",
            f"  Delta: {event_listeners_delta:,}",
            f"  Threshold: {EVENT_LISTENERS_THRESHOLD:,}",
            f"  Status: {'❌ LEAK' if event_listeners_delta > EVENT_LISTENERS_THRESHOLD else '✅ OK'}",
            f"{'='*60}",
            f"Overall Result: {'❌ MEMORY LEAK DETECTED' if is_leaking else '✅ NO MEMORY LEAK'}",
            f"{'='*60}",
        ]
        
        return {
            "js_heap_delta": js_heap_delta,
            "nodes_delta": nodes_delta,
            "documents_delta": documents_delta,
            "event_listeners_delta": event_listeners_delta,
            "is_leaking": is_leaking,
            "report": "\n".join(report_lines)
        }
    
    async def close(self) -> None:
        """Close CDP session."""
        if self.cdp_session:
            await self.cdp_session.detach()
            self.cdp_session = None


# Test routes with ECharts components
ECHARTS_ROUTES = [
    "/",                        # Dashboard (ECharts)
    "/fof/fundFilter",          # FundFilter
    "/fund/compare",            # FundCompare (heatmap)
    "/analytics/fear-greed",    # FearGreed (gauge)
    "/market/erp",              # ERPSpread (line chart)
    "/market/index-valuation",  # IndexValuation
    "/fund/stock-reverse",      # StockReverseHolding (pie chart)
    "/analytics/style-strength", # StyleStrength (radar)
    "/market/crowding",         # MarketCrowding (multiple charts)
    "/fof/fofBacktest",         # FOFBacktest (waterfall)
]


@pytest.fixture
async def browser_context():
    """Create browser context with CDP enabled."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--enable-precise-memory-info",
                "--enable-memory-info",
                "--js-flags=--expose-gc",
            ]
        )
        context = await browser.new_context()
        yield context
        await context.close()
        await browser.close()


@pytest.fixture
async def memory_page(browser_context: BrowserContext):
    """Create page with memory profiler."""
    page = await browser_context.new_page()
    profiler = MemoryProfiler(page)
    await profiler.initialize()
    yield page, profiler
    await profiler.close()
    await page.close()


@pytest.mark.asyncio
@pytest.mark.playwright
@pytest.mark.timeout(120000)  # 2 minutes for 50 transitions
async def test_echarts_memory_leak_route_transitions(memory_page):
    """
    Test memory leak during 50 route transitions between ECharts pages.
    
    Assertions:
    - JSHeap delta < 50KB after GC
    - DOM nodes delta ≤ 0
    - Documents delta ≤ 0
    """
    page, profiler = memory_page
    
    base_url = "http://localhost:60201"
    await page.goto(f"{base_url}{ECHARTS_ROUTES[0]}", wait_until="domcontentloaded")
    
    await page.wait_for_selector("#app > *", timeout=15000)
    
    try:
        await page.wait_for_selector("canvas, .echarts-container, [data-echarts]", timeout=5000)
    except Exception:
        pass
    
    await asyncio.sleep(2)
    
    # Take baseline measurement
    baseline = await profiler.measure("baseline_after_initial_load")
    
    # Perform 50 route transitions
    num_transitions = 50
    for i in range(num_transitions):
        route = ECHARTS_ROUTES[i % len(ECHARTS_ROUTES)]
        await page.goto(f"{base_url}{route}", wait_until="domcontentloaded")
        
        try:
            await page.wait_for_selector("#app > *", timeout=5000)
        except Exception:
            pass
        
        try:
            await page.wait_for_selector("canvas, .echarts-container", timeout=3000)
        except Exception:
            pass
        
        await asyncio.sleep(0.3)
    
    # Take final measurement
    final = await profiler.measure(f"final_after_{num_transitions}_transitions")
    
    # Analyze and report
    analysis = profiler.analyze(baseline, final)
    print(analysis["report"])
    
    # Assertions
    assert analysis["js_heap_delta"] < 51200, \
        f"JSHeap leak detected: {analysis['js_heap_delta']} bytes > 50KB threshold"
    assert analysis["nodes_delta"] <= 0, \
        f"DOM nodes leak detected: {analysis['nodes_delta']} nodes leaked"
    assert analysis["documents_delta"] <= 0, \
        f"Documents leak detected: {analysis['documents_delta']} documents leaked"
    assert not analysis["is_leaking"], "Memory leak detected in route transitions"


@pytest.mark.asyncio
@pytest.mark.playwright
async def test_chart_resize_memory_leak(memory_page):
    """
    Test memory leak during window resize operations.
    
    Simulates 50 resize operations and checks for memory leaks.
    """
    page, profiler = memory_page
    
    # Navigate to a chart-heavy page
    base_url = "http://localhost:60201"
    await page.goto(f"{base_url}/fund/compare")
    await page.wait_for_selector("canvas", timeout=10000)
    await asyncio.sleep(1)
    
    # Baseline measurement
    baseline = await profiler.measure("baseline_before_resize")
    
    # Perform 50 resize operations
    viewport_sizes = [
        (1920, 1080), (1366, 768), (1280, 720),
        (1024, 768), (768, 1024), (375, 812),
    ]
    
    for i in range(50):
        size = viewport_sizes[i % len(viewport_sizes)]
        await page.set_viewport_size({"width": size[0], "height": size[1]})
        await asyncio.sleep(0.1)
    
    # Final measurement
    final = await profiler.measure("final_after_50_resizes")
    
    # Analyze
    analysis = profiler.analyze(baseline, final)
    print(analysis["report"])
    
    # Assertions
    assert analysis["js_heap_delta"] < 51200, \
        f"JSHeap leak on resize: {analysis['js_heap_delta']} bytes"
    assert analysis["nodes_delta"] <= 0, \
        f"DOM nodes leak on resize: {analysis['nodes_delta']} nodes"
    assert not analysis["is_leaking"], "Memory leak detected during resize"


@pytest.mark.asyncio
@pytest.mark.playwright
async def test_chart_add_remove_series(memory_page):
    """
    Test memory leak when adding/removing chart series.
    
    Uses fund compare page to add/remove funds from comparison.
    """
    page, profiler = memory_page
    
    base_url = "http://localhost:60201"
    await page.goto(f"{base_url}/fund/compare")
    await page.wait_for_selector("canvas", timeout=10000)
    await asyncio.sleep(1)
    
    # Baseline
    baseline = await profiler.measure("baseline_before_series_ops")
    
    # Add and remove funds multiple times
    # This tests ECharts series add/remove memory handling
    fund_codes = ["000001", "000002", "000003", "000004", "000005"]
    
    for cycle in range(10):
        # Add funds
        for code in fund_codes:
            try:
                # Look for fund input/search
                search_input = await page.query_selector("input[placeholder*='基金'], input[placeholder*='fund']")
                if search_input:
                    await search_input.fill(code)
                    await asyncio.sleep(0.1)
                    # Try to click add button
                    add_btn = await page.query_selector("button:has-text('添加'), button:has-text('Add')")
                    if add_btn:
                        await add_btn.click()
                        await asyncio.sleep(0.2)
            except Exception:
                pass  # Continue if element not found
        
        # Remove funds
        remove_btns = await page.query_selector_all("button:has-text('删除'), button:has-text('移除'), .remove-btn")
        for btn in remove_btns[:5]:
            try:
                await btn.click()
                await asyncio.sleep(0.1)
            except Exception:
                pass
    
    # Final measurement
    final = await profiler.measure("final_after_series_operations")
    
    # Analyze
    analysis = profiler.analyze(baseline, final)
    print(analysis["report"])
    
    # Assertions
    assert analysis["js_heap_delta"] < 51200, \
        f"JSHeap leak in series ops: {analysis['js_heap_delta']} bytes"
    assert not analysis["is_leaking"], "Memory leak detected in series add/remove"


@pytest.mark.asyncio
@pytest.mark.playwright
async def test_dom_node_cleanup(memory_page):
    """
    Test DOM node cleanup when navigating away from chart pages.
    
    Verifies that ECharts properly disposes DOM elements.
    """
    page, profiler = memory_page
    
    base_url = "http://localhost:60201"
    
    # Start on a non-chart page
    await page.goto(f"{base_url}/")
    await asyncio.sleep(0.5)
    
    baseline = await profiler.measure("baseline_home_page")
    
    # Navigate to chart pages and back
    for _ in range(20):
        for route in ECHARTS_ROUTES:
            await page.goto(f"{base_url}{route}")
            await page.wait_for_selector("canvas", timeout=10000)
            await asyncio.sleep(0.3)
            
            # Navigate back to home
            await page.goto(f"{base_url}/")
            await asyncio.sleep(0.2)
    
    final = await profiler.measure("final_after_navigation_cycles")
    
    # Analyze
    analysis = profiler.analyze(baseline, final)
    print(analysis["report"])
    
    # DOM nodes should not grow
    assert analysis["nodes_delta"] <= 0, \
        f"DOM nodes not cleaned: {analysis['nodes_delta']} nodes remaining"
    assert analysis["documents_delta"] <= 0, \
        f"Documents not cleaned: {analysis['documents_delta']} documents remaining"
    assert not analysis["is_leaking"], "DOM cleanup memory leak detected"


@pytest.mark.asyncio
@pytest.mark.playwright
async def test_event_listener_cleanup(memory_page):
    """
    Test event listener cleanup when disposing ECharts instances.
    
    Verifies that event listeners are properly removed.
    """
    page, profiler = memory_page
    
    base_url = "http://localhost:60201"
    
    # Start fresh
    await page.goto(f"{base_url}/")
    await asyncio.sleep(0.5)
    
    baseline = await profiler.measure("baseline_event_listeners")
    
    # Navigate through chart pages multiple times
    # Each visit should properly dispose and re-create event listeners
    for _ in range(30):
        route = ECHARTS_ROUTES[_ % len(ECHARTS_ROUTES)]
        await page.goto(f"{base_url}{route}")
        await page.wait_for_selector("canvas", timeout=10000)
        
        # Interact with chart to trigger event listeners
        canvas = await page.query_selector("canvas")
        if canvas:
            # Simulate mouse interactions
            await canvas.hover()
            try:
                await page.mouse.move(100, 100)
                await page.mouse.click(100, 100)
            except Exception:
                pass
        
        await asyncio.sleep(0.2)
    
    # Navigate to non-chart page
    await page.goto(f"{base_url}/")
    await asyncio.sleep(0.5)
    
    final = await profiler.measure("final_event_listeners")
    
    # Analyze
    analysis = profiler.analyze(baseline, final)
    print(analysis["report"])
    
    # Event listeners should not accumulate
    assert analysis["event_listeners_delta"] <= 0, \
        f"Event listeners not cleaned: {analysis['event_listeners_delta']} listeners leaked"
    assert not analysis["is_leaking"], "Event listener memory leak detected"


# Additional helper test for comprehensive memory profiling
@pytest.mark.asyncio
@pytest.mark.playwright
async def test_memory_profile_report(memory_page):
    """
    Generate comprehensive memory profile report for all ECharts routes.
    
    This test provides detailed memory metrics for each route.
    """
    page, profiler = memory_page
    
    base_url = "http://localhost:60201"
    reports = []
    
    print("\n" + "="*70)
    print("COMPREHENSIVE MEMORY PROFILE REPORT")
    print("="*70)
    
    for route in ECHARTS_ROUTES:
        # Fresh start for each route
        await page.goto(f"{base_url}/")
        await asyncio.sleep(0.3)
        
        before = await profiler.measure(f"before_{route}")
        
        # Navigate to route
        await page.goto(f"{base_url}{route}")
        await page.wait_for_selector("canvas", timeout=10000)
        await asyncio.sleep(1)
        
        after = await profiler.measure(f"after_{route}")
        
        # Analyze
        analysis = profiler.analyze(before, after)
        
        route_name = route.replace("/", "_").strip("_") or "home"
        print(f"\nRoute: {route}")
        print(f"  JS Heap: {analysis['js_heap_delta']/1024:.2f} KB")
        print(f"  DOM Nodes: {analysis['nodes_delta']:+,}")
        print(f"  Documents: {analysis['documents_delta']:+,}")
        print(f"  Event Listeners: {analysis['event_listeners_delta']:+,}")
        
        reports.append({
            "route": route,
            "js_heap_kb": analysis["js_heap_delta"] / 1024,
            "nodes_delta": analysis["nodes_delta"],
            "documents_delta": analysis["documents_delta"],
            "event_listeners_delta": analysis["event_listeners_delta"],
        })
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    total_heap = sum(r["js_heap_kb"] for r in reports)
    avg_heap = total_heap / len(reports) if reports else 0
    
    print(f"Total JS Heap across routes: {total_heap:.2f} KB")
    print(f"Average JS Heap per route: {avg_heap:.2f} KB")
    
    # All routes should have reasonable memory footprint
    for report in reports:
        assert report["js_heap_kb"] < 5000, \
            f"Route {report['route']} uses too much memory: {report['js_heap_kb']:.2f} KB"
