"""
Comprehensive test suite for gold conversion functions.

Tests cover:
1. Constant precision
2. Unit conversion (troy oz to grams)
3. Currency conversion (USD to CNY)
4. Purity adjustment
5. VAT friction
6. Round-trip error verification
7. API response format
"""
import pytest
import asyncio
from backend.services.gold_constants import (
    TROY_OUNCE_TO_GRAMS,
    LONDON_GOLD_PURITY,
    SHANGHAI_GOLD_PURITY,
    VAT_FRICTION_FACTOR,
    DEFAULT_USDCNY_FALLBACK,
    get_usdcny_rate,
    convert_london_to_shanghai,
    convert_shanghai_to_london,
    verify_round_trip,
    calculate_premium,
)


class TestConstants:
    """Test case 1-4: Constant precision tests."""
    
    def test_troy_ounce_precision(self):
        """Test 1: Troy ounce constant has 7 decimal places."""
        assert TROY_OUNCE_TO_GRAMS == 31.1034768
        assert TROY_OUNCE_TO_GRAMS != 31.10  # Must NOT be the old approximate value
    
    def test_london_gold_purity(self):
        """Test 2: LBMA Good Delivery standard purity."""
        assert LONDON_GOLD_PURITY == 0.995
        assert 0.99 <= LONDON_GOLD_PURITY <= 1.0
    
    def test_shanghai_gold_purity(self):
        """Test 3: SGE Au99.99 standard purity."""
        assert SHANGHAI_GOLD_PURITY == 0.9999
        assert LONDON_GOLD_PURITY < SHANGHAI_GOLD_PURITY  # Shanghai is purer
    
    def test_vat_friction_factor(self):
        """Test 4: VAT friction factor is 0.35%."""
        assert VAT_FRICTION_FACTOR == 0.0035
        assert 0 < VAT_FRICTION_FACTOR < 0.01  # Reasonable range


class TestUnitConversion:
    """Test case 5-6: Unit conversion tests."""
    
    def test_london_to_shanghai_unit_conversion(self):
        """Test 5: Convert USD/oz to CNY/g."""
        london_price = 2000.0  # $2000/oz
        usdcny = 7.20
        
        result = convert_london_to_shanghai(london_price, usdcny, include_vat=False)
        
        # Calculate expected: 2000 / 31.1034768 * 7.20 * (0.9999/0.995)
        expected_usd_per_gram = 2000 / 31.1034768
        expected_cny_per_gram = expected_usd_per_gram * 7.20
        expected_purity_factor = 0.9999 / 0.995
        
        assert abs(result["usd_per_gram"] - expected_usd_per_gram) < 0.0001
        assert abs(result["cny_per_gram_unadjusted"] - expected_cny_per_gram) < 0.01
        assert abs(result["purity_factor"] - expected_purity_factor) < 0.00001
    
    def test_shanghai_to_london_unit_conversion(self):
        """Test 6: Convert CNY/g to USD/oz."""
        shanghai_price = 585.0  # 585 CNY/g
        usdcny = 7.20
        
        result = convert_shanghai_to_london(shanghai_price, usdcny, include_vat=False)
        
        # Should have all conversion factors
        assert "shanghai_cny_per_g" in result
        assert "usd_per_gram" in result
        assert "london_usd_per_oz" in result
        
        # Verify the calculation
        assert result["shanghai_cny_per_g"] == shanghai_price
        assert result["london_usd_per_oz"] > 0


class TestCurrencyConversion:
    """Test case 7: Currency conversion test."""
    
    def test_usdcny_rate_fetch(self):
        """Test 7: USDCNY rate fetching with fallback."""
        rate = asyncio.run(get_usdcny_rate())
        assert rate > 0
        assert rate == DEFAULT_USDCNY_FALLBACK or rate > 0  # Either fallback or real rate
        assert 6.0 < rate < 8.0  # Reasonable range for USDCNY


class TestPurityAdjustment:
    """Test case 8: Purity adjustment test."""
    
    def test_purity_factor_application(self):
        """Test 8: Purity factor correctly adjusts price."""
        london_price = 2000.0
        usdcny = 7.20
        
        result = convert_london_to_shanghai(london_price, usdcny, include_vat=False)
        
        # Purity factor should be > 1 because Shanghai gold is purer
        purity_factor = SHANGHAI_GOLD_PURITY / LONDON_GOLD_PURITY
        assert result["purity_factor"] > 1.0
        assert abs(result["purity_factor"] - purity_factor) < 0.00001
        
        # Theoretical Shanghai price should be higher due to purity
        unadjusted = result["cny_per_gram_unadjusted"]
        theoretical = result["shanghai_theoretical"]
        assert theoretical > unadjusted  # Purity adjustment increases price


