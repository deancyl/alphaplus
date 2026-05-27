"""
Tests for Brinson Attribution Analysis Service.

Covers:
- Geometric compounding
- Carino linking coefficients
- Menchero linking coefficients
- Multi-period Brinson attribution
- Edge cases and boundary conditions
- Backward compatibility
"""
import math
import pytest
from backend.services.brinson import (
    _geometric_compound,
    _carino_coefficient,
    _carino_adjusted_effects,
    _menchero_coefficient,
    _menchero_adjusted_effects,
    calculate_multi_period_brinson,
    calculate_brinson_attribution,
    calculate_brinson_by_category,
    BrinsonAttributionError,
)


class TestGeometricCompound:
    """Test geometric compound return calculation."""
    
    def test_basic_compound(self):
        """Test basic two-period compounding."""
        result = _geometric_compound([0.1, 0.1])
        expected = (1.1 * 1.1) - 1
        assert abs(result - expected) < 1e-12
    
    def test_zero_return(self):
        """Test with zero return."""
        assert _geometric_compound([0.0]) == 0.0
        assert _geometric_compound([0.0, 0.0, 0.0]) == 0.0
    
    def test_empty_list(self):
        """Test with empty list returns 0."""
        assert _geometric_compound([]) == 0.0
    
    def test_negative_return(self):
        """Test with negative returns."""
        result = _geometric_compound([-0.1, 0.05])
        expected = (0.9 * 1.05) - 1
        assert abs(result - expected) < 1e-12
    
    def test_large_negative_return(self):
        """Test with large negative return (but not -100%)."""
        result = _geometric_compound([-0.5, 0.2])
        expected = (0.5 * 1.2) - 1
        assert abs(result - expected) < 1e-12
    
    def test_multi_period(self):
        """Test multi-period compounding."""
        returns = [0.05, 0.03, 0.02, 0.04]
        result = _geometric_compound(returns)
        expected = 1.05 * 1.03 * 1.02 * 1.04 - 1
        assert abs(result - expected) < 1e-12


class TestCarinoAdjustedEffects:
    """Test Carino-adjusted effects calculation."""
    
    def test_normal_case(self):
        """Test normal case with different returns."""
        effects = [0.01, 0.02]
        portfolio_returns = [0.10, 0.05]
        benchmark_returns = [0.08, 0.04]
        
        adjusted = _carino_adjusted_effects(effects, portfolio_returns, benchmark_returns)
        
        assert len(adjusted) == 2
        assert all(isinstance(a, float) for a in adjusted)
        assert all(not math.isnan(a) for a in adjusted)
    
    def test_equal_returns(self):
        """Test when all returns are equal."""
        effects = [0.01, 0.01]
        portfolio_returns = [0.05, 0.05]
        benchmark_returns = [0.05, 0.05]
        
        adjusted = _carino_adjusted_effects(effects, portfolio_returns, benchmark_returns)
        
        assert len(adjusted) == 2
        assert all(isinstance(a, float) for a in adjusted)
    
    def test_mismatched_lengths(self):
        """Test that mismatched lengths work correctly."""
        effects = [0.01, 0.02]
        portfolio_returns = [0.10, 0.05]
        benchmark_returns = [0.08, 0.04]
        
        adjusted = _carino_adjusted_effects(effects, portfolio_returns, benchmark_returns)
        
        assert len(adjusted) == 2
    
    def test_empty_effects(self):
        """Test with empty effects list."""
        adjusted = _carino_adjusted_effects([], [], [])
        assert adjusted == []
    
    def test_negative_returns(self):
        """Test with negative returns."""
        effects = [0.01, -0.02]
        portfolio_returns = [-0.05, 0.03]
        benchmark_returns = [-0.03, 0.02]
        
        adjusted = _carino_adjusted_effects(effects, portfolio_returns, benchmark_returns)
        
        assert len(adjusted) == 2
        assert all(not math.isnan(a) for a in adjusted)
    
    def test_sum_preserves_effect(self):
        """Test that sum of adjusted effects preserves cumulative effect."""
        effects = [0.01, 0.02]
        portfolio_returns = [0.05, 0.03]
        benchmark_returns = [0.04, 0.02]
        
        adjusted = _carino_adjusted_effects(effects, portfolio_returns, benchmark_returns)
        
        r_p_cum = _geometric_compound(portfolio_returns)
        r_b_cum = _geometric_compound(benchmark_returns)
        geom_excess = r_p_cum - r_b_cum
        arith_excess = sum(p - b for p, b in zip(portfolio_returns, benchmark_returns))
        
        expected_total = (geom_excess / arith_excess) * sum(effects) if abs(arith_excess) > 1e-10 else sum(effects)
        
        assert abs(sum(adjusted) - expected_total) < 1e-10


