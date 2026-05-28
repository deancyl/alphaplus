"""
Tests for v0.1.22 config extension: warmup, quant, and gold parameters.
"""
import pytest
from backend.core.config import settings


class TestWarmupConfig:
    """Test warmup configuration parameters."""
    
    def test_warmup_top_funds_count_default(self):
        """Test default warmup top funds count."""
        assert settings.warmup_top_funds_count == 50
    
    def test_warmup_index_valuation_codes(self):
        """Test warmup index valuation codes list."""
        assert isinstance(settings.warmup_index_valuation_codes, list)
        assert len(settings.warmup_index_valuation_codes) == 7
        assert "000300" in settings.warmup_index_valuation_codes
        assert "000905" in settings.warmup_index_valuation_codes


class TestQuantConfig:
    """Test quantitative analysis configuration parameters."""
    
    def test_fear_greed_history_days(self):
        """Test fear-greed history days default."""
        assert settings.fear_greed_history_days == 30
    
    def test_erp_history_days(self):
        """Test ERP history days default."""
        assert settings.erp_history_days == 100
    
    def test_crowding_history_records(self):
        """Test crowding history records default."""
        assert settings.crowding_history_records == 240


class TestGoldConfig:
    """Test gold arbitrage calibration parameters."""
    
    def test_gold_shanghai_purity(self):
        """Test Shanghai gold purity default."""
        assert settings.gold_shanghai_purity == 0.9999
    
    def test_gold_london_purity(self):
        """Test London gold purity default."""
        assert settings.gold_london_purity == 0.9950
    
    def test_gold_vat_friction_factor(self):
        """Test gold VAT friction factor default."""
        assert settings.gold_vat_friction_factor == 0.0035


class TestCoreIndicesConfig:
    """Test CORE_INDICES configuration."""
    
    def test_core_indices_dict_exists(self):
        """Test CORE_INDICES dictionary exists."""
        assert hasattr(settings, 'CORE_INDICES')
        assert isinstance(settings.CORE_INDICES, dict)
    
    def test_core_indices_count(self):
        """Test CORE_INDICES has 17 entries."""
        assert len(settings.CORE_INDICES) == 17
    
    def test_core_indices_key_values(self):
        """Test specific CORE_INDICES entries."""
        assert settings.CORE_INDICES.get("000300") == "沪深300"
        assert settings.CORE_INDICES.get("000905") == "中证500"
        assert settings.CORE_INDICES.get("399006") == "创业板指"
