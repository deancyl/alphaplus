"""
Unit tests for correlation calculation service.

Tests:
- Pearson correlation calculation
- Log returns computation
- O-U fallback when data insufficient
- Cache integration
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.correlation import (
    calculate_log_returns,
    compute_pearson_matrix,
    generate_ou_correlation_fallback,
    correlation_matrix_to_list,
    calculate_pearson_matrix,
    fetch_nav_data,
    MIN_DATA_POINTS,
)


class TestCalculateLogReturns:
    """Tests for log returns calculation."""
    
    def test_basic_log_returns(self):
        """Test basic log returns calculation."""
        nav_series = pd.Series([100.0, 101.0, 102.5, 101.5, 103.0])
        log_returns = calculate_log_returns(nav_series)
        
        assert len(log_returns) == 4
        assert not log_returns.isna().any()
        expected = np.log(101.0 / 100.0)
        assert abs(log_returns.iloc[0] - expected) < 1e-6
    
    def test_zero_nav_filtered(self):
        """Test that zero NAV values are filtered out."""
        nav_series = pd.Series([100.0, 0.0, 101.0, 102.0])
        log_returns = calculate_log_returns(nav_series)
        
        assert len(log_returns) == 2
        assert not log_returns.isna().any()
    
    def test_insufficient_data(self):
        """Test with insufficient NAV data."""
        nav_series = pd.Series([100.0])
        log_returns = calculate_log_returns(nav_series)
        
        assert len(log_returns) == 0
    
    def test_empty_series(self):
        """Test with empty NAV series."""
        nav_series = pd.Series([], dtype=float)
        log_returns = calculate_log_returns(nav_series)
        
        assert len(log_returns) == 0


class TestComputePearsonMatrix:
    """Tests for Pearson matrix computation."""
    
    def test_perfect_correlation(self):
        """Test perfect positive correlation."""
        dates = pd.date_range("2024-01-01", periods=100)
        returns = np.random.randn(100) * 0.02
        
        df = pd.DataFrame({
            "FUND_A": returns,
            "FUND_B": returns * 2,
        }, index=dates)
        
        matrix = compute_pearson_matrix(df)
        
        assert "FUND_A" in matrix
        assert "FUND_B" in matrix
        assert matrix["FUND_A"]["FUND_B"] > 0.99
        assert matrix["FUND_A"]["FUND_A"] == 1.0
        assert matrix["FUND_B"]["FUND_B"] == 1.0
    
    def test_negative_correlation(self):
        """Test negative correlation."""
        dates = pd.date_range("2024-01-01", periods=100)
        returns = np.random.randn(100) * 0.02
        
        df = pd.DataFrame({
            "FUND_A": returns,
            "FUND_B": -returns,
        }, index=dates)
        
        matrix = compute_pearson_matrix(df)
        
        assert matrix["FUND_A"]["FUND_B"] < -0.99
    
    def test_independent_funds(self):
        """Test uncorrelated funds."""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=1000)
        
        df = pd.DataFrame({
            "FUND_A": np.random.randn(1000) * 0.02,
            "FUND_B": np.random.randn(1000) * 0.02,
        }, index=dates)
        
        matrix = compute_pearson_matrix(df)
        
        assert abs(matrix["FUND_A"]["FUND_B"]) < 0.2
    
    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        df = pd.DataFrame()
        matrix = compute_pearson_matrix(df)
        
        assert matrix == {}
    
    def test_single_fund(self):
        """Test with single fund."""
        dates = pd.date_range("2024-01-01", periods=100)
        df = pd.DataFrame({
            "FUND_A": np.random.randn(100) * 0.02,
        }, index=dates)
        
        matrix = compute_pearson_matrix(df)
        
        assert matrix == {}


class TestOUCorrelationFallback:
    """Tests for O-U correlation fallback."""
    
    def test_symmetric_matrix(self):
        """Test that O-U fallback produces symmetric matrix."""
        fund_codes = ["FUND_A", "FUND_B", "FUND_C"]
        matrix = generate_ou_correlation_fallback(fund_codes, seed=42)
        
        assert matrix["FUND_A"]["FUND_B"] == matrix["FUND_B"]["FUND_A"]
        assert matrix["FUND_A"]["FUND_C"] == matrix["FUND_C"]["FUND_A"]
    
    def test_diagonal_is_one(self):
        """Test that diagonal elements are 1.0."""
        fund_codes = ["FUND_A", "FUND_B", "FUND_C"]
        matrix = generate_ou_correlation_fallback(fund_codes, seed=42)
        
        for fund in fund_codes:
            assert matrix[fund][fund] == 1.0
    
    def test_correlation_bounds(self):
        """Test that correlations are within valid bounds."""
        fund_codes = ["FUND_A", "FUND_B", "FUND_C", "FUND_D", "FUND_E"]
        matrix = generate_ou_correlation_fallback(fund_codes, seed=42)
        
        for fund_i in fund_codes:
            for fund_j in fund_codes:
                corr = matrix[fund_i][fund_j]
                assert -1.0 <= corr <= 1.0, f"Correlation {fund_i}-{fund_j} = {corr} out of bounds"
    
    def test_empty_fund_list(self):
        """Test with empty fund list."""
        matrix = generate_ou_correlation_fallback([])
        assert matrix == {}
    
    def test_reproducible_with_seed(self):
        """Test that same seed produces same result."""
        fund_codes = ["FUND_A", "FUND_B", "FUND_C"]
        matrix1 = generate_ou_correlation_fallback(fund_codes, seed=123)
        matrix2 = generate_ou_correlation_fallback(fund_codes, seed=123)
        
        assert matrix1 == matrix2


class TestCorrelationMatrixToList:
    """Tests for matrix to list conversion."""
    
    def test_basic_conversion(self):
        """Test basic conversion."""
        matrix = {
            "A": {"A": 1.0, "B": 0.5, "C": 0.3},
            "B": {"A": 0.5, "B": 1.0, "C": 0.7},
            "C": {"A": 0.3, "B": 0.7, "C": 1.0},
        }
        fund_codes = ["A", "B", "C"]
        
        result = correlation_matrix_to_list(matrix, fund_codes)
        
        assert len(result) == 3
        assert result[0][0] == 1.0
        assert result[0][1] == 0.5
        assert result[1][2] == 0.7
    
    def test_preserves_order(self):
        """Test that order is preserved."""
        matrix = {
            "A": {"A": 1.0, "B": 0.5},
            "B": {"A": 0.5, "B": 1.0},
        }
        
        result1 = correlation_matrix_to_list(matrix, ["A", "B"])
        result2 = correlation_matrix_to_list(matrix, ["B", "A"])
        
        assert result1[0][0] == 1.0
        assert result2[0][0] == 1.0
        assert result1 == [[1.0, 0.5], [0.5, 1.0]]
        assert result2 == [[1.0, 0.5], [0.5, 1.0]]


class TestCalculatePearsonMatrix:
    """Tests for main correlation calculation function."""
    
    @pytest.mark.asyncio
    async def test_insufficient_data_uses_ou_fallback(self):
        """Test that O-U fallback is used when data is insufficient."""
        mock_db = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result
        
        fund_codes = ["FUND_A", "FUND_B"]
        matrix, is_real = await calculate_pearson_matrix(
            db=mock_db,
            fund_codes=fund_codes,
            use_cache=False,
        )
        
        assert is_real is False
        assert len(matrix) == 2
        assert matrix["FUND_A"]["FUND_A"] == 1.0
    
    @pytest.mark.asyncio
    async def test_max_funds_validation(self):
        """Test that more than 15 funds raises error."""
        mock_db = AsyncMock()
        fund_codes = [f"FUND_{i}" for i in range(16)]
        
        with pytest.raises(ValueError, match="Maximum 15 funds"):
            await calculate_pearson_matrix(
                db=mock_db,
                fund_codes=fund_codes,
                use_cache=False,
            )
    
    @pytest.mark.asyncio
    async def test_empty_fund_list(self):
        """Test with empty fund list."""
        mock_db = AsyncMock()
        
        matrix, is_real = await calculate_pearson_matrix(
            db=mock_db,
            fund_codes=[],
            use_cache=False,
        )
        
        assert matrix == {}
        assert is_real is True


class TestPerformance:
    """Performance tests for correlation calculation."""
    
    def test_pearson_matrix_performance(self):
        """Test that 15 funds, 252 days computes in <150ms."""
        import time
        
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=252)
        
        data = {}
        for i in range(15):
            data[f"FUND_{i}"] = np.random.randn(252) * 0.02
        
        df = pd.DataFrame(data, index=dates)
        
        start = time.perf_counter()
        for _ in range(10):
            matrix = compute_pearson_matrix(df)
        elapsed = (time.perf_counter() - start) / 10 * 1000
        
        assert elapsed < 150, f"Performance test failed: {elapsed:.2f}ms > 150ms"
        print(f"Performance: {elapsed:.2f}ms for 15 funds, 252 days")
    
    def test_log_returns_performance(self):
        """Test log returns calculation performance."""
        import time
        
        nav_series = pd.Series(np.random.uniform(1.0, 2.0, 10000))
        
        start = time.perf_counter()
        for _ in range(100):
            calculate_log_returns(nav_series)
        elapsed = (time.perf_counter() - start) / 100 * 1000
        
        assert elapsed < 5, f"Log returns too slow: {elapsed:.2f}ms"
        print(f"Log returns: {elapsed:.3f}ms for 10,000 points")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
