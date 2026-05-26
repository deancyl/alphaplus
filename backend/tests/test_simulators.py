"""
Unit tests for stochastic process simulators.

Tests cover:
- GBM path generation shape
- O-U path generation shape
- GBM mean/variance within tolerance (Monte Carlo validation)
- O-U mean reversion property
- Performance benchmarking
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
import numpy as np
import time
from backend.services.simulators import (
    GBMSimulator,
    OUSimulator,
    simulate_from_history,
    simulate_price_fallback,
    simulate_indicator_fallback,
)


class TestGBMSimulator:
    """Test Geometric Brownian Motion simulator."""
    
    def test_gbm_shape(self):
        """Test GBM output shape is (n_paths, N+1)."""
        simulator = GBMSimulator(
            S0=100.0,
            mu=0.08,
            sigma=0.20,
            T=1.0,
            N=252,
            n_paths=1000,
        )
        
        paths = simulator.simulate(seed=42)
        
        assert paths.shape == (1000, 253), f"Expected (1000, 253), got {paths.shape}"
    
    def test_gbm_initial_value(self):
        """Test all paths start at S0."""
        S0 = 100.0
        simulator = GBMSimulator(
            S0=S0,
            mu=0.08,
            sigma=0.20,
            T=1.0,
            N=252,
            n_paths=100,
        )
        
        paths = simulator.simulate(seed=42)
        
        assert np.all(paths[:, 0] == S0), "All paths should start at S0"
    
    def test_gbm_positive_paths(self):
        """Test GBM paths remain positive (log-normal property)."""
        simulator = GBMSimulator(
            S0=100.0,
            mu=0.08,
            sigma=0.20,
            T=1.0,
            N=252,
            n_paths=100,
        )
        
        paths = simulator.simulate(seed=42)
        
        assert np.all(paths > 0), "GBM paths should always be positive"
    
    def test_gbm_mean_within_tolerance(self):
        """Test GBM mean is within 5% of theoretical value (Monte Carlo validation)."""
        # Use large number of paths for statistical significance
        simulator = GBMSimulator(
            S0=100.0,
            mu=0.08,
            sigma=0.20,
            T=1.0,
            N=252,
            n_paths=10000,  # Large sample for Monte Carlo
        )
        
        paths = simulator.simulate(seed=42)
        result = simulator.check_mean(paths)
        
        assert result["tolerance_met"], (
            f"Mean outside tolerance: theoretical={result['theoretical_mean']:.2f}, "
            f"empirical={result['empirical_mean']:.2f}, "
            f"error={result['relative_error']*100:.2f}%"
        )
    
    def test_gbm_variance_within_tolerance(self):
        """Test GBM variance is within 10% of theoretical value."""
        simulator = GBMSimulator(
            S0=100.0,
            mu=0.08,
            sigma=0.20,
            T=1.0,
            N=252,
            n_paths=10000,
        )
        
        paths = simulator.simulate(seed=42)
        result = simulator.check_variance(paths)
        
        assert result["tolerance_met"], (
            f"Variance outside tolerance: theoretical={result['theoretical_variance']:.2f}, "
            f"empirical={result['empirical_variance']:.2f}, "
            f"error={result['relative_error']*100:.2f}%"
        )
    
    def test_gbm_performance(self):
        """Test GBM simulation completes in ~10ms for 1000 paths, 252 steps."""
        simulator = GBMSimulator(
            S0=100.0,
            mu=0.08,
            sigma=0.20,
            T=1.0,
            N=252,
            n_paths=1000,
        )
        
        # Warm up JIT compilation (multiple calls to ensure compilation is cached)
        for i in range(5):
            simulator.simulate(seed=42+i)
        
        # Benchmark (average over multiple runs)
        total_time = 0.0
        for i in range(10):
            start = time.perf_counter()
            simulator.simulate(seed=123+i)
            total_time += (time.perf_counter() - start) * 1000
        elapsed_ms = total_time / 10
        
        # Allow 15ms tolerance for JIT variability in pytest environment
        assert elapsed_ms < 15.0, f"Performance target not met: {elapsed_ms:.2f}ms > 15ms"
        print(f"\nGBM performance: {elapsed_ms:.2f}ms for 1000 paths, 252 steps")


class TestOUSimulator:
    """Test Ornstein-Uhlenbeck simulator."""
    
    def test_ou_shape(self):
        """Test O-U output shape is (n_paths, N+1)."""
        simulator = OUSimulator(
            X0=50.0,
            theta=50.0,
            kappa=0.15,
            sigma=10.0,
            T=1.0,
            N=252,
            n_paths=1000,
        )
        
        paths = simulator.simulate(seed=42)
        
        assert paths.shape == (1000, 253), f"Expected (1000, 253), got {paths.shape}"
    
    def test_ou_initial_value(self):
        """Test all paths start at X0."""
        X0 = 50.0
        simulator = OUSimulator(
            X0=X0,
            theta=50.0,
            kappa=0.15,
            sigma=10.0,
            T=1.0,
            N=252,
            n_paths=100,
        )
        
        paths = simulator.simulate(seed=42)
        
        assert np.all(paths[:, 0] == X0), "All paths should start at X0"
    
    def test_ou_mean_reversion(self):
        """Test O-U paths revert toward theta (mean reversion property)."""
        # Start far from theta
        simulator = OUSimulator(
            X0=80.0,  # Start at 80
            theta=50.0,  # Mean is 50
            kappa=0.5,  # Strong mean reversion
            sigma=5.0,
            T=2.0,  # Long time horizon
            N=504,  # 2 years
            n_paths=1000,
        )
        
        paths = simulator.simulate(seed=42)
        result = simulator.check_mean_reversion(paths)
        
        assert result["mean_reversion_observed"], (
            f"Mean reversion not observed: "
            f"initial_dist={result['initial_distance_from_theta']:.2f}, "
            f"final_dist={result['final_distance_from_theta']:.2f}, "
            f"ratio={result['reversion_ratio']:.2f}"
        )
    
    def test_ou_mean_within_tolerance(self):
        """Test O-U mean is within tolerance of theoretical value."""
        simulator = OUSimulator(
            X0=50.0,
            theta=50.0,
            kappa=0.15,
            sigma=10.0,
            T=1.0,
            N=252,
            n_paths=10000,
        )
        
        paths = simulator.simulate(seed=42)
        result = simulator.check_mean(paths)
        
        assert result["tolerance_met"], (
            f"Mean outside tolerance: theoretical={result['theoretical_mean']:.2f}, "
            f"empirical={result['empirical_mean']:.2f}, "
            f"error={result['absolute_error']:.2f}"
        )
    
    def test_ou_variance_within_tolerance(self):
        """Test O-U variance is within 15% of theoretical value."""
        simulator = OUSimulator(
            X0=50.0,
            theta=50.0,
            kappa=0.15,
            sigma=10.0,
            T=1.0,
            N=252,
            n_paths=10000,
        )
        
        paths = simulator.simulate(seed=42)
        result = simulator.check_variance(paths)
        
        assert result["tolerance_met"], (
            f"Variance outside tolerance: theoretical={result['theoretical_variance']:.2f}, "
            f"empirical={result['empirical_variance']:.2f}, "
            f"error={result['relative_error']*100:.2f}%"
        )
    
    def test_ou_performance(self):
        """Test O-U simulation completes in ~10ms for 1000 paths, 252 steps."""
        simulator = OUSimulator(
            X0=50.0,
            theta=50.0,
            kappa=0.15,
            sigma=10.0,
            T=1.0,
            N=252,
            n_paths=1000,
        )
        
        # Warm up JIT compilation (multiple calls to ensure compilation is cached)
        for i in range(5):
            simulator.simulate(seed=42+i)
        
        # Benchmark (average over multiple runs)
        total_time = 0.0
        for i in range(10):
            start = time.perf_counter()
            simulator.simulate(seed=123+i)
            total_time += (time.perf_counter() - start) * 1000
        elapsed_ms = total_time / 10
        
        # Allow 20ms tolerance for JIT variability in pytest environment
        assert elapsed_ms < 20.0, f"Performance target not met: {elapsed_ms:.2f}ms > 20ms"
        print(f"\nO-U performance: {elapsed_ms:.2f}ms for 1000 paths, 252 steps")


class TestConvenienceFunctions:
    """Test convenience functions for common use cases."""
    
    def test_simulate_price_fallback(self):
        """Test price fallback simulation."""
        paths = simulate_price_fallback(
            last_price=100.0,
            mu=0.08,
            sigma=0.20,
            n_days=30,
            n_paths=100,
        )
        
        assert paths.shape == (100, 31), f"Expected (100, 31), got {paths.shape}"
        assert np.all(paths[:, 0] == 100.0), "All paths should start at last_price"
        assert np.all(paths > 0), "Price paths should be positive"
    
    def test_simulate_indicator_fallback_fear_greed(self):
        """Test fear-greed indicator fallback."""
        paths = simulate_indicator_fallback(
            last_value=50.0,
            indicator_type="fear_greed",
            n_days=30,
            n_paths=100,
        )
        
        assert paths.shape == (100, 31), f"Expected (100, 31), got {paths.shape}"
        assert np.all(paths[:, 0] == 50.0), "All paths should start at last_value"
    
    def test_simulate_indicator_fallback_crowding(self):
        """Test crowding indicator fallback."""
        paths = simulate_indicator_fallback(
            last_value=60.0,
            indicator_type="crowding",
            n_days=30,
            n_paths=100,
        )
        
        assert paths.shape == (100, 31), f"Expected (100, 31), got {paths.shape}"
    
    def test_simulate_indicator_fallback_percentile(self):
        """Test percentile indicator fallback."""
        paths = simulate_indicator_fallback(
            last_value=45.0,
            indicator_type="percentile",
            n_days=30,
            n_paths=100,
        )
        
        assert paths.shape == (100, 31), f"Expected (100, 31), got {paths.shape}"


class TestStatisticalValidation:
    """Test statistical validation methods."""
    
    def test_gbm_check_mean_without_paths_raises(self):
        """Test check_mean raises error if no paths available."""
        simulator = GBMSimulator(
            S0=100.0,
            mu=0.08,
            sigma=0.20,
            T=1.0,
            N=252,
            n_paths=100,
        )
        
        with pytest.raises(ValueError, match="No paths available"):
            simulator.check_mean()
    
    def test_gbm_check_variance_without_paths_raises(self):
        """Test check_variance raises error if no paths available."""
        simulator = GBMSimulator(
            S0=100.0,
            mu=0.08,
            sigma=0.20,
            T=1.0,
            N=252,
            n_paths=100,
        )
        
        with pytest.raises(ValueError, match="No paths available"):
            simulator.check_variance()
    
    def test_ou_check_mean_without_paths_raises(self):
        """Test check_mean raises error if no paths available."""
        simulator = OUSimulator(
            X0=50.0,
            theta=50.0,
            kappa=0.15,
            sigma=10.0,
            T=1.0,
            N=252,
            n_paths=100,
        )
        
        with pytest.raises(ValueError, match="No paths available"):
            simulator.check_mean()
    
    def test_ou_check_variance_without_paths_raises(self):
        """Test check_variance raises error if no paths available."""
        simulator = OUSimulator(
            X0=50.0,
            theta=50.0,
            kappa=0.15,
            sigma=10.0,
            T=1.0,
            N=252,
            n_paths=100,
        )
        
        with pytest.raises(ValueError, match="No paths available"):
            simulator.check_variance()
    
    def test_ou_check_mean_reversion_without_paths_raises(self):
        """Test check_mean_reversion raises error if no paths available."""
        simulator = OUSimulator(
            X0=50.0,
            theta=50.0,
            kappa=0.15,
            sigma=10.0,
            T=1.0,
            N=252,
            n_paths=100,
        )
        
        with pytest.raises(ValueError, match="No paths available"):
            simulator.check_mean_reversion()


class TestReproducibility:
    """Test reproducibility with seed."""
    
    def test_gbm_reproducible_with_seed(self):
        """Test GBM produces same results with same seed."""
        simulator = GBMSimulator(
            S0=100.0,
            mu=0.08,
            sigma=0.20,
            T=1.0,
            N=252,
            n_paths=100,
        )
        
        paths1 = simulator.simulate(seed=42)
        paths2 = simulator.simulate(seed=42)
        
        assert np.allclose(paths1, paths2), "Same seed should produce identical paths"
    
    def test_ou_reproducible_with_seed(self):
        """Test O-U produces same results with same seed."""
        simulator = OUSimulator(
            X0=50.0,
            theta=50.0,
            kappa=0.15,
            sigma=10.0,
            T=1.0,
            N=252,
            n_paths=100,
        )
        
        paths1 = simulator.simulate(seed=42)
        paths2 = simulator.simulate(seed=42)
        
        assert np.allclose(paths1, paths2), "Same seed should produce identical paths"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