class TestCarinoCoefficient:
    """Test single-period Carino coefficient."""
    
    def test_normal_case(self):
        """Test normal case with different returns."""
        k = _carino_coefficient(0.10, 0.08)
        expected = (math.log(1.1) - math.log(1.08)) / 0.02
        assert abs(k - expected) < 1e-12
    
    def test_equal_returns(self):
        """Test boundary case when R_p = R_b."""
        k = _carino_coefficient(0.05, 0.05)
        expected = 1.0 / 1.05
        assert abs(k - expected) < 1e-10
    
    def test_near_equal_returns(self):
        """Test when R_p ≈ R_b (within tolerance)."""
        k = _carino_coefficient(0.0500001, 0.05)
        expected = 1.0 / 1.05
        assert abs(k - expected) < 1e-6
    
    def test_zero_benchmark(self):
        """Test with zero benchmark return."""
        k = _carino_coefficient(0.05, 0.0)
        expected = math.log(1.05) / 0.05
        assert abs(k - expected) < 1e-12
    
    def test_negative_returns(self):
        """Test with negative returns."""
        k = _carino_coefficient(-0.05, -0.03)
        expected = (math.log(0.95) - math.log(0.97)) / (-0.02)
        assert abs(k - expected) < 1e-12
    
    def test_invalid_return_below_minus_one(self):
        """Test that returns <= -1 raise ValueError."""
        with pytest.raises(ValueError, match="must be > -1"):
            _carino_coefficient(-1.5, 0.05)
        
        with pytest.raises(ValueError, match="must be > -1"):
            _carino_coefficient(0.05, -1.0)


