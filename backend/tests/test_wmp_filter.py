"""
Unit tests for Wealth Management Product (WMP) filtering logic.
"""
import pytest
from datetime import datetime

from backend.schemas.wmp import WMPItem, WMPFilterParams
from backend.api.wmp import _filter_products, _sort_products, _paginate_products
from backend.services.sources.wmp_source import (
    ChinaWealthSource,
    EastmoneyWMPSource,
    MockWMPSource,
    WMPDataGateway,
)


# ==================== Test Data ====================

@pytest.fixture
def sample_products():
    """Sample WMP products for testing."""
    return [
        {
            "product_code": "LC2026000001",
            "product_name": "工商银行理财稳利1号",
            "yield_rate": 3.5,
            "risk_level": "PR2",
            "duration": 90,
            "issuer": "工商银行",
            "min_amount": 10000,
            "product_type": "固定收益类",
            "currency": "CNY",
            "is_active": True,
        },
        {
            "product_code": "LC2026000002",
            "product_name": "建设银行理财尊享2号",
            "yield_rate": 4.2,
            "risk_level": "PR3",
            "duration": 180,
            "issuer": "建设银行",
            "min_amount": 50000,
            "product_type": "混合类",
            "currency": "CNY",
            "is_active": True,
        },
        {
            "product_code": "LC2026000003",
            "product_name": "招商银行理财优选3号",
            "yield_rate": 2.8,
            "risk_level": "PR1",
            "duration": 30,
            "issuer": "招商银行",
            "min_amount": 10000,
            "product_type": "固定收益类",
            "currency": "CNY",
            "is_active": True,
        },
        {
            "product_code": "LC2026000004",
            "product_name": "农业银行理财添利4号",
            "yield_rate": 5.0,
            "risk_level": "PR4",
            "duration": 365,
            "issuer": "农业银行",
            "min_amount": 100000,
            "product_type": "权益类",
            "currency": "CNY",
            "is_active": False,
        },
        {
            "product_code": "LC2026000005",
            "product_name": "中国银行理财稳健5号",
            "yield_rate": 3.0,
            "risk_level": "PR2",
            "duration": 120,
            "issuer": "中国银行",
            "min_amount": 50000,
            "product_type": "固定收益类",
            "currency": "CNY",
            "is_active": True,
        },
    ]


# ==================== Filter Tests ====================

