"""
Performance Benchmark Tests for First Contentful Paint (FCP)
Uses Playwright to measure page load performance across all major routes.

Target: firstContentfulPaint < 500ms for all routes
Tolerance: 5% for CI variance (max 525ms)

Routes tested:
- / - Dashboard
- /fof/fundFilter - FundFilter
- /fund/compare - FundCompare
- /analytics/fear-greed - FearGreed
- /market/erp - ERPSpread
- /market/index-valuation - IndexValuation
- /fund/stock-reverse - StockReverseHolding
- /analytics/style-strength - StyleStrength
- /market/crowding - MarketCrowding
- /fof/fofBacktest - FOFBacktest
- /product/wmpFilter - WMPFilter
"""
import time
import pytest
from playwright.sync_api import sync_playwright, Page, Browser


# Configuration
BASE_URL = "http://localhost:60201"
FCP_TARGET_MS = 500  # Target: 500ms
FCP_TOLERANCE_PCT = 0.05  # 5% tolerance
FCP_MAX_MS = FCP_TARGET_MS * (1 + FCP_TOLERANCE_PCT)  # 525ms with tolerance

# Routes to test with their primary selectors (fallback to body)
ROUTES = [
    {
        "path": "/",
        "name": "Dashboard",
        "selector": "body",  # Dashboard has multiple dynamic components
        "description": "Dashboard with fear-greed gauge and ERP charts"
    },
    {
        "path": "/fof/fundFilter",
        "name": "FundFilter",
        "selector": "body",
        "description": "Fund filtering with 26,801 funds"
    },
    {
        "path": "/fund/compare",
        "name": "FundCompare",
        "selector": "body",
        "description": "Fund comparison with correlation matrix"
    },
    {
        "path": "/analytics/fear-greed",
        "name": "FearGreed",
        "selector": "body",
        "description": "Fear & Greed gauge visualization"
    },
    {
        "path": "/market/erp",
        "name": "ERPSpread",
        "selector": "body",
        "description": "Equity Risk Premium spread chart"
    },
    {
        "path": "/market/index-valuation",
        "name": "IndexValuation",
        "selector": "body",
        "description": "Index PE/PB valuation dashboard"
    },
    {
        "path": "/fund/stock-reverse",
        "name": "StockReverseHolding",
        "selector": "body",
        "description": "Stock-to-fund reverse lookup"
    },
    {
        "path": "/analytics/style-strength",
        "name": "StyleStrength",
        "selector": "body",
        "description": "Market style strength analysis"
    },
    {
        "path": "/market/crowding",
        "name": "MarketCrowding",
        "selector": "body",
        "description": "Market crowding phase space trajectory"
    },
    {
        "path": "/fof/fofBacktest",
        "name": "FOFBacktest",
        "selector": "body",
        "description": "FOF portfolio backtest with Brinson attribution"
    },
    {
        "path": "/product/wmpFilter",
        "name": "WMPFilter",
        "selector": "body",
        "description": "Wealth management product filter"
    },
]


def measure_fcp(page: Page, route: dict) -> dict:
    """
    Measure firstContentfulPaint for a route.
    
    Returns dict with:
    - fcp_ms: First Contentful Paint in milliseconds
    - load_time_ms: Total page load time
    - route_name: Name of the route
    - route_path: Path of the route
    """
    url = f"{BASE_URL}{route['path']}"
    
    # Start timing
    start_time = time.time()
    
    # Navigate to page
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    
    # Wait for primary content selector
    try:
        page.wait_for_selector(route['selector'], timeout=10000)
    except Exception:
        # Fallback: wait for body to be visible
        page.wait_for_selector("body", timeout=5000)
    
    # Record load time
    load_time_ms = (time.time() - start_time) * 1000
    
    # Get FCP from Performance API
    fcp_ms = page.evaluate("""
        () => {
            const entries = performance.getEntriesByType('paint');
            const fcp = entries.find(e => e.name === 'first-contentful-paint');
            return fcp ? fcp.startTime : null;
        }
    """)
    
    # If FCP not available, use load time as approximation
    if fcp_ms is None:
        fcp_ms = load_time_ms
    
    return {
        "fcp_ms": fcp_ms,
        "load_time_ms": load_time_ms,
        "route_name": route['name'],
        "route_path": route['path']
    }


