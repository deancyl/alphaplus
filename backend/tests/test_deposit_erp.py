"""
Tests for deposit rate and ERP linkage feature.
"""
import pytest
from backend.services.risk_free_rates import get_deposit_rate, get_risk_free_rate, DEPOSIT_RATES
from backend.services.deposit_spread import calculate_spread, get_deposit_spread_history


class TestDepositRates:
    """Test deposit rate retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_deposit_rate_1y(self):
        result = await get_deposit_rate("deposit_1y")
        assert result == DEPOSIT_RATES["deposit_1y"]
        assert result == 1.75
    
    @pytest.mark.asyncio
    async def test_get_deposit_rate_3y(self):
        result = await get_deposit_rate("deposit_3y")
        assert result == DEPOSIT_RATES["deposit_3y"]
        assert result == 2.25
    
    @pytest.mark.asyncio
    async def test_get_deposit_rate_5y(self):
        result = await get_deposit_rate("deposit_5y")
        assert result == DEPOSIT_RATES["deposit_5y"]
        assert result == 2.75
    
    @pytest.mark.asyncio
    async def test_get_deposit_rate_invalid_tier(self):
        with pytest.raises(ValueError, match="Unknown deposit tier"):
            await get_deposit_rate("deposit_10y")
    
    @pytest.mark.asyncio
    async def test_get_risk_free_rate_with_deposit(self):
        result = await get_risk_free_rate("deposit_1y")
        assert result == 1.75
        
        result = await get_risk_free_rate("deposit_3y")
        assert result == 2.25
        
        result = await get_risk_free_rate("deposit_5y")
        assert result == 2.75


class TestDepositSpread:
    """Test deposit spread calculations."""
    
    @pytest.mark.asyncio
    async def test_calculate_spread_positive(self):
        result = await calculate_spread(3.0, 2.5)
        assert result == 0.5
    
    @pytest.mark.asyncio
    async def test_calculate_spread_negative(self):
        result = await calculate_spread(2.0, 2.5)
        assert result == -0.5
    
    @pytest.mark.asyncio
    async def test_calculate_spread_zero(self):
        result = await calculate_spread(2.5, 2.5)
        assert result == 0.0
    
    @pytest.mark.asyncio
    async def test_get_deposit_spread_history_1y(self):
        history = await get_deposit_spread_history("deposit_1y", days=30)
        assert len(history) > 0
        assert all("date" in item for item in history)
        assert all("deposit_rate" in item for item in history)
        assert all("bond_rate" in item for item in history)
        assert all("spread" in item for item in history)
        assert all(item["deposit_rate"] == 1.75 for item in history)
    
    @pytest.mark.asyncio
    async def test_get_deposit_spread_history_3y(self):
        history = await get_deposit_spread_history("deposit_3y", days=30)
        assert len(history) > 0
        assert all(item["deposit_rate"] == 2.25 for item in history)
    
    @pytest.mark.asyncio
    async def test_get_deposit_spread_history_5y(self):
        history = await get_deposit_spread_history("deposit_5y", days=30)
        assert len(history) > 0
        assert all(item["deposit_rate"] == 2.75 for item in history)
    
    @pytest.mark.asyncio
    async def test_get_deposit_spread_history_invalid_tier(self):
        with pytest.raises(ValueError, match="Unknown tier"):
            await get_deposit_spread_history("deposit_10y", days=30)
    
    @pytest.mark.asyncio
    async def test_get_deposit_spread_history_sorted(self):
        history = await get_deposit_spread_history("deposit_1y", days=30)
        dates = [item["date"] for item in history]
        assert dates == sorted(dates)


class TestDepositERPIntegration:
    """Integration tests for deposit-ERP feature."""
    
    @pytest.mark.asyncio
    async def test_erp_with_deposit_rate(self):
        deposit_rate = await get_risk_free_rate("deposit_1y")
        pe_ttm = 12.0
        erp = 100.0 / pe_ttm - deposit_rate
        expected_erp = 100.0 / 12.0 - 1.75
        assert abs(erp - expected_erp) < 0.0001
    
    @pytest.mark.asyncio
    async def test_spread_calculation_consistency(self):
        deposit_rate = await get_deposit_rate("deposit_3y")
        bond_rate = 2.5
        spread = await calculate_spread(deposit_rate, bond_rate)
        assert spread == deposit_rate - bond_rate
    
    @pytest.mark.asyncio
    async def test_all_deposit_tiers_available(self):
        tiers = ["deposit_1y", "deposit_3y", "deposit_5y"]
        for tier in tiers:
            rate = await get_deposit_rate(tier)
            assert rate > 0
            assert rate < 10