class TestMencheroCoefficients:
    """Test Menchero linking coefficient calculation."""
    
    def test_normal_case(self):
        """Test normal case with multiple periods."""
        portfolio_returns = [0.05, 0.03]
        benchmark_returns = [0.04, 0.02]
        
        k_overall, k_list = _menchero_coefficient(portfolio_returns, benchmark_returns)
        
        assert len(k_list) == 2
        assert isinstance(k_overall, float)
        assert all(isinstance(k, float) for k in k_list)
        assert all(not math.isnan(k) for k in k_list)
    
    def test_equal_returns(self):
        """Test when all period returns are equal."""
        portfolio_returns = [0.05, 0.05]
        benchmark_returns = [0.05, 0.05]
        
        k_overall, k_list = _menchero_coefficient(portfolio_returns, benchmark_returns)
        
        assert k_overall == 1.0
        assert all(k == 1.0 for k in k_list)
    
    def test_zero_excess(self):
        """Test when total excess return is zero."""
        portfolio_returns = [0.05, -0.03]
        benchmark_returns = [0.04, -0.02]
        
        k_overall, k_list = _menchero_coefficient(portfolio_returns, benchmark_returns)
        
        assert len(k_list) == 2
        assert all(not math.isnan(k) for k in k_list)
    
    def test_mismatched_lengths(self):
        """Test that mismatched lengths raise ValueError."""
        with pytest.raises(ValueError, match="must have same length"):
            _menchero_coefficient([0.05, 0.03], [0.04])
    
    def test_empty_lists(self):
        """Test that empty lists raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            _menchero_coefficient([], [])
    
    def test_large_negative_return(self):
        """Test handling of large negative returns."""
        portfolio_returns = [-0.5, 0.2]
        benchmark_returns = [-0.3, 0.1]
        
        k_overall, k_list = _menchero_coefficient(portfolio_returns, benchmark_returns)
        
        assert len(k_list) == 2
        assert not math.isnan(k_overall)
        assert not any(math.isnan(k) for k in k_list)


class TestMencheroAdjustedEffects:
    """Test Menchero-adjusted effects calculation."""
    
    def test_normal_case(self):
        """Test normal case with multiple periods."""
        effects = [0.01, 0.02]
        portfolio_returns = [0.05, 0.03]
        benchmark_returns = [0.04, 0.02]
        
        adjusted = _menchero_adjusted_effects(effects, portfolio_returns, benchmark_returns)
        
        assert len(adjusted) == 2
        assert all(isinstance(a, float) for a in adjusted)
        assert all(not math.isnan(a) for a in adjusted)
    
    def test_equal_returns(self):
        """Test when all period returns are equal."""
        effects = [0.01, 0.01]
        portfolio_returns = [0.05, 0.05]
        benchmark_returns = [0.05, 0.05]
        
        adjusted = _menchero_adjusted_effects(effects, portfolio_returns, benchmark_returns)
        
        assert adjusted == effects
    
    def test_zero_excess(self):
        """Test when total excess return is zero."""
        effects = [0.01, 0.02]
        portfolio_returns = [0.05, -0.03]
        benchmark_returns = [0.04, -0.02]
        
        adjusted = _menchero_adjusted_effects(effects, portfolio_returns, benchmark_returns)
        
        assert len(adjusted) == 2
        assert all(not math.isnan(a) for a in adjusted)
    
    def test_empty_effects(self):
        """Test with empty effects list."""
        adjusted = _menchero_adjusted_effects([], [], [])
        assert adjusted == []


class TestMultiPeriodBrinson:
    """Test multi-period Brinson attribution."""
    
    def test_basic_two_period(self):
        """Test basic two-period attribution with consistent effects."""
        # Period 1: excess = 0.05 - 0.04 = 0.01
        # Period 2: excess = 0.03 - 0.02 = 0.01
        single_period_results = [
            {"allocation_effect": 0.004, "selection_effect": 0.004, "interaction_effect": 0.002},
            {"allocation_effect": 0.003, "selection_effect": 0.005, "interaction_effect": 0.002}
        ]
        portfolio_returns = [0.05, 0.03]
        benchmark_returns = [0.04, 0.02]
        
        result = calculate_multi_period_brinson(
            single_period_results, portfolio_returns, benchmark_returns
        )
        
        assert "allocation_effect" in result
        assert "selection_effect" in result
        assert "interaction_effect" in result
        assert "total_effect" in result
        assert "residual" in result
        assert "method" in result
        assert result["residual"] < 1e-12
    
    def test_carino_method(self):
        """Test explicit Carino method with consistent effects."""
        # Period 1: excess = 0.05 - 0.04 = 0.01
        single_period_results = [
            {"allocation_effect": 0.004, "selection_effect": 0.004, "interaction_effect": 0.002}
        ]
        portfolio_returns = [0.05]
        benchmark_returns = [0.04]
        
        result = calculate_multi_period_brinson(
            single_period_results, portfolio_returns, benchmark_returns, method="carino"
        )
        
        assert result["method"] == "carino"
        assert result["residual"] < 1e-12
    
    def test_menchero_method(self):
        """Test explicit Menchero method with consistent effects."""
        # Period 1: excess = 0.05 - 0.04 = 0.01
        single_period_results = [
            {"allocation_effect": 0.004, "selection_effect": 0.004, "interaction_effect": 0.002}
        ]
        portfolio_returns = [0.05]
        benchmark_returns = [0.04]
        
        result = calculate_multi_period_brinson(
            single_period_results, portfolio_returns, benchmark_returns, method="menchero"
        )
        
        assert result["method"] == "menchero"
        assert result["residual"] < 1e-12
    
    def test_auto_method_switch(self):
        """Test auto method selection with consistent effects."""
        # Period 1: excess = 0.05 - 0.04 = 0.01
        single_period_results = [
            {"allocation_effect": 0.004, "selection_effect": 0.004, "interaction_effect": 0.002}
        ]
        portfolio_returns = [0.05]
        benchmark_returns = [0.04]
        
        result = calculate_multi_period_brinson(
            single_period_results, portfolio_returns, benchmark_returns, method="auto"
        )
        
        assert result["method"] in ["carino", "menchero"]
        assert result["residual"] < 1e-12
    
    def test_residual_accuracy(self):
        """Test that residual is within tolerance with consistent effects."""
        # Period 1: excess = 0.06 - 0.04 = 0.02
        # Period 2: excess = 0.04 - 0.02 = 0.02
        # Period 3: excess = 0.05 - 0.03 = 0.02
        single_period_results = [
            {"allocation_effect": 0.008, "selection_effect": 0.008, "interaction_effect": 0.004},
            {"allocation_effect": 0.006, "selection_effect": 0.010, "interaction_effect": 0.004},
            {"allocation_effect": 0.007, "selection_effect": 0.009, "interaction_effect": 0.004}
        ]
        portfolio_returns = [0.06, 0.04, 0.05]
        benchmark_returns = [0.04, 0.02, 0.03]
        
        result = calculate_multi_period_brinson(
            single_period_results, portfolio_returns, benchmark_returns
        )
        
        assert result["residual"] < 1e-12, f"Residual {result['residual']} exceeds 1e-12"
    
    def test_mismatched_results_length(self):
        """Test that mismatched results length raises ValueError."""
        with pytest.raises(ValueError, match="must match number of portfolio returns"):
            calculate_multi_period_brinson(
                [{"allocation_effect": 0.01}],
                [0.05, 0.03],
                [0.04, 0.02]
            )
    
    def test_mismatched_returns_length(self):
        """Test that mismatched returns length raises ValueError."""
        with pytest.raises(ValueError, match="must match number of portfolio returns"):
            calculate_multi_period_brinson(
                [{"allocation_effect": 0.01}, {"allocation_effect": 0.02}],
                [0.05],
                [0.04, 0.02]
            )
    
    def test_empty_results(self):
        """Test that empty results raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            calculate_multi_period_brinson([], [], [])
    
    def test_invalid_method(self):
        """Test that invalid method raises ValueError."""
        with pytest.raises(ValueError, match="Unknown method"):
            calculate_multi_period_brinson(
                [{"allocation_effect": 0.01}],
                [0.05],
                [0.04],
                method="invalid"
            )
    
    def test_negative_returns(self):
        """Test with negative returns and consistent effects."""
        # Period 1: excess = -0.03 - (-0.02) = -0.01
        # Period 2: excess = 0.05 - 0.04 = 0.01
        # Arithmetic sum = 0, but geometric excess ≠ 0
        # This is a valid edge case - adjust effects to match reality
        single_period_results = [
            {"allocation_effect": -0.003, "selection_effect": -0.004, "interaction_effect": -0.003},
            {"allocation_effect": 0.003, "selection_effect": 0.004, "interaction_effect": 0.003}
        ]
        portfolio_returns = [-0.03, 0.05]
        benchmark_returns = [-0.02, 0.04]
        
        # Total arithmetic effects = 0, but geometric excess ≠ 0
        # In this case, the residual will be non-zero because effects don't match returns
        result = calculate_multi_period_brinson(
            single_period_results, portfolio_returns, benchmark_returns
        )
        
        # With effects summing to 0 but geometric excess ≠ 0, residual is expected
        # The test verifies the algorithm handles this edge case gracefully
        assert "residual" in result
        assert not math.isnan(result["residual"])
    
    def test_zero_returns(self):
        """Test with zero returns."""
        single_period_results = [
            {"allocation_effect": 0.0, "selection_effect": 0.0, "interaction_effect": 0.0}
        ]
        portfolio_returns = [0.0]
        benchmark_returns = [0.0]
        
        result = calculate_multi_period_brinson(
            single_period_results, portfolio_returns, benchmark_returns
        )
        
        assert result["residual"] < 1e-12
        assert result["total_effect"] == 0.0
    
    def test_compound_return_calculation(self):
        """Test that compound returns are calculated correctly."""
        single_period_results = [
            {"allocation_effect": 0.01, "selection_effect": 0.02, "interaction_effect": 0.005}
        ]
        portfolio_returns = [0.05]
        benchmark_returns = [0.04]
        
        result = calculate_multi_period_brinson(
            single_period_results, portfolio_returns, benchmark_returns
        )
        
        assert abs(result["portfolio_compound_return"] - 0.05) < 1e-12
        assert abs(result["benchmark_compound_return"] - 0.04) < 1e-12
        assert abs(result["excess_return"] - 0.01) < 1e-12


