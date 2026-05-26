"""
Factor Exposure Analyzer - SLSQP Constrained Regression.

Implements Sharpe-style multi-factor analysis with 14 factors:
- 6 style factors: SIZE, VALUE, MOMENTUM, VOLATILITY, QUALITY, GROWTH
- 8 sector factors: 申万一级 (SW Level-1 sectors)

Mathematical Framework:
-----------------------
Objective: Minimize RSS (residual sum of squares)
    min Σ(R_fund - Σ(w_i * F_i))²
    
Subject to:
    1. Σ w_i = 1.0 (no leverage constraint)
    2. w_i ≥ 0.0 (no short selling constraint)
    
Where:
    R_fund: Fund return time series
    F_i: Factor return time series
    w_i: Factor exposure weight

Optimization Method: SLSQP (Sequential Least Squares Programming)
Performance Target: <200ms per analysis

Factor Returns Data Sources:
- Primary: Database (factor_returns table)
- Fallback: O-U simulated returns from historical data
"""
import numpy as np
from scipy.optimize import minimize
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import time

from backend.services.simulators import OUSimulator


# 14-factor model definition
STYLE_FACTORS = [
    "SIZE",       # 市值因子
    "VALUE",      # 价值因子
    "MOMENTUM",   # 动量因子
    "VOLATILITY", # 波动率因子
    "QUALITY",    # 质量因子
    "GROWTH",     # 成长因子
]

SECTOR_FACTORS = [
    "FINANCE",      # 金融
    "TECHNOLOGY",   # 科技
    "HEALTHCARE",   # 医疗
    "CONSUMER",     # 消费
    "ENERGY",       # 能源
    "MATERIALS",    # 材料
    "INDUSTRIAL",   # 工业
    "REALTY",       # 房地产
]

ALL_FACTORS = STYLE_FACTORS + SECTOR_FACTORS