class TestWMPFiltering:
    """Tests for WMP filtering logic."""
    
    def test_filter_by_yield_min(self, sample_products):
        """Test filtering by minimum yield rate."""
        params = WMPFilterParams(yield_min=3.0)
        filtered = _filter_products(sample_products, params)
        
        assert len(filtered) == 4
        assert all(p["yield_rate"] >= 3.0 for p in filtered)
    
    def test_filter_by_yield_max(self, sample_products):
        """Test filtering by maximum yield rate."""
        params = WMPFilterParams(yield_max=4.0)
        filtered = _filter_products(sample_products, params)
        
        assert len(filtered) == 3
        assert all(p["yield_rate"] <= 4.0 for p in filtered)
    
    def test_filter_by_yield_range(self, sample_products):
        """Test filtering by yield rate range."""
        params = WMPFilterParams(yield_min=3.0, yield_max=4.0)
        filtered = _filter_products(sample_products, params)
        
        # Products with yield_rate in [3.0, 4.0]:
        # LC2026000001 (3.5), LC2026000005 (3.0) => 2 products (not including 4.2 and 5.0)
        assert len(filtered) == 2
        assert all(3.0 <= p["yield_rate"] <= 4.0 for p in filtered)
    
    def test_filter_by_risk_level(self, sample_products):
        """Test filtering by risk level."""
        params = WMPFilterParams(risk_levels=["PR1", "PR2"])
        filtered = _filter_products(sample_products, params)
        
        assert len(filtered) == 3
        assert all(p["risk_level"] in ["PR1", "PR2"] for p in filtered)
    
    def test_filter_by_duration_min(self, sample_products):
        """Test filtering by minimum duration."""
        params = WMPFilterParams(duration_min=100)
        filtered = _filter_products(sample_products, params)
        
        assert len(filtered) == 3
        assert all(p["duration"] >= 100 for p in filtered)
    
    def test_filter_by_duration_max(self, sample_products):
        """Test filtering by maximum duration."""
        params = WMPFilterParams(duration_max=100)
        filtered = _filter_products(sample_products, params)
        
        assert len(filtered) == 2
        assert all(p["duration"] <= 100 for p in filtered)
    
    def test_filter_by_duration_range(self, sample_products):
        """Test filtering by duration range."""
        params = WMPFilterParams(duration_min=60, duration_max=180)
        filtered = _filter_products(sample_products, params)
        
        assert len(filtered) == 3
        assert all(60 <= p["duration"] <= 180 for p in filtered)
    
    def test_filter_by_issuer_fuzzy(self, sample_products):
        """Test filtering by issuer (fuzzy match)."""
        params = WMPFilterParams(issuer="工商")
        filtered = _filter_products(sample_products, params)
        
        assert len(filtered) == 1
        assert "工商" in filtered[0]["issuer"]
    
    def test_filter_by_issuers_exact(self, sample_products):
        """Test filtering by issuers (exact match)."""
        params = WMPFilterParams(issuers=["工商银行", "建设银行"])
        filtered = _filter_products(sample_products, params)
        
        assert len(filtered) == 2
        assert all(p["issuer"] in ["工商银行", "建设银行"] for p in filtered)
    
    def test_filter_by_min_amount_max(self, sample_products):
        """Test filtering by maximum minimum amount."""
        params = WMPFilterParams(min_amount_max=50000)
        filtered = _filter_products(sample_products, params)
        
        assert len(filtered) == 4
        assert all(p["min_amount"] <= 50000 for p in filtered)
    
    def test_filter_by_product_type(self, sample_products):
        """Test filtering by product type."""
        params = WMPFilterParams(product_types=["固定收益类"])
        filtered = _filter_products(sample_products, params)
        
        assert len(filtered) == 3
        assert all(p["product_type"] == "固定收益类" for p in filtered)
    
    def test_filter_by_is_active(self, sample_products):
        """Test filtering by active status."""
        params = WMPFilterParams(is_active=True)
        filtered = _filter_products(sample_products, params)
        
        assert len(filtered) == 4
        assert all(p["is_active"] for p in filtered)
    
    def test_filter_combined(self, sample_products):
        """Test combined filtering."""
        params = WMPFilterParams(
            yield_min=3.0,
            risk_levels=["PR2", "PR3"],
            duration_min=60,
            is_active=True,
        )
        filtered = _filter_products(sample_products, params)
        
        # Products matching all criteria:
        # LC2026000001 (yield=3.5, risk=PR2, duration=90, active=True)
        # LC2026000002 (yield=4.2, risk=PR3, duration=180, active=True)
        # LC2026000005 (yield=3.0, risk=PR2, duration=120, active=True)
        assert len(filtered) == 3
        for p in filtered:
            assert p["yield_rate"] >= 3.0
            assert p["risk_level"] in ["PR2", "PR3"]
            assert p["duration"] >= 60
            assert p["is_active"]


# ==================== Sort Tests ====================

class TestWMPSorting:
    """Tests for WMP sorting logic."""
    
    def test_sort_by_yield_desc(self, sample_products):
        """Test sorting by yield rate descending."""
        sorted_products = _sort_products(sample_products, "yield_rate", "desc")
        
        yields = [p["yield_rate"] for p in sorted_products]
        assert yields == sorted(yields, reverse=True)
    
    def test_sort_by_yield_asc(self, sample_products):
        """Test sorting by yield rate ascending."""
        sorted_products = _sort_products(sample_products, "yield_rate", "asc")
        
        yields = [p["yield_rate"] for p in sorted_products]
        assert yields == sorted(yields)
    
    def test_sort_by_duration_desc(self, sample_products):
        """Test sorting by duration descending."""
        sorted_products = _sort_products(sample_products, "duration", "desc")
        
        durations = [p["duration"] for p in sorted_products]
        assert durations == sorted(durations, reverse=True)
    
    def test_sort_by_min_amount(self, sample_products):
        """Test sorting by minimum amount."""
        sorted_products = _sort_products(sample_products, "min_amount", "asc")
        
        amounts = [p["min_amount"] for p in sorted_products]
        assert amounts == sorted(amounts)


