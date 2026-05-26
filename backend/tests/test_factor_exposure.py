"""
Unit tests for factor exposure analyzer.

Tests cover:
- SLSQP optimization with constraints
- Factor exposure weights sum to 1.0
- Factor exposure weights >= 0.0
- Performance benchmarking (<200ms)
- R² calculation
- O-U fallback simulation
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
import numpy as np
import time
from backend.services.factor_exposure import (
    FactorExposureAnalyzer,
    analyze_factor_exposure,
    STYLE_FACTORS,
    SECTOR_FACTORS,
    ALL_FACTORS,
)


class TestFactorExposureAnalyzer:
    """Test FactorExposureAnalyzer class."""
    
    def test_analyzer_initialization(self):
        """Test analyzer initializes with correct number of factors."""
        analyzer = FactorExposureAnalyzer(n_factors=14)
        
        assert analyzer.n_factors == 14
        assert len(analyzer.style_factors) == 6
        assert len(analyzer.sector_factors) == 8
        assert len(analyzer.all_factors) == 14
        assert analyzer.all_factors == ALL_FACTORS
    
    def test_factor_names(self):
        """Test factor names are correctly defined."""
        assert STYLE_FACTORS == ["SIZE", "VALUE", "MOMENTUM", "VOLATILITY", "QUALITY", "GROWTH"]
        assert SECTOR_FACTORS == ["FINANCE", "TECHNOLOGY", "HEALTHCARE", "CONSUMER", 
                                   "ENERGY", "MATERIALS", "INDUSTRIAL", "REALTY"]
    
    def test_estimate_exposure_shape(self):
        """Test estimate_exposure returns correct shape."""
        analyzer = FactorExposureAnalyzer()
        
        # Generate sample data
        T = 252
        n_factors = 14
        fund_returns = np.random.normal(0.0003, 0.01, T)
        factor_returns = np.random.normal(0.0002, 0.005, (T, n_factors))
        
        weights, metadata = analyzer.estimate_exposure(fund_returns, factor_returns)
        
        assert weights.shape == (n_factors,), f"Expected (14,), got {weights.shape}"
    
    def test_weights_sum_to_one(self):
        """Test weights sum to 1.0 (no leverage constraint)."""
        analyzer = FactorExposureAnalyzer()
        
        T = 252
        n_factors = 14
        fund_returns = np.random.normal(0.0003, 0.01, T)
        factor_returns = np.random.normal(0.0002, 0.005, (T, n_factors))
        
        weights, _ = analyzer.estimate_exposure(fund_returns, factor_returns)
        
        weight_sum = np.sum(weights)
        assert abs(weight_sum - 1.0) < 1e-6, f"Weights sum to {weight_sum}, expected 1.0"
    
    def test_weights_non_negative(self):
        """Test all weights >= 0.0 (no short selling constraint)."""
        analyzer = FactorExposureAnalyzer()
        
        T = 252
        n_factors = 14
        fund_returns = np.random.normal(0.0003, 0.01, T)
        factor_returns = np.random.normal(0.0002, 0.005, (T, n_factors))
        
        weights, _ = analyzer.estimate_exposure(fund_returns, factor_returns)
        
        assert np.all(weights >= -1e-6), f"Found negative weights: {weights[weights < 0]}"
    
    def test_optimization_convergence(self):
        """Test SLSQP optimization converges successfully."""
        analyzer = FactorExposureAnalyzer()
        
        T = 252
        n_factors = 14
        fund_returns = np.random.normal(0.0003, 0.01, T)
        factor_returns = np.random.normal(0.0002, 0.005, (T, n_factors))
        
        weights, metadata = analyzer.estimate_exposure(fund_returns, factor_returns)
        
        assert metadata["optimization_success"], f"Optimization failed: {metadata['message']}"
        assert metadata["iterations"] > 0, "No iterations performed"
    
    def test_r_squared_calculation(self):
        """Test R² is calculated and in valid range [0, 1]."""
        analyzer = FactorExposureAnalyzer()
        
        T = 252
        n_factors = 14
        fund_returns = np.random.normal(0.0003, 0.01, T)
        factor_returns = np.random.normal(0.0002, 0.005, (T, n_factors))
        
        weights, metadata = analyzer.estimate_exposure(fund_returns, factor_returns)
        
        r_squared = metadata["r_squared"]
        assert 0.0 <= r_squared <= 1.0, f"R² = {r_squared} outside [0, 1]"
    
    def test_performance_under_200ms(self):
        """Test optimization completes in <200ms for 252 days, 14 factors."""
        analyzer = FactorExposureAnalyzer()
        
        T = 252
        n_factors = 14
        fund_returns = np.random.normal(0.0003, 0.01, T)
        factor_returns = np.random.normal(0.0002, 0.005, (T, n_factors))
        
        # Warm up
        for _ in range(3):
            analyzer.estimate_exposure(fund_returns, factor_returns)
        
        # Benchmark
        total_time = 0.0
        n_runs = 10
        for i in range(n_runs):
            fund_returns_new = np.random.normal(0.0003, 0.01, T)
            factor_returns_new = np.random.normal(0.0002, 0.005, (T, n_factors))
            
            start = time.perf_counter()
            weights, metadata = analyzer.estimate_exposure(fund_returns_new, factor_returns_new)
            total_time += metadata["elapsed_ms"]
        
        avg_time_ms = total_time / n_runs
        
        assert avg_time_ms < 200.0, f"Performance target not met: {avg_time_ms:.2f}ms > 200ms"
        print(f"\nPerformance: {avg_time_ms:.2f}ms for 252 days, 14 factors")
    
    def test_estimate_exposure_with_perfect_fit(self):
        """Test estimation recovers true weights with perfect linear relationship."""
        analyzer = FactorExposureAnalyzer()
        
        # Create perfect linear relationship
        T = 252
        n_factors = 14
        
        # True weights (known exposure)
        true_weights = np.array([
            0.15, 0.10, 0.20, 0.05, 0.10, 0.05,  # 6 style
            0.10, 0.08, 0.05, 0.07, 0.02, 0.01, 0.01, 0.01,  # 8 sector
        ])
        
        # Generate factor returns
        np.random.seed(42)
        factor_returns = np.random.normal(0.0002, 0.005, (T, n_factors))
        
        # Generate fund returns as exact linear combination
        fund_returns = np.dot(factor_returns, true_weights)
        
        # Estimate
        estimated_weights, metadata = analyzer.estimate_exposure(fund_returns, factor_returns)
        
        # Check close to true weights (with some tolerance due to optimization)
        max_error = np.max(np.abs(estimated_weights - true_weights))
        assert max_error < 0.05, f"Max weight error {max_error:.3f} > 0.05"
        
        # Check R² is near 1.0
        assert metadata["r_squared"] > 0.99, f"R² = {metadata['r_squared']:.3f} < 0.99"
    
    def test_estimate_exposure_handles_different_shapes(self):
        """Test estimate_exposure handles various input shapes."""
        analyzer = FactorExposureAnalyzer()
        
        T = 100
        n_factors = 14
        
        # Test with 1D fund_returns
        fund_returns_1d = np.random.normal(0.0003, 0.01, T)
        factor_returns = np.random.normal(0.0002, 0.005, (T, n_factors))
        
        weights, metadata = analyzer.estimate_exposure(fund_returns_1d, factor_returns)
        assert weights.shape == (n_factors,)
        
        # Test with 2D fund_returns (T, 1)
        fund_returns_2d = fund_returns_1d.reshape(-1, 1)
        weights, metadata = analyzer.estimate_exposure(fund_returns_2d, factor_returns)
        assert weights.shape == (n_factors,)


class TestFactorReturnsSimulation:
    """Test factor returns simulation fallback."""
    
    def test_get_factor_returns_shape(self):
        """Test get_factor_returns returns correct shape."""
        analyzer = FactorExposureAnalyzer()
        
        start_date = "2024-01-01"
        end_date = "2024-12-31"
        
        factor_returns = analyzer.get_factor_returns(start_date, end_date)
        
        assert factor_returns.shape[1] == 14, f"Expected 14 factors, got {factor_returns.shape[1]}"
        assert factor_returns.shape[0] > 0, "Empty time series"
    
    def test_simulated_factor_returns_realistic_range(self):
        """Test simulated factor returns are in realistic range."""
        analyzer = FactorExposureAnalyzer()
        
        start_date = "2024-01-01"
        end_date = "2024-12-31"
        
        factor_returns = analyzer.get_factor_returns(start_date, end_date)
        
        # Daily returns should be in [-5%, 5%] range typically
        assert np.all(factor_returns > -0.05), "Factor returns too negative"
        assert np.all(factor_returns < 0.05), "Factor returns too positive"
        
        # Check mean is near zero
        mean_return = np.mean(factor_returns)
        assert abs(mean_return) < 0.001, f"Mean return {mean_return:.4f} too far from zero"
    
    def test_factor_returns_caching(self):
        """Test factor returns caching mechanism."""
        analyzer = FactorExposureAnalyzer()
        
        start_date = "2024-01-01"
        end_date = "2024-12-31"
        
        # First call (should use simulation)
        factor_returns_1 = analyzer.get_factor_returns(start_date, end_date, use_cache=False)
        
        # Second call (should use cache)
        start = time.perf_counter()
        factor_returns_2 = analyzer.get_factor_returns(start_date, end_date, use_cache=True)
        elapsed = (time.perf_counter() - start) * 1000
        
        # Cache should be fast (<1ms)
        assert elapsed < 5.0, f"Cache lookup took {elapsed:.2f}ms > 5ms"
        
        # Results should be identical
        assert np.allclose(factor_returns_1, factor_returns_2), "Cache returned different results"


class TestFormatExposureResult:
    """Test result formatting."""
    
    def test_format_exposure_result_structure(self):
        """Test format_exposure_result returns correct structure."""
        analyzer = FactorExposureAnalyzer()
        
        weights = np.array([0.15, 0.10, 0.20, 0.05, 0.10, 0.05,
                           0.10, 0.08, 0.05, 0.07, 0.02, 0.01, 0.01, 0.01])
        metadata = {"r_squared": 0.85, "optimization_success": True}
        
        result = analyzer.format_exposure_result(weights, metadata)
        
        assert "factor_exposures" in result
        assert "style_factors" in result
        assert "sector_factors" in result
        assert "metadata" in result
        
        assert len(result["factor_exposures"]) == 14
        assert len(result["style_factors"]) == 6
        assert len(result["sector_factors"]) == 8
    
    def test_format_exposure_sorted_by_weight(self):
        """Test factor exposures are sorted by weight descending."""
        analyzer = FactorExposureAnalyzer()
        
        weights = np.array([0.15, 0.10, 0.20, 0.05, 0.10, 0.05,
                           0.10, 0.08, 0.05, 0.07, 0.02, 0.01, 0.01, 0.01])
        metadata = {"r_squared": 0.85, "optimization_success": True}
        
        result = analyzer.format_exposure_result(weights, metadata)
        
        exposures = result["factor_exposures"]
        weights_list = [e["weight"] for e in exposures]
        
        # Check sorted descending
        assert all(weights_list[i] >= weights_list[i+1] for i in range(len(weights_list)-1)), \
            "Exposures not sorted by weight descending"


class TestConvenienceFunction:
    """Test analyze_factor_exposure convenience function."""
    
    def test_analyze_factor_exposure_integration(self):
        """Test end-to-end factor exposure analysis."""
        # Generate sample fund returns
        T = 252
        fund_returns = np.random.normal(0.0003, 0.01, T)
        
        start_date = "2024-01-01"
        end_date = "2024-12-31"
        
        result = analyze_factor_exposure(fund_returns, start_date, end_date)
        
        assert "factor_exposures" in result
        assert "style_factors" in result
        assert "sector_factors" in result
        assert "metadata" in result
        
        # Check all weights present
        total_weight = sum(e["weight"] for e in result["factor_exposures"])
        assert abs(total_weight - 1.0) < 1e-6, f"Total weight {total_weight:.4f} != 1.0"
    
    def test_analyze_factor_exposure_with_precomputed_returns(self):
        """Test analysis with pre-computed factor returns."""
        T = 252
        n_factors = 14
        
        fund_returns = np.random.normal(0.0003, 0.01, T)
        factor_returns = np.random.normal(0.0002, 0.005, (T, n_factors))
        
        start_date = "2024-01-01"
        end_date = "2024-12-31"
        
        result = analyze_factor_exposure(fund_returns, start_date, end_date, factor_returns)
        
        assert "factor_exposures" in result
        assert result["metadata"]["n_factors"] == n_factors


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_estimate_exposure_with_zero_variance(self):
        """Test handling of zero-variance fund returns."""
        analyzer = FactorExposureAnalyzer()
        
        T = 252
        n_factors = 14
        
        # Zero variance fund returns
        fund_returns = np.full(T, 0.001)
        factor_returns = np.random.normal(0.0002, 0.005, (T, n_factors))
        
        weights, metadata = analyzer.estimate_exposure(fund_returns, factor_returns)
        
        # Should still return valid weights
        assert weights.shape == (n_factors,)
        assert np.sum(weights) > 0.99
    
    def test_estimate_exposure_with_high_correlation_factors(self):
        """Test handling of highly correlated factors."""
        analyzer = FactorExposureAnalyzer()
        
        T = 252
        n_factors = 14
        
        # Create highly correlated factors
        base_factor = np.random.normal(0.0002, 0.005, T)
        factor_returns = np.zeros((T, n_factors))
        for i in range(n_factors):
            factor_returns[:, i] = base_factor + np.random.normal(0, 0.0001, T)
        
        fund_returns = np.random.normal(0.0003, 0.01, T)
        
        weights, metadata = analyzer.estimate_exposure(fund_returns, factor_returns)
        
        # Should still converge
        assert weights.shape == (n_factors,)
        assert np.isclose(np.sum(weights), 1.0, atol=1e-6)
    
    def test_estimate_exposure_with_short_history(self):
        """Test handling of short history (fewer time points than factors)."""
        analyzer = FactorExposureAnalyzer()
        
        T = 10  # Only 10 days
        n_factors = 14
        
        fund_returns = np.random.normal(0.0003, 0.01, T)
        factor_returns = np.random.normal(0.0002, 0.005, (T, n_factors))
        
        weights, metadata = analyzer.estimate_exposure(fund_returns, factor_returns)
        
        # Should still return valid weights
        assert weights.shape == (n_factors,)
        assert np.isclose(np.sum(weights), 1.0, atol=1e-6)


class TestReproducibility:
    """Test reproducibility of results."""
    
    def test_reproducible_with_same_data(self):
        """Test same input produces same output."""
        analyzer = FactorExposureAnalyzer()
        
        T = 252
        n_factors = 14
        
        np.random.seed(42)
        fund_returns = np.random.normal(0.0003, 0.01, T)
        factor_returns = np.random.normal(0.0002, 0.005, (T, n_factors))
        
        weights1, metadata1 = analyzer.estimate_exposure(fund_returns, factor_returns)
        weights2, metadata2 = analyzer.estimate_exposure(fund_returns, factor_returns)
        
        assert np.allclose(weights1, weights2), "Same input should produce same output"
        assert metadata1["r_squared"] == metadata2["r_squared"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
