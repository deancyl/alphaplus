"""
Pearson Correlation Matrix Calculation Service.

Implements real-time correlation calculation using log returns from FundNavHistory.
Performance target: <150ms for 15 funds, 252 days of NAV.

Mathematical Framework:
-----------------------
Log Returns: r_t = log(nav_t / nav_{t-1})
Pearson Correlation: ρ = Cov(r_i, r_j) / (σ_i * σ_j)

Features:
- Real Pearson correlation using numpy/pandas
- 1-hour TTL cache via CorrelationCache
- O-U simulator fallback when NAV data insufficient
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from backend.models.fund import FundNavHistory
from backend.services.cache import correlation_cache
from backend.services.simulators import OUSimulator
from backend.utils.formatters import round4

logger = logging.getLogger(__name__)

# Minimum data points required for reliable correlation
MIN_DATA_POINTS = 30  # At least 30 trading days
DEFAULT_LOOKBACK_DAYS = 252  # 1 year of trading days


async def fetch_nav_data(
    db: AsyncSession,
    fund_codes: List[str],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch NAV history for multiple funds from database.
    
    Args:
        db: AsyncSession database connection
        fund_codes: List of fund codes to fetch
        start_date: Start date (YYYY-MM-DD), defaults to 252 trading days ago
        end_date: End date (YYYY-MM-DD), defaults to today
    
    Returns:
        DataFrame with columns: fund_code, nav_date, nav_value
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    if start_date is None:
        # Default to ~1 year of trading days (252 days ≈ 365 calendar days)
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    
    query = select(FundNavHistory).where(
        and_(
            FundNavHistory.fund_code.in_(fund_codes),
            FundNavHistory.nav_date >= start_date,
            FundNavHistory.nav_date <= end_date,
        )
    ).order_by(FundNavHistory.nav_date)
    
    result = await db.execute(query)
    rows = result.scalars().all()
    
    if not rows:
        return pd.DataFrame(columns=["fund_code", "nav_date", "nav_value"])
    
    # Convert to DataFrame
    data = [
        {"fund_code": row.fund_code, "nav_date": row.nav_date, "nav_value": row.nav_value}
        for row in rows
    ]
    df = pd.DataFrame(data)
    
    return df


def calculate_log_returns(nav_series: pd.Series) -> pd.Series:
    """
    Calculate log returns from NAV series.
    
    Formula: r_t = log(nav_t / nav_{t-1})
    
    Args:
        nav_series: Series of NAV values indexed by date
    
    Returns:
        Series of log returns
    """
    # Ensure positive NAV values
    nav_series = nav_series[nav_series > 0]
    
    if len(nav_series) < 2:
        return pd.Series(dtype=float)
    
    # Calculate log returns
    log_returns = np.log(nav_series / nav_series.shift(1))
    
    # Drop first NaN value
    log_returns = log_returns.dropna()
    
    return log_returns


def compute_pearson_matrix(log_returns_df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """
    Compute Pearson correlation matrix from log returns.
    
    Args:
        log_returns_df: DataFrame with fund codes as columns, log returns as values
    
    Returns:
        Dict mapping fund_code_i -> {fund_code_j: correlation}
    """
    if log_returns_df.empty or log_returns_df.shape[1] < 2:
        return {}
    
    # Compute correlation matrix using pandas
    corr_matrix = log_returns_df.corr(method='pearson')
    
    # Convert to nested dict format
    result = {}
    for fund_i in corr_matrix.index:
        result[fund_i] = {}
        for fund_j in corr_matrix.columns:
            corr_value = corr_matrix.loc[fund_i, fund_j]
            # Handle NaN (when one series has zero variance)
            if pd.isna(corr_value):
                result[fund_i][fund_j] = 0.0
            else:
                result[fund_i][fund_j] = round4(corr_value)
    
    return result


def generate_ou_correlation_fallback(
    fund_codes: List[str],
    seed: Optional[int] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Generate simulated correlation matrix using O-U process when data insufficient.
    
    This provides graceful degradation when real NAV data is unavailable.
    Uses realistic correlation structure based on fund type heuristics.
    
    Args:
        fund_codes: List of fund codes
        seed: Random seed for reproducibility
    
    Returns:
        Dict mapping fund_code_i -> {fund_code_j: correlation}
    """
    n = len(fund_codes)
    if n == 0:
        return {}
    
    if seed is not None:
        np.random.seed(seed)
    
    # Generate base correlation matrix using O-U process
    # Start with moderate correlation (0.5) and let O-U process create variation
    ou = OUSimulator(
        X0=0.5,  # Initial correlation
        theta=0.5,  # Mean correlation (funds tend to be moderately correlated)
        kappa=0.3,  # Moderate mean reversion
        sigma=0.2,  # Volatility of correlation
        T=1.0,
        N=n * n,  # Total elements needed
        n_paths=1,
    )
    
    simulated_result = ou.simulate(seed=seed)
    if simulated_result is None or len(simulated_result) == 0:
        logger.warning("O-U simulation returned empty result, using fallback correlation")
        result = {}
        for i, fund_i in enumerate(fund_codes):
            result[fund_i] = {}
            for j, fund_j in enumerate(fund_codes):
                if i == j:
                    result[fund_i][fund_j] = 1.0
                else:
                    result[fund_i][fund_j] = 0.5
        return result
    
    simulated_values = simulated_result[0]
    
    # Build symmetric correlation matrix
    result = {}
    idx = 0
    for i, fund_i in enumerate(fund_codes):
        result[fund_i] = {}
        for j, fund_j in enumerate(fund_codes):
            if i == j:
                # Diagonal: perfect self-correlation
                result[fund_i][fund_j] = 1.0
            elif j > i:
                # Upper triangle: generate from O-U
                raw_corr = simulated_values[idx] if idx < len(simulated_values) else 0.5
                # Bound correlation to [-1, 1]
                corr = round4(np.clip(raw_corr, -0.9, 0.95))
                result[fund_i][fund_j] = corr
                idx += 1
            else:
                # Lower triangle: symmetric
                result[fund_i][fund_j] = result[fund_j][fund_i]
    
    return result