@pytest.fixture(scope="module")
def browser():
    """Launch browser for all tests in module."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-extensions',
            ]
        )
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    """Create new page for each test."""
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    )
    page = context.new_page()
    yield page
    page.close()
    context.close()


class TestFirstContentfulPaint:
    """Test suite for firstContentfulPaint performance benchmarks."""
    
    @pytest.mark.parametrize("route", ROUTES, ids=[r['name'] for r in ROUTES])
    def test_fcp_under_500ms(self, page: Page, route: dict):
        """
        Test that firstContentfulPaint is under 500ms for each route.
        
        Acceptance Criteria:
        - FCP < 500ms (target)
        - FCP < 525ms (with 5% CI tolerance)
        - Test output shows actual load times
        """
        result = measure_fcp(page, route)
        
        # Log actual times
        print(f"\n{route['name']} ({route['path']}):")
        print(f"  FCP: {result['fcp_ms']:.1f}ms")
        print(f"  Load Time: {result['load_time_ms']:.1f}ms")
        
        # Assert FCP is under target with tolerance
        assert result['fcp_ms'] < FCP_MAX_MS, (
            f"{route['name']} FCP {result['fcp_ms']:.1f}ms exceeds "
            f"{FCP_MAX_MS:.1f}ms target (with {FCP_TOLERANCE_PCT*100:.0f}% tolerance)"
        )
    
    def test_all_routes_measured(self, browser: Browser):
        """
        Verify all major routes are tested and report summary.
        
        This test runs all routes in sequence and provides a summary report.
        """
        results = []
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        try:
            for route in ROUTES:
                result = measure_fcp(page, route)
                results.append(result)
                print(f"\n{route['name']}: FCP={result['fcp_ms']:.1f}ms, "
                      f"Load={result['load_time_ms']:.1f}ms")
        finally:
            page.close()
            context.close()
        
        # Summary report
        print("\n" + "=" * 60)
        print("PERFORMANCE BENCHMARK SUMMARY")
        print("=" * 60)
        print(f"Target: FCP < {FCP_TARGET_MS}ms")
        print(f"Tolerance: {FCP_TOLERANCE_PCT*100:.0f}% (max {FCP_MAX_MS:.1f}ms)")
        print("-" * 60)
        
        passed = 0
        failed = 0
        
        for r in results:
            status = "✓ PASS" if r['fcp_ms'] < FCP_MAX_MS else "✗ FAIL"
            if r['fcp_ms'] < FCP_MAX_MS:
                passed += 1
            else:
                failed += 1
            print(f"{status} {r['route_name']:20s} FCP: {r['fcp_ms']:6.1f}ms")
        
        print("-" * 60)
        print(f"Total: {len(results)} routes | Passed: {passed} | Failed: {failed}")
        print("=" * 60)
        
        # Assert all routes pass
        assert failed == 0, f"{failed} routes exceeded FCP target of {FCP_MAX_MS:.1f}ms"


class TestPerformanceMetrics:
    """Additional performance metrics tests."""
    
    def test_dashboard_load_time(self, page: Page):
        """Test Dashboard page load time with detailed metrics."""
        route = ROUTES[0]  # Dashboard
        result = measure_fcp(page, route)
        
        # Get additional performance metrics
        metrics = page.evaluate("""
            () => {
                const timing = performance.timing;
                const navigation = performance.getEntriesByType('navigation')[0];
                
                return {
                    domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
                    loadComplete: timing.loadEventEnd - timing.navigationStart,
                    domInteractive: timing.domInteractive - timing.navigationStart,
                    responseEnd: timing.responseEnd - timing.requestStart,
                    transferSize: navigation ? navigation.transferSize : 0,
                    encodedBodySize: navigation ? navigation.encodedBodySize : 0,
                };
            }
        """)
        
        print(f"\nDashboard Performance Metrics:")
        print(f"  FCP: {result['fcp_ms']:.1f}ms")
        print(f"  DOM Content Loaded: {metrics['domContentLoaded']:.1f}ms")
        print(f"  Load Complete: {metrics['loadComplete']:.1f}ms")
        print(f"  DOM Interactive: {metrics['domInteractive']:.1f}ms")
        print(f"  Response Time: {metrics['responseEnd']:.1f}ms")
        print(f"  Transfer Size: {metrics['transferSize']/1024:.1f}KB")
        print(f"  Encoded Body Size: {metrics['encodedBodySize']/1024:.1f}KB")
        
        assert result['fcp_ms'] < FCP_MAX_MS
    
    def test_fund_filter_performance(self, page: Page):
        """Test FundFilter page with large dataset performance."""
        route = next(r for r in ROUTES if r['name'] == 'FundFilter')
        result = measure_fcp(page, route)
        
        print(f"\nFundFilter Performance (26,801 funds):")
        print(f"  FCP: {result['fcp_ms']:.1f}ms")
        print(f"  Load Time: {result['load_time_ms']:.1f}ms")
        
        # FundFilter should be especially fast due to L1/L2 cache
        assert result['fcp_ms'] < FCP_MAX_MS
    
    def test_echarts_render_performance(self, page: Page):
        """Test ECharts rendering performance on chart-heavy pages."""
        chart_routes = [
            r for r in ROUTES 
            if r['name'] in ['FearGreed', 'ERPSpread', 'MarketCrowding', 'StyleStrength']
        ]
        
        results = []
        for route in chart_routes:
            result = measure_fcp(page, route)
            results.append(result)
            print(f"\n{route['name']} (ECharts): FCP={result['fcp_ms']:.1f}ms")
        
        # All chart pages should meet target
        for r in results:
            assert r['fcp_ms'] < FCP_MAX_MS, (
                f"{r['route_name']} FCP {r['fcp_ms']:.1f}ms exceeds target"
            )


if __name__ == "__main__":
    """Run performance tests directly."""
    pytest.main([__file__, "-v", "-s", "--tb=short"])