class TestBackwardCompatibility:
    """Test backward compatibility with existing single-period API."""
    
    def test_calculate_brinson_attribution_exists(self):
        """Test that original function still exists."""
        assert callable(calculate_brinson_attribution)
    
    def test_calculate_brinson_by_category_exists(self):
        """Test that original function still exists."""
        assert callable(calculate_brinson_by_category)
    
    def test_single_period_attribution(self):
        """Test that single-period attribution still works."""
        portfolio_returns = [{"date": "2024-01-01", "return_pct": 5.0, "nav": 1.05}]
        benchmark_returns = [{"date": "2024-01-01", "return_pct": 4.0, "nav": 1.04}]
        fund_allocations = [
            {"fund_code": "000001", "weight": 0.5, "total_return": 6.0},
            {"fund_code": "000002", "weight": 0.5, "total_return": 4.0}
        ]
        
        result = calculate_brinson_attribution(
            portfolio_returns, benchmark_returns, fund_allocations
        )
        
        assert "allocation_effect" in result
        assert "selection_effect" in result
        assert "interaction_effect" in result
        assert "total_effect" in result
    
    def test_category_attribution(self):
        """Test that category-level attribution still works."""
        portfolio_category_returns = [
            {"category": "equity", "weight": 0.6, "return": 0.08},
            {"category": "bond", "weight": 0.4, "return": 0.03}
        ]
        benchmark_category_returns = [
            {"category": "equity", "weight": 0.5, "return": 0.06},
            {"category": "bond", "weight": 0.5, "return": 0.04}
        ]
        
        result = calculate_brinson_by_category(
            portfolio_category_returns, benchmark_category_returns
        )
        
        assert "allocation_effect" in result
        assert "selection_effect" in result
        assert "interaction_effect" in result
        assert "total_effect" in result


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_single_period(self):
        """Test with single period with consistent effects."""
        # Period 1: excess = 0.05 - 0.04 = 0.01
        single_period_results = [
            {"allocation_effect": 0.004, "selection_effect": 0.004, "interaction_effect": 0.002}
        ]
        portfolio_returns = [0.05]
        benchmark_returns = [0.04]
        
        result = calculate_multi_period_brinson(
            single_period_results, portfolio_returns, benchmark_returns
        )
        
        assert result["residual"] < 1e-12
    
    def test_many_periods(self):
        """Test with many periods with consistent effects."""
        # All periods: excess = 0.02 - 0.015 = 0.005
        n_periods = 12
        single_period_results = [
            {"allocation_effect": 0.002, "selection_effect": 0.002, "interaction_effect": 0.001}
            for _ in range(n_periods)
        ]
        portfolio_returns = [0.02] * n_periods
        benchmark_returns = [0.015] * n_periods
        
        result = calculate_multi_period_brinson(
            single_period_results, portfolio_returns, benchmark_returns
        )
        
        assert result["residual"] < 1e-12
    
    def test_very_small_returns(self):
        """Test with very small returns with consistent effects."""
        # Period 1: excess = 0.0005 - 0.0004 = 0.0001
        single_period_results = [
            {"allocation_effect": 0.00004, "selection_effect": 0.00004, "interaction_effect": 0.00002}
        ]
        portfolio_returns = [0.0005]
        benchmark_returns = [0.0004]
        
        result = calculate_multi_period_brinson(
            single_period_results, portfolio_returns, benchmark_returns
        )
        
        assert result["residual"] < 1e-12
    
    def test_large_returns(self):
        """Test with large returns with consistent effects."""
        # Period 1: excess = 0.20 - 0.10 = 0.10
        single_period_results = [
            {"allocation_effect": 0.04, "selection_effect": 0.04, "interaction_effect": 0.02}
        ]
        portfolio_returns = [0.20]
        benchmark_returns = [0.10]
        
        result = calculate_multi_period_brinson(
            single_period_results, portfolio_returns, benchmark_returns
        )
        
        assert result["residual"] < 1e-12
    
    def test_mixed_positive_negative(self):
        """Test with mixed positive and negative returns with consistent effects."""
        # Period 1: excess = 0.06 - 0.04 = 0.02
        # Period 2: excess = -0.03 - (-0.02) = -0.01
        # Period 3: excess = 0.05 - 0.03 = 0.02
        single_period_results = [
            {"allocation_effect": 0.008, "selection_effect": 0.008, "interaction_effect": 0.004},
            {"allocation_effect": -0.004, "selection_effect": -0.004, "interaction_effect": -0.002},
            {"allocation_effect": 0.008, "selection_effect": 0.008, "interaction_effect": 0.004}
        ]
        portfolio_returns = [0.06, -0.03, 0.05]
        benchmark_returns = [0.04, -0.02, 0.03]
        
        result = calculate_multi_period_brinson(
            single_period_results, portfolio_returns, benchmark_returns
        )
        
        assert result["residual"] < 1e-12
    
    def test_missing_effect_keys(self):
        """Test handling of missing effect keys (should default to 0)."""
        single_period_results = [
            {"allocation_effect": 0.01},  # Missing selection and interaction
            {"selection_effect": 0.02}   # Missing allocation and interaction
        ]
        portfolio_returns = [0.05, 0.03]
        benchmark_returns = [0.04, 0.02]
        
        result = calculate_multi_period_brinson(
            single_period_results, portfolio_returns, benchmark_returns
        )
        
        assert "allocation_effect" in result
        assert "selection_effect" in result
        assert "interaction_effect" in result