async def calculate_pearson_matrix(
    db: AsyncSession,
    fund_codes: List[str],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    use_cache: bool = True,
) -> Tuple[Dict[str, Dict[str, float]], bool]:
    """
    Calculate Pearson correlation matrix for fund NAV returns.
    
    Main entry point for correlation calculation with caching and fallback.
    
    Args:
        db: AsyncSession database connection
        fund_codes: List of fund codes (max 15)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        use_cache: Whether to use 1-hour TTL cache
    
    Returns:
        Tuple of (correlation_matrix, is_real_data)
        - correlation_matrix: Dict[fund_code_i, Dict[fund_code_j, correlation]]
        - is_real_data: True if calculated from real NAV, False if O-U fallback
    """
    if not fund_codes:
        return {}, True
    
    if len(fund_codes) > 15:
        raise ValueError("Maximum 15 funds allowed for correlation calculation")
    
    # Check cache first
    if use_cache:
        cached = await correlation_cache.get(fund_codes)
        if cached is not None:
            logger.debug(f"Correlation cache hit for {len(fund_codes)} funds")
            return cached["matrix"], cached["is_real_data"]
    
    # Fetch NAV data
    nav_df = await fetch_nav_data(db, fund_codes, start_date, end_date)
    
    # Check if we have sufficient data
    data_coverage = {}
    for fund_code in fund_codes:
        fund_data = nav_df[nav_df["fund_code"] == fund_code]
        data_coverage[fund_code] = len(fund_data)
    
    min_coverage = min(data_coverage.values()) if data_coverage else 0
    
    # Determine if we have enough data for reliable correlation
    if min_coverage < MIN_DATA_POINTS:
        logger.warning(
            f"Insufficient NAV data for correlation: min_coverage={min_coverage}, "
            f"required={MIN_DATA_POINTS}. Using O-U fallback."
        )
        # Use O-U fallback
        matrix = generate_ou_correlation_fallback(fund_codes, seed=42)
        is_real_data = False
    else:
        # Pivot to wide format: dates as index, funds as columns
        nav_pivot = nav_df.pivot(index="nav_date", columns="fund_code", values="nav_value")
        
        # Calculate log returns for each fund
        log_returns_df = pd.DataFrame(index=nav_pivot.index)
        for fund_code in fund_codes:
            if fund_code in nav_pivot.columns:
                log_returns_df[fund_code] = calculate_log_returns(nav_pivot[fund_code])
        
        # Drop dates where any fund has missing data
        log_returns_df = log_returns_df.dropna()
        
        # Check if we still have enough overlapping data
        if len(log_returns_df) < MIN_DATA_POINTS:
            logger.warning(
                f"Insufficient overlapping data: {len(log_returns_df)} days, "
                f"required={MIN_DATA_POINTS}. Using O-U fallback."
            )
            matrix = generate_ou_correlation_fallback(fund_codes, seed=42)
            is_real_data = False
        else:
            # Compute real Pearson correlation
            matrix = compute_pearson_matrix(log_returns_df)
            is_real_data = True
            logger.info(
                f"Computed real Pearson correlation for {len(fund_codes)} funds, "
                f"{len(log_returns_df)} days of data"
            )
    
    # Cache the result
    if use_cache:
        await correlation_cache.set(
            fund_codes,
            {"matrix": matrix, "is_real_data": is_real_data}
        )
    
    return matrix, is_real_data


def correlation_matrix_to_list(
    matrix: Dict[str, Dict[str, float]],
    fund_codes: List[str],
) -> List[List[float]]:
    """
    Convert nested dict correlation matrix to 2D list format.
    
    Args:
        matrix: Dict[fund_code_i, Dict[fund_code_j, correlation]]
        fund_codes: Ordered list of fund codes
    
    Returns:
        2D list where result[i][j] = correlation(fund_i, fund_j)
    """
    n = len(fund_codes)
    result = [[0.0] * n for _ in range(n)]
    
    for i, fund_i in enumerate(fund_codes):
        for j, fund_j in enumerate(fund_codes):
            if fund_i in matrix and fund_j in matrix[fund_i]:
                result[i][j] = matrix[fund_i][fund_j]
            elif i == j:
                result[i][j] = 1.0
            else:
                result[i][j] = 0.0
    
    return result