# ==================== Pagination Tests ====================

class TestWMPPagination:
    """Tests for WMP pagination logic."""
    
    def test_pagination_first_page(self, sample_products):
        """Test first page pagination."""
        paginated = _paginate_products(sample_products, page=1, page_size=2)
        
        assert len(paginated) == 2
        assert paginated[0]["product_code"] == "LC2026000001"
    
    def test_pagination_second_page(self, sample_products):
        """Test second page pagination."""
        paginated = _paginate_products(sample_products, page=2, page_size=2)
        
        assert len(paginated) == 2
        assert paginated[0]["product_code"] == "LC2026000003"
    
    def test_pagination_last_page(self, sample_products):
        """Test last page pagination."""
        paginated = _paginate_products(sample_products, page=3, page_size=2)
        
        assert len(paginated) == 1
        assert paginated[0]["product_code"] == "LC2026000005"
    
    def test_pagination_empty_page(self, sample_products):
        """Test empty page pagination."""
        paginated = _paginate_products(sample_products, page=10, page_size=2)
        
        assert len(paginated) == 0


# ==================== Source Tests ====================

class TestWMPSources:
    """Tests for WMP data sources."""
    
    @pytest.mark.asyncio
    async def test_chinawealth_source(self):
        """Test ChinaWealth source adapter."""
        source = ChinaWealthSource()
        data = await source.fetch("wmp_list")
        
        assert len(data) > 0
        assert all("product_code" in p for p in data)
        assert all("yield_rate" in p for p in data)
        assert all("risk_level" in p for p in data)
    
    @pytest.mark.asyncio
    async def test_eastmoney_source(self):
        """Test Eastmoney WMP source adapter."""
        source = EastmoneyWMPSource()
        data = await source.fetch("wmp_list")
        
        assert len(data) > 0
        assert all("product_code" in p for p in data)
    
    @pytest.mark.asyncio
    async def test_mock_source(self):
        """Test mock WMP source adapter."""
        source = MockWMPSource()
        data = await source.fetch("wmp_list")
        
        assert len(data) > 0
        assert all("product_code" in p for p in data)
    
    @pytest.mark.asyncio
    async def test_wmp_gateway_failover(self):
        """Test WMP gateway failover logic."""
        gateway = WMPDataGateway()
        gateway.register_source("chinawealth", ChinaWealthSource(), priority=1)
        gateway.register_source("mock", MockWMPSource(), priority=99)
        
        data, source_name, fallback_chain = await gateway.fetch_wmp_list()
        
        assert len(data) > 0
        assert source_name in ["chinawealth", "mock"]
        assert len(fallback_chain) >= 1


# ==================== Schema Tests ====================

class TestWMPSchemas:
    """Tests for WMP Pydantic schemas."""
    
    def test_wmp_item_creation(self):
        """Test WMPItem schema creation."""
        item = WMPItem(
            product_code="LC2026000001",
            product_name="测试理财产品",
            yield_rate=3.5,
            risk_level="PR2",
            duration=90,
            issuer="测试银行",
            min_amount=10000,
        )
        
        assert item.product_code == "LC2026000001"
        assert item.yield_rate == 3.5
        assert item.risk_level == "PR2"
    
    def test_wmp_filter_params_defaults(self):
        """Test WMPFilterParams default values."""
        params = WMPFilterParams()
        
        assert params.page == 1
        assert params.page_size == 50
        assert params.sort_by == "yield_rate"
        assert params.sort_order == "desc"
    
    def test_wmp_filter_params_validation(self):
        """Test WMPFilterParams validation."""
        # Valid params
        params = WMPFilterParams(
            yield_min=2.0,
            yield_max=5.0,
            risk_levels=["PR2", "PR3"],
            page=1,
            page_size=20,
        )
        
        assert params.yield_min == 2.0
        assert params.yield_max == 5.0
        
        # Invalid page_size (should be <= 200)
        with pytest.raises(Exception):
            WMPFilterParams(page_size=500)
