"""
Dividend-Adjusted NAV Calculation Service.
Calculates 复权净值 (cumulative NAV) for funds considering dividend distributions.

Formula:
    adjusted_nav[t] = raw_nav[t] * cumulative_adjustment_factor[t]
    cumulative_adjustment_factor[t] = ∏(1 + dividend[i] / nav_before_dividend[i])
    
    where the product is over all dividends before time t.

This is needed for accurate long-term performance comparison across funds 
with different dividend policies.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.fund import FundNavHistory
from backend.services.backtest import (
    BacktestResult,
    BacktestStatistics,
    DailyReturn,
    BacktestError,
    calculate_statistics,
)
from backend.utils.formatters import round2, round4

logger = logging.getLogger(__name__)


@dataclass
class DividendRecord:
    """
    Dividend distribution record.
    
    Attributes:
        date: Dividend distribution date (YYYY-MM-DD)
        dividend_per_unit: Dividend amount per unit (单位分红金额)
        nav_before_dividend: NAV before dividend distribution (分红前单位净值)
    """
    date: str  # YYYY-MM-DD
    dividend_per_unit: float  # 分红金额 per unit
    nav_before_dividend: float  # 分红前净值


@dataclass
class AdjustedNavResult:
    """
    Result of adjusted NAV calculation.
    
    Attributes:
        adjusted_nav_series: DataFrame with adjusted NAV values
        cumulative_factors: Series of cumulative adjustment factors
        dividend_events: List of dividend records used in calculation
    """
    adjusted_nav_series: pd.DataFrame
    cumulative_factors: pd.Series
    dividend_events: List[DividendRecord]


def calculate_adjusted_nav(
    nav_series: pd.DataFrame,
    dividend_records: List[DividendRecord]
) -> AdjustedNavResult:
    """
    Calculate dividend-adjusted NAV (复权净值) from raw NAV series.
    
    Args:
        nav_series: DataFrame with columns [date, nav] - raw NAV history
        dividend_records: List of DividendRecord objects representing dividend distributions
        
    Returns:
        AdjustedNavResult with adjusted NAV series, cumulative factors, and dividend events
        
    Algorithm:
        1. For each dividend, calculate adjustment factor: factor = (1 + dividend / nav_before)
        2. Cumulative factor at time t = product of all factors for dividends before t
        3. Adjusted NAV = raw NAV * cumulative factor
        
    Edge Cases:
        - No dividend records: returns original NAV series unchanged
        - Missing NAV before dividend: uses previous day's NAV (or initial NAV for first dividend)
        - NAV series empty: returns empty result
        
    Example:
        >>> nav_df = pd.DataFrame({
        ...     "date": ["2024-01-01", "2024-01-10", "2024-01-20"],
        ...     "nav": [1.00, 1.10, 1.15]
        ... })
        >>> dividends = [
        ...     DividendRecord("2024-01-10", 0.05, 1.10),
        ...     DividendRecord("2024-01-20", 0.03, 1.15)
        ... ]
        >>> result = calculate_adjusted_nav(nav_df, dividends)
        >>> # Day 10 factor: 1 + 0.05/1.10 = 1.0455
        >>> # Day 20 factor: 1.0455 * (1 + 0.03/1.15) = 1.0714
        >>> # adjusted_nav[Day 20] = 1.15 * 1.0714 = 1.232
        
    Unit Test Examples (in comments):
        # Test 1: No dividends - should return unchanged NAV
        # nav_df = pd.DataFrame({"date": ["2024-01-01"], "nav": [1.0]})
        # result = calculate_adjusted_nav(nav_df, [])
        # assert result.adjusted_nav_series["nav"].iloc[0] == 1.0
        # assert result.cumulative_factors.iloc[0] == 1.0
        
        # Test 2: Single dividend
        # nav_df = pd.DataFrame({"date": ["2024-01-01", "2024-01-10"], "nav": [1.0, 1.05]})
        # dividends = [DividendRecord("2024-01-10", 0.05, 1.05)]
        # result = calculate_adjusted_nav(nav_df, dividends)
        # expected_factor = 1 + 0.05 / 1.05 = 1.0476
        # assert abs(result.cumulative_factors.iloc[-1] - 1.0476) < 0.001
        
        # Test 3: Multiple dividends with cumulative effect
        # ... see Example above
        
        # Test 4: Missing NAV before dividend (fallback to previous)
        # nav_df = pd.DataFrame({"date": ["2024-01-01", "2024-01-10"], "nav": [1.0, 1.05]})
        # dividends = [DividendRecord("2024-01-05", 0.02, None)]  # Missing nav_before
        # result = calculate_adjusted_nav(nav_df, dividends)
        # # Should use nav=1.0 (previous day's NAV)
        # expected_factor = 1 + 0.02 / 1.0 = 1.02
    """
    if nav_series.empty:
        logger.warning("Empty NAV series provided")
        return AdjustedNavResult(
            adjusted_nav_series=pd.DataFrame({"date": [], "nav": [], "adjusted_nav": []}),
            cumulative_factors=pd.Series([], dtype=float),
            dividend_events=[]
        )
    
    if not dividend_records:
        logger.info("No dividend records, returning original NAV series")
        nav_series["adjusted_nav"] = nav_series["nav"]
        nav_series["cumulative_factor"] = 1.0
        return AdjustedNavResult(
            adjusted_nav_series=nav_series,
            cumulative_factors=pd.Series([1.0] * len(nav_series), index=nav_series["date"]),
            dividend_events=[]
        )
    
    # Ensure dates are datetime for comparison
    nav_series["date"] = pd.to_datetime(nav_series["date"])
    nav_series = nav_series.sort_values("date").reset_index(drop=True)
    
    # Convert dividend records to DataFrame for easier processing
    dividend_df = pd.DataFrame([
        {
            "date": pd.to_datetime(d.date),
            "dividend": d.dividend_per_unit,
            "nav_before": d.nav_before_dividend
        }
        for d in dividend_records
    ])
    dividend_df = dividend_df.sort_values("date").reset_index(drop=True)
    
    # Initialize cumulative factor series
    cumulative_factors = pd.Series(1.0, index=nav_series["date"])
    
    # Calculate adjustment factors for each dividend
    for idx, div_row in dividend_df.iterrows():
        div_date = div_row["date"]
        div_amount = div_row["dividend"]
        nav_before = div_row["nav_before"]
        
        # Handle missing NAV before dividend
        if nav_before is None or nav_before == 0:
            # Find the closest NAV before this dividend date
            nav_before_div = nav_series[nav_series["date"] < div_date]
            if nav_before_div.empty:
                # Use initial NAV if no prior NAV exists (first dividend case)
                nav_before = nav_series.iloc[0]["nav"] if len(nav_series) > 0 else 1.0
                logger.warning(
                    f"Dividend at {div_date}: Using initial NAV {nav_before} "
                    f"as nav_before_dividend (no prior NAV found)"
                )
            else:
                nav_before = nav_before_div.iloc[-1]["nav"]
                logger.warning(
                    f"Dividend at {div_date}: Using previous day NAV {nav_before} "
                    f"as nav_before_dividend (original value missing)"
                )
        
        # Calculate adjustment factor for this dividend
        adjustment_factor = 1.0 + div_amount / nav_before
        
        # Apply factor to all dates after this dividend
        dates_after = nav_series["date"] >= div_date
        cumulative_factors.loc[dates_after] *= adjustment_factor
        
        logger.debug(
            f"Dividend at {div_date}: amount={div_amount}, nav_before={nav_before}, "
            f"factor={adjustment_factor:.6f}"
        )
    
    # Calculate adjusted NAV
    nav_series["cumulative_factor"] = cumulative_factors.values
    nav_series["adjusted_nav"] = nav_series["nav"] * nav_series["cumulative_factor"]
    
    return AdjustedNavResult(
        adjusted_nav_series=nav_series,
        cumulative_factors=cumulative_factors,
        dividend_events=dividend_records
    )


async def get_fund_dividend_history(
    fund_code: str,
    start_date: str,
    end_date: str,
    db: AsyncSession
) -> List[DividendRecord]:
    """
    Fetch dividend distribution records for a fund from database.
    
    Args:
        fund_code: Fund code (e.g., "000001")
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        db: Async database session
        
    Returns:
        List of DividendRecord objects representing dividend distributions
        
    Note:
        This function queries FundNavHistory table and identifies dividend events
        by detecting NAV drops (nav_after = nav_before - dividend).
        
        Real dividend data may come from:
        - A dedicated fund_dividend_history table (if exists)
        - AkShare fund_dividend_fund_info API
        
    Example:
        >>> dividends = await get_fund_dividend_history("000001", "2024-01-01", "2024-12-31", db)
        >>> for div in dividends:
        ...     print(f"{div.date}: ¥{div.dividend_per_unit} per unit")
    """
    # Query NAV history for the fund
    result = await db.execute(
        select(FundNavHistory)
        .where(
            and_(
                FundNavHistory.fund_code == fund_code,
                FundNavHistory.nav_date >= start_date,
                FundNavHistory.nav_date <= end_date
            )
        )
        .order_by(FundNavHistory.nav_date)
    )
    nav_records = result.scalars().all()
    
    if not nav_records:
        logger.info(f"No NAV history for fund {fund_code} in period {start_date} to {end_date}")
        return []
    
    # Detect dividend events from NAV history
    # Dividend causes NAV to drop: nav_after = nav_before - dividend
    # daily_return should reflect this drop
    
    dividend_records = []
    for i, record in enumerate(nav_records):
        if i == 0:
            continue
        
        prev_record = nav_records[i - 1]
        
        # Check for significant NAV drop (potential dividend)
        # daily_return should be large negative (around -dividend/nav_before)
        if record.daily_return and record.daily_return < -2.0:
            # Calculate dividend amount from NAV drop
            nav_before = prev_record.nav_value
            nav_after = record.nav_value
            
            # Dividend = nav_before - nav_after (approximately)
            # More accurate: dividend = nav_before * (-daily_return/100) approximately
            dividend_amount = nav_before - nav_after
            
            # Sanity check: dividend should be positive and reasonable (< nav_before)
            if dividend_amount > 0 and dividend_amount < nav_before:
                rounded_dividend = round4(dividend_amount)
                rounded_nav = round4(nav_before)
                if rounded_dividend is not None and rounded_nav is not None:
                    dividend_records.append(
                        DividendRecord(
                            date=record.nav_date,
                            dividend_per_unit=rounded_dividend,
                            nav_before_dividend=rounded_nav
                        )
                    )
                logger.info(
                    f"Detected dividend for fund {fund_code} at {record.nav_date}: "
                    f"¥{dividend_amount:.4f} per unit (NAV before: {nav_before:.4f})"
                )
    
    # Note: In production, you would query a dedicated dividend table
    # or use AkShare API: fund_dividend_fund_info(fund=fund_code)
    
    return dividend_records


async def get_fund_nav_history_adjusted(
    fund_code: str,
    start_date: str,
    end_date: str,
    db: AsyncSession,
    use_adjusted: bool = True
) -> pd.DataFrame:
    """
    Fetch NAV history for a fund with optional dividend adjustment.
    
    Args:
        fund_code: Fund code (e.g., "000001")
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        db: Async database session
        use_adjusted: If True, return dividend-adjusted NAV (复权净值)
        
    Returns:
        DataFrame with columns: date, nav, adjusted_nav (if use_adjusted=True), daily_return
        
    Raises:
        BacktestError: If no NAV data available
    """
    # Fetch raw NAV history
    result = await db.execute(
        select(FundNavHistory)
        .where(
            and_(
                FundNavHistory.fund_code == fund_code,
                FundNavHistory.nav_date >= start_date,
                FundNavHistory.nav_date <= end_date
            )
        )
        .order_by(FundNavHistory.nav_date)
    )
    nav_records = result.scalars().all()
    
    if not nav_records:
        raise BacktestError(
            f"No NAV history found for fund {fund_code} "
            f"in period {start_date} to {end_date}"
        )
    
    # Convert to DataFrame
    df = pd.DataFrame([
        {
            "date": r.nav_date,
            "nav": r.nav_value,
            "daily_return": r.daily_return if r.daily_return else 0.0
        }
        for r in nav_records
    ])
    
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    
    if use_adjusted:
        # Fetch dividend records
        dividend_records = await get_fund_dividend_history(
            fund_code, start_date, end_date, db
        )
        
        # Calculate adjusted NAV
        adjusted_result = calculate_adjusted_nav(df, dividend_records)
        
        # Return adjusted NAV series
        adjusted_df = adjusted_result.adjusted_nav_series
        adjusted_df["daily_return"] = df["daily_return"]
        
        # Recalculate daily returns based on adjusted NAV for consistency
        if len(adjusted_df) > 1:
            adjusted_df["daily_return_adjusted"] = (
                adjusted_df["adjusted_nav"].pct_change() * 100
            ).fillna(0.0)
        
        return adjusted_df
    
    return df


async def run_backtest_adjusted(
    fund_allocations: List[Dict[str, float]],
    start_date: str,
    end_date: str,
    benchmark: str,
    db: AsyncSession,
    use_adjusted_nav: bool = True
) -> BacktestResult:
    """
    Run FOF backtest using dividend-adjusted NAV (复权净值).
    
    Args:
        fund_allocations: List of fund allocations with fund_code and weight
            [{"fund_code": "000001", "weight": 0.3}, ...]
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        benchmark: Benchmark index code (e.g., "000300" for 沪深300)
        db: Async database session
        use_adjusted_nav: If True, use dividend-adjusted NAV for more accurate
            long-term performance comparison
            
    Returns:
        BacktestResult with portfolio returns, benchmark returns, and statistics
        
    Note:
        Using adjusted NAV is essential for comparing funds with different
        dividend policies over long periods. Without adjustment, funds that
        distribute dividends appear to have lower NAV growth even though
        total returns may be identical.
        
    Example:
        >>> allocations = [
        ...     {"fund_code": "000001", "weight": 0.4},
        ...     {"fund_code": "000002", "weight": 0.6}
        ... ]
        >>> result = await run_backtest_adjusted(
        ...     allocations, "2023-01-01", "2023-12-31",
        ...     "000300", db, use_adjusted_nav=True
        ... )
        >>> print(f"Total return: {result.statistics.total_return:.2f}%")
    """
    logger.info(
        f"Running adjusted backtest for {len(fund_allocations)} funds "
        f"from {start_date} to {end_date} (use_adjusted={use_adjusted_nav})"
    )
    
    # Validate inputs
    if not fund_allocations:
        raise BacktestError("fund_allocations cannot be empty")
    
    # Normalize weights
    total_weight = sum(f["weight"] for f in fund_allocations)
    if abs(total_weight - 1.0) > 0.01:
        logger.warning(f"Weights sum to {total_weight}, normalizing to 1.0")
        fund_allocations = [
            {"fund_code": f["fund_code"], "weight": f["weight"] / total_weight}
            for f in fund_allocations
        ]
    
    # Fetch NAV history for all funds (adjusted or raw)
    fund_navs = {}
    all_dates = None
    
    for allocation in fund_allocations:
        fund_code = str(allocation["fund_code"])
        weight = float(allocation["weight"])
        
        try:
            nav_df = await get_fund_nav_history_adjusted(
                fund_code, start_date, end_date, db,
                use_adjusted=use_adjusted_nav
            )
            
            # Use adjusted_nav column if available, else use nav
            nav_column = "adjusted_nav" if use_adjusted_nav and "adjusted_nav" in nav_df.columns else "nav"
            
            fund_navs[fund_code] = {
                "weight": weight,
                "nav_df": nav_df,
                "nav_column": nav_column
            }
            
            # Track common dates
            if all_dates is None:
                all_dates = set(nav_df["date"])
            else:
                all_dates = all_dates.intersection(set(nav_df["date"]))
                
        except BacktestError as e:
            logger.warning(f"Skipping fund {fund_code}: {e}")
            continue
    
    if not fund_navs:
        raise BacktestError("No valid fund NAV data available for the specified period")
    
    # Find common date range
    if all_dates:
        common_dates = sorted(list(all_dates))
        if len(common_dates) < 2:
            raise BacktestError("Insufficient overlapping dates across funds")
    else:
        raise BacktestError("No common dates found across funds")
    
    # Build portfolio NAV using adjusted NAV
    portfolio_nav = []
    for date in common_dates:
        total_nav = 0.0
        for fund_code, data in fund_navs.items():
            weight = data["weight"]
            nav_df = data["nav_df"]
            nav_column = data["nav_column"]
            
            row = nav_df[nav_df["date"] == date]
            if not row.empty:
                total_nav += weight * row.iloc[0][nav_column]
        
        portfolio_nav.append({
            "date": date,
            "nav": total_nav
        })
    
    portfolio_df = pd.DataFrame(portfolio_nav)
    
    # Calculate portfolio daily returns
    if len(portfolio_df) > 1:
        portfolio_df["daily_return"] = portfolio_df["nav"].pct_change() * 100
        portfolio_df["daily_return"] = portfolio_df["daily_return"].fillna(0.0)
    else:
        portfolio_df["daily_return"] = 0.0
    
    # Calculate portfolio statistics
    portfolio_stats = calculate_statistics(
        portfolio_df["nav"],
        portfolio_df["daily_return"]
    )
    
    # Prepare portfolio returns
    portfolio_returns = [
        DailyReturn(
            date=str(row["date"])[:10] if len(str(row["date"])) > 10 else str(row["date"]),
            return_pct=round4(float(row["daily_return"])) or 0.0,
            nav=round4(float(row["nav"])) or 0.0
        )
        for _, row in portfolio_df.iterrows()
    ]
    
    # Fetch benchmark NAV history (using existing function from backtest.py)
    from backend.services.backtest import get_index_nav_history
    
    benchmark_returns = None
    try:
        benchmark_df = await get_index_nav_history(benchmark, start_date, end_date, db)
        
        if not benchmark_df.empty and len(benchmark_df) > 1:
            benchmark_df = benchmark_df[benchmark_df["date"].isin(common_dates)]
            
            benchmark_returns = [
                DailyReturn(
                    date=str(row["date"])[:10] if len(str(row["date"])) > 10 else str(row["date"]),
                    return_pct=round4(float(row["daily_return"])) or 0.0,
                    nav=round4(float(row["nav"])) or 0.0
                )
                for _, row in benchmark_df.iterrows()
            ]
    except Exception as e:
        logger.warning(f"Failed to fetch benchmark data: {e}")
    
    # Calculate individual fund performance
    fund_performance = []
    for fund_code, data in fund_navs.items():
        nav_df = data["nav_df"]
        nav_column = data["nav_column"]
        weight = data["weight"]
        
        if len(nav_df) > 1:
            fund_total_return = (
                (nav_df.iloc[-1][nav_column] / nav_df.iloc[0][nav_column]) - 1
            ) * 100
            fund_performance.append({
                "fund_code": fund_code,
                "weight": round4(weight),
                "total_return": round2(fund_total_return),
                "uses_adjusted_nav": use_adjusted_nav
            })
    
    return BacktestResult(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        statistics=portfolio_stats,
        fund_performance=fund_performance
    )


# ==================== Utility Functions ====================

def compare_adjusted_vs_raw_nav(
    nav_series: pd.DataFrame,
    dividend_records: List[DividendRecord]
) -> pd.DataFrame:
    """
    Compare dividend-adjusted NAV vs raw NAV for visualization.
    
    Args:
        nav_series: DataFrame with columns [date, nav]
        dividend_records: List of DividendRecord objects
        
    Returns:
        DataFrame with columns: date, raw_nav, adjusted_nav, cumulative_factor
        
    Example:
        >>> df = compare_adjusted_vs_raw_nav(nav_history, dividends)
        >>> # Plot both raw_nav and adjusted_nav on same chart
        >>> # Highlight dividend dates with markers
    """
    result = calculate_adjusted_nav(nav_series, dividend_records)
    
    comparison_df = result.adjusted_nav_series[["date", "nav", "adjusted_nav", "cumulative_factor"]].copy()
    comparison_df.columns = ["date", "raw_nav", "adjusted_nav", "cumulative_factor"]
    
    # Explicit cast to DataFrame for type checker
    return pd.DataFrame(comparison_df)


def calculate_cumulative_return_from_adjusted_nav(
    adjusted_nav_series: pd.DataFrame
) -> float:
    """
    Calculate total cumulative return from adjusted NAV series.
    
    Args:
        adjusted_nav_series: DataFrame with adjusted_nav column
        
    Returns:
        Total return as percentage
        
    Note:
        Using adjusted NAV gives the true total return including
        reinvested dividends.
    """
    if adjusted_nav_series.empty or "adjusted_nav" not in adjusted_nav_series.columns:
        return 0.0
    
    start_nav = adjusted_nav_series.iloc[0]["adjusted_nav"]
    end_nav = adjusted_nav_series.iloc[-1]["adjusted_nav"]
    
    return ((end_nav / start_nav) - 1) * 100