class FactorExposureAnalyzer:
    """
    Factor Exposure Analyzer using SLSQP constrained regression.
    
    Implements Sharpe-style attribution with constraints:
    - sum(weights) = 1.0 (no leverage)
    - weights >= 0.0 (no short selling)
    
    Performance: <200ms per analysis
    """
    
    def __init__(self, n_factors: int = 14):
        """
        Initialize factor exposure analyzer.
        
        Args:
            n_factors: Number of factors (default 14 for 6 style + 8 sector)
        """
        self.n_factors = n_factors
        self.style_factors = STYLE_FACTORS
        self.sector_factors = SECTOR_FACTORS
        self.all_factors = ALL_FACTORS
        
        # Cache for factor returns
        self._factor_returns_cache: Optional[np.ndarray] = None
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl_seconds = 3600  # 1 hour cache
    
    def estimate_exposure(
        self,
        fund_returns: np.ndarray,
        factor_returns: np.ndarray,
    ) -> Tuple[np.ndarray, Dict]:
        """
        Estimate factor exposure using SLSQP optimization.
        
        Mathematical Model:
            min Σ(R_fund - Σ(w_i * F_i))²
            
        Subject to:
            Σ w_i = 1.0
            w_i ≥ 0.0
            
        Args:
            fund_returns: Fund return time series (T,) or (T, 1)
            factor_returns: Factor return matrix (T, n_factors)
        
        Returns:
            Tuple of (weights, metadata)
            weights: Factor exposure weights (n_factors,)
            metadata: Dict with optimization details
        """
        start_time = time.perf_counter()
        
        # Validate inputs
        fund_returns = np.asarray(fund_returns).flatten()
        factor_returns = np.asarray(factor_returns)
        
        if factor_returns.ndim == 1:
            factor_returns = factor_returns.reshape(-1, 1)
        
        n_factors = factor_returns.shape[1]
        T = len(fund_returns)
        
        if factor_returns.shape[0] != T:
            raise ValueError(
                f"Shape mismatch: fund_returns has {T} time points, "
                f"but factor_returns has {factor_returns.shape[0]}"
            )
        
        # Define objective function (RSS)
        def rss_objective(weights: np.ndarray) -> float:
            """Residual sum of squares."""
            estimated = np.dot(factor_returns, weights)
            residuals = fund_returns - estimated
            return float(np.sum(residuals ** 2))
        
        # Define constraints
        constraints = [
            {
                "type": "eq",
                "fun": lambda w: np.sum(w) - 1.0,
            }
        ]
        
        # Define bounds (no short selling)
        bounds = [(0.0, 1.0) for _ in range(n_factors)]
        
        # Initial guess (equal weights)
        initial_weights = np.ones(n_factors) / n_factors
        
        # Run SLSQP optimization
        solution = minimize(
            rss_objective,
            initial_weights,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={
                "maxiter": 1000,
                "ftol": 1e-9,
                "disp": False,
            }
        )
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        # Extract results
        if solution.success:
            weights = solution.x
        else:
            # Fallback to equal weights if optimization fails
            weights = initial_weights
        
        # Calculate R²
        estimated_returns = np.dot(factor_returns, weights)
        ss_res = np.sum((fund_returns - estimated_returns) ** 2)
        ss_tot = np.sum((fund_returns - np.mean(fund_returns)) ** 2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        
        # Build metadata
        metadata = {
            "optimization_success": solution.success,
            "message": solution.message if hasattr(solution, "message") else "",
            "iterations": solution.nit if hasattr(solution, "nit") else 0,
            "r_squared": float(r_squared),
            "rss": float(ss_res),
            "elapsed_ms": float(elapsed_ms),
            "n_time_points": T,
            "n_factors": n_factors,
        }
        
        return weights, metadata
    
    def get_factor_returns(
        self,
        start_date: str,
        end_date: str,
        use_cache: bool = True,
    ) -> np.ndarray:
        """
        Get factor returns for the specified date range.
        
        Tries database first, falls back to O-U simulation.
        
        Args:
            start_date: Start date "YYYY-MM-DD"
            end_date: End date "YYYY-MM-DD"
            use_cache: Whether to use cached factor returns (default True)
        
        Returns:
            Factor returns matrix (T, 14) where T is number of trading days
        """
        # Check cache
        if use_cache and self._factor_returns_cache is not None and self._cache_timestamp is not None:
            cache_age = time.time() - self._cache_timestamp
            if cache_age < self._cache_ttl_seconds:
                return self._factor_returns_cache
        
        # Try to load from database
        try:
            factor_returns = self._load_factor_returns_from_db(start_date, end_date)
            if factor_returns is not None:
                # Update cache
                self._factor_returns_cache = factor_returns
                self._cache_timestamp = time.time()
                return factor_returns
        except Exception as e:
            print(f"Warning: Failed to load factor returns from database: {e}")
        
        # Fallback: Simulate using O-U process
        print("Info: Using O-U simulated factor returns as fallback")
        factor_returns = self._simulate_factor_returns(start_date, end_date)
        
        # Update cache
        self._factor_returns_cache = factor_returns
        self._cache_timestamp = time.time()
        
        return factor_returns
    
    def _load_factor_returns_from_db(
        self,
        start_date: str,
        end_date: str,
    ) -> Optional[np.ndarray]:
        """
        Load factor returns from database.
        
        Args:
            start_date: Start date "YYYY-MM-DD"
            end_date: End date "YYYY-MM-DD"
        
        Returns:
            Factor returns matrix (T, 14) or None if unavailable
        """
        # TODO: Implement database query when factor_returns table is available
        # For now, return None to trigger fallback
        return None
    
    def _simulate_factor_returns(
        self,
        start_date: str,
        end_date: str,
    ) -> np.ndarray:
        """
        Simulate factor returns using O-U process.
        
        Uses realistic parameters for each factor type:
        - Style factors: Lower volatility, moderate mean reversion
        - Sector factors: Higher volatility, slower mean reversion
        
        Args:
            start_date: Start date "YYYY-MM-DD"
            end_date: End date "YYYY-MM-DD"
        
        Returns:
            Simulated factor returns matrix (T, 14)
        """
        # Calculate number of trading days
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        days = (end - start).days
        n_trading_days = max(int(days * (252 / 365)), 20)  # At least 20 days
        
        # Factor return parameters (mean, kappa, sigma)
        # Style factors: More stable, lower volatility
        style_params = {
            "SIZE":       {"theta": 0.0005, "kappa": 2.0, "sigma": 0.01},
            "VALUE":      {"theta": 0.0003, "kappa": 1.5, "sigma": 0.012},
            "MOMENTUM":   {"theta": 0.0006, "kappa": 3.0, "sigma": 0.015},
            "VOLATILITY": {"theta": 0.0002, "kappa": 2.5, "sigma": 0.008},
            "QUALITY":    {"theta": 0.0004, "kappa": 1.0, "sigma": 0.009},
            "GROWTH":     {"theta": 0.0007, "kappa": 1.8, "sigma": 0.013},
        }
        
        # Sector factors: Higher volatility, sector-specific means
        sector_params = {
            "FINANCE":    {"theta": 0.0004, "kappa": 1.2, "sigma": 0.018},
            "TECHNOLOGY": {"theta": 0.0008, "kappa": 1.5, "sigma": 0.022},
            "HEALTHCARE": {"theta": 0.0006, "kappa": 1.0, "sigma": 0.016},
            "CONSUMER":   {"theta": 0.0005, "kappa": 1.3, "sigma": 0.014},
            "ENERGY":     {"theta": 0.0003, "kappa": 2.0, "sigma": 0.025},
            "MATERIALS":  {"theta": 0.0004, "kappa": 1.8, "sigma": 0.020},
            "INDUSTRIAL": {"theta": 0.0005, "kappa": 1.4, "sigma": 0.015},
            "REALTY":     {"theta": 0.0002, "kappa": 1.6, "sigma": 0.019},
        }
        
        all_params = {**style_params, **sector_params}
        
        # Simulate each factor independently
        factor_returns = np.zeros((n_trading_days, 14))
        
        for i, factor_name in enumerate(self.all_factors):
            params = all_params[factor_name]
            
            # Use O-U simulator for mean-reverting returns
            simulator = OUSimulator(
                X0=params["theta"],
                theta=params["theta"],
                kappa=params["kappa"],
                sigma=params["sigma"],
                T=n_trading_days / 252,
                N=n_trading_days,
                n_paths=1,
            )
            
            # Generate one path
            path = simulator.simulate(seed=42 + i)
            
            # Convert to returns (first difference)
            returns = np.diff(path[0])
            factor_returns[:, i] = returns
        
        return factor_returns
    
    def format_exposure_result(
        self,
        weights: np.ndarray,
        metadata: Dict,
    ) -> Dict:
        """
        Format factor exposure result as API response.
        
        Args:
            weights: Factor exposure weights (14,)
            metadata: Optimization metadata
        
        Returns:
            Dict with factor exposures and metadata
        """
        # Build factor exposures list
        factor_exposures = []
        
        for i, factor_name in enumerate(self.all_factors):
            factor_exposures.append({
                "factor_name": factor_name,
                "factor_type": "style" if i < 6 else "sector",
                "weight": float(weights[i]),
            })
        
        # Sort by weight descending
        factor_exposures.sort(key=lambda x: x["weight"], reverse=True)
        
        return {
            "factor_exposures": factor_exposures,
            "style_factors": [
                {"name": fn, "weight": float(weights[i])}
                for i, fn in enumerate(self.style_factors)
            ],
            "sector_factors": [
                {"name": fn, "weight": float(weights[i])}
                for i, fn in enumerate(self.sector_factors, start=6)
            ],
            "metadata": metadata,
        }


def analyze_factor_exposure(
    fund_returns: np.ndarray,
    start_date: str,
    end_date: str,
    factor_returns: Optional[np.ndarray] = None,
) -> Dict:
    """
    Convenience function for factor exposure analysis.
    
    Args:
        fund_returns: Fund return time series
        start_date: Start date "YYYY-MM-DD"
        end_date: End date "YYYY-MM-DD"
        factor_returns: Optional pre-loaded factor returns (T, 14)
    
    Returns:
        Dict with factor exposures and metadata
    """
    analyzer = FactorExposureAnalyzer()
    
    # Get factor returns if not provided
    if factor_returns is None:
        factor_returns = analyzer.get_factor_returns(start_date, end_date)
    
    # Estimate exposure
    weights, metadata = analyzer.estimate_exposure(fund_returns, factor_returns)
    
    # Format result
    return analyzer.format_exposure_result(weights, metadata)
