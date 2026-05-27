"""
Tests for New High Ratio calculation and filtering.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest


@pytest.mark.asyncio
async def test_new_high_ratio_schema_validation():
    """Test that FundFilterRequest schema accepts new_high_ratio_min parameter."""
    from backend.schemas.fund import FundFilterRequest
    
    request = FundFilterRequest(
        page=1,
        page_size=50,
        sort_by="return_1y",
        sort_order="desc",
        new_high_ratio_min=50.0
    )
    
    assert request.new_high_ratio_min == 50.0


@pytest.mark.asyncio
async def test_fund_indicator_response_schema():
    """Test that FundIndicatorResponse schema includes new_high_ratio_1y field."""
    from backend.schemas.fund import FundIndicatorResponse
    
    response = FundIndicatorResponse(
        fund_code="000001",
        fund_name="Test Fund",
        fund_type="混合型",
        manager="Test Manager",
        setup_date="2020-01-01",
        setup_year=5.0,
        scale=10.0,
        company_name="Test Company",
        return_1y=15.5,
        volatility_1y=12.3,
        max_drawdown_1y=-8.5,
        sharpe_1y=1.2,
        new_high_ratio_1y=45.5,
        heavy_sector="科技"
    )
    
    assert response.new_high_ratio_1y == 45.5


@pytest.mark.asyncio
async def test_new_high_ratio_nullable():
    """Test that new_high_ratio_1y is nullable (Optional)."""
    from backend.schemas.fund import FundIndicatorResponse
    
    response = FundIndicatorResponse(
        fund_code="000001",
        fund_name="Test Fund",
        fund_type="混合型"
    )
    
    assert response.new_high_ratio_1y is None


@pytest.mark.asyncio
async def test_new_high_ratio_with_other_filter_params():
    """Test that new_high_ratio_min works with other filter parameters."""
    from backend.schemas.fund import FundFilterRequest
    
    request = FundFilterRequest(
        page=1,
        page_size=50,
        sort_by="return_1y",
        sort_order="desc",
        new_high_ratio_min=30.0,
        setup_year_min=3,
        scale_min=1.0
    )
    
    assert request.new_high_ratio_min == 30.0
    assert request.setup_year_min == 3
    assert request.scale_min == 1.0


@pytest.mark.asyncio
async def test_calculate_new_high_ratio_service_import():
    """Test that fund_metrics service can be imported and function exists."""
    from backend.services.fund_metrics import calculate_new_high_ratio, batch_calculate_new_high_ratio
    
    assert callable(calculate_new_high_ratio)
    assert callable(batch_calculate_new_high_ratio)


@pytest.mark.asyncio
async def test_fund_indicators_model_has_field():
    """Test that FundIndicators model has new_high_ratio_1y field."""
    from backend.models.fund import FundIndicators
    
    assert hasattr(FundIndicators, 'new_high_ratio_1y')