class TestVATFriction:
    """Test case 9-10: VAT friction tests."""
    
    def test_vat_increases_price(self):
        """Test 9: VAT inclusion increases Shanghai price."""
        london_price = 2000.0
        usdcny = 7.20
        
        without_vat = convert_london_to_shanghai(london_price, usdcny, include_vat=False)
        with_vat = convert_london_to_shanghai(london_price, usdcny, include_vat=True)
        
        assert with_vat["shanghai_with_vat"] > without_vat["shanghai_theoretical"]
        
        # Verify the VAT factor
        expected_vat_price = without_vat["shanghai_theoretical"] * (1 + VAT_FRICTION_FACTOR)
        assert abs(with_vat["shanghai_with_vat"] - expected_vat_price) < 0.01
    
    def test_vat_exclusion_flag(self):
        """Test 10: VAT exclusion flag is respected."""
        london_price = 2000.0
        usdcny = 7.20
        
        with_vat = convert_london_to_shanghai(london_price, usdcny, include_vat=True)
        without_vat = convert_london_to_shanghai(london_price, usdcny, include_vat=False)
        
        assert with_vat["vat_included"] is True
        assert without_vat["vat_included"] is False
        assert with_vat["vat_factor"] == VAT_FRICTION_FACTOR
        assert without_vat["vat_factor"] == 0.0


class TestRoundTrip:
    """Test case 11: Round-trip error verification."""
    
    def test_round_trip_error_less_than_0_01_percent(self):
        """Test 11: Round-trip conversion error must be < 0.01%."""
        test_cases = [
            (2000.0, 7.20),   # Standard case
            (1800.0, 7.10),   # Lower price
            (2200.0, 7.30),   # Higher price
            (1500.0, 6.80),   # Low price, low rate
            (2500.0, 7.50),   # High price, high rate
        ]
        
        for london_price, usdcny in test_cases:
            result = verify_round_trip(london_price, usdcny, include_vat=True)
            
            assert result["passes_threshold"] is True, \
                f"Round-trip failed for {london_price}/oz at {usdcny} rate: {result['percent_error']}%"
            
            assert result["percent_error"] < 0.01, \
                f"Error {result['percent_error']}% exceeds 0.01% threshold"
    
    def test_round_trip_without_vat(self):
        """Test 11b: Round-trip without VAT also passes."""
        result = verify_round_trip(2000.0, 7.20, include_vat=False)
        assert result["passes_threshold"] is True


class TestAPIResponseFormat:
    """Test case 12: API response format test."""
    
    def test_conversion_factors_in_response(self):
        """Test 12: All conversion factors are exposed in response."""
        london_price = 2000.0
        usdcny = 7.20
        
        result = convert_london_to_shanghai(london_price, usdcny, include_vat=True)
        
        required_fields = [
            "london_usd_per_oz",
            "usd_per_gram",
            "cny_per_gram_unadjusted",
            "purity_factor",
            "shanghai_theoretical",
            "shanghai_with_vat",
            "usdcny_rate",
            "vat_included",
            "vat_factor",
        ]
        
        for field in required_fields:
            assert field in result, f"Missing field: {field}"
        
        # Verify all values are numeric
        for field, value in result.items():
            if isinstance(value, (int, float)):
                assert value >= 0, f"Negative value for {field}: {value}"
    
    def test_premium_calculation(self):
        """Test 12b: Premium calculation returns correct format."""
        premium = calculate_premium(590.0, 585.0)
        
        assert "shanghai_actual" in premium
        assert "shanghai_theoretical" in premium
        assert "absolute_premium" in premium
        assert "percent_premium" in premium
        
        assert premium["absolute_premium"] == 5.0
        assert abs(premium["percent_premium"] - 0.8547) < 0.01


class TestEdgeCases:
    """Additional edge case tests."""
    
    def test_zero_price_handling(self):
        """Test handling of zero price."""
        result = convert_london_to_shanghai(0.0, 7.20, include_vat=True)
        assert result["london_usd_per_oz"] == 0.0
        assert result["shanghai_with_vat"] == 0.0
    
    def test_extreme_prices(self):
        """Test handling of extreme prices."""
        # Very high price
        high_result = convert_london_to_shanghai(10000.0, 7.20, include_vat=True)
        assert high_result["shanghai_with_vat"] > 0
        
        # Very low price
        low_result = convert_london_to_shanghai(100.0, 7.20, include_vat=True)
        assert low_result["shanghai_with_vat"] > 0
    
    def test_extreme_exchange_rates(self):
        """Test handling of extreme exchange rates."""
        # High rate
        high_rate = convert_london_to_shanghai(2000.0, 8.0, include_vat=True)
        
        # Low rate
        low_rate = convert_london_to_shanghai(2000.0, 6.0, include_vat=True)
        
        # Higher rate should result in higher CNY price
        assert high_rate["shanghai_with_vat"] > low_rate["shanghai_with_vat"]


class TestConversionAccuracy:
    """Test conversion accuracy against known values."""
    
    def test_known_conversion(self):
        """Test against known conversion (with VAT)."""
        # London: $2000/oz, USDCNY: 7.20
        # Expected: 2000 / 31.1034768 * 7.20 * (0.9999/0.995) * 1.0035
        london_price = 2000.0
        usdcny = 7.20
        
        result = convert_london_to_shanghai(london_price, usdcny, include_vat=True)
        
        # Manual calculation:
        # 2000 / 31.1034768 = 64.3014 USD/g
        # 64.3014 * 7.20 = 462.97 CNY/g
        # 462.97 * (0.9999/0.995) = 465.30 CNY/g (purity adjusted)
        # 465.30 * 1.0035 = 466.93 CNY/g (with VAT)
        
        expected_shanghai = (2000.0 / 31.1034768 * 7.20 * 
                            (SHANGHAI_GOLD_PURITY / LONDON_GOLD_PURITY) * 
                            (1 + VAT_FRICTION_FACTOR))
        
        assert abs(result["shanghai_with_vat"] - expected_shanghai) < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
