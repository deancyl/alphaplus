"""
FOF Backtesting Engine Service.
Calculates portfolio NAV by combining fund NAVs with weights.
Computes statistics: total_return, annual_return, max_drawdown, sharpe_ratio, volatility.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.fund import FundNavHistory

logger = logging.getLogger(__name__)


class BacktestError(Exception):
    """Raised when backtest calculation fails."""
    pass


@dataclass
class BacktestStatistics:
    """Backtest statistics result."""
    total_return: float  # percentage
    annual_return: float  # percentage
    max_drawdown: float  # percentage
    sharpe_ratio: float
    volatility: float  # annualized, percentage
    sortino_ratio: Optional[float] = None
    calmar_ratio: Optional[float] = None


@dataclass
class DailyReturn:
    """Daily return data."""
    date: str
    return_pct: float  # percentage
    nav: float


@dataclass
class BacktestResult:
    """Complete backtest result."""
    portfolio_returns: List[DailyReturn]
    benchmark_returns: Optional[List[DailyReturn]]
    statistics: BacktestStatistics
    fund_performance: List[Dict] = field(default_factory=list)


async def get_fund_nav_history(
    fund_code: str,
    start_date: str,
    end_date: str,
    db: AsyncSession
) -> pd.DataFrame:
    """
    Fetch NAV history for a single fund.
    
    Args:
        fund_code: Fund code (e.g., "000001")
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        db: Async database session
    
    Returns:
        DataFrame with columns: date, nav, daily_return
    
    Raises:
        BacktestError: If no NAV data available
    """
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
        raise BacktestError(f"No NAV history found for fund {fund_code} in period {start_date} to {end_date}")
    
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
    
    return df


async def get_index_nav_history(
    index_code: str,
    start_date: str,
    end_date: str,
    db: AsyncSession
) -> pd.DataFrame:
    """
    Fetch index NAV history (treat index as a fund for simplicity).
    For now, we'll use index valuation history or generate from market data.
    
    Args:
        index_code: Index code (e.g., "000300" for 沪深300)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        db: Async database session
    
    Returns:
        DataFrame with columns: date, nav, daily_return
    """
    # For indices, we treat the close price as NAV
    # We'll need to fetch from IndexValuationHistory or StockQuotesHistory
    from backend.models.fund import IndexValuationHistory
    
    result = await db.execute(
        select(IndexValuationHistory)
        .where(
            and_(
                IndexValuationHistory.index_code == index_code,
                IndexValuationHistory.trade_date >= start_date,
                IndexValuationHistory.trade_date <= end_date
            )
        )
        .order_by(IndexValuationHistory.trade_date)
    )
    index_records = result.scalars().all()
    
    if not index_records:
        # Return empty DataFrame if no data
        return pd.DataFrame({"date": [], "nav": [], "daily_return": []})
    
    # Use index_close_price as NAV
    df = pd.DataFrame([
        {
            "date": r.trade_date,
            "nav": r.index_close_price if r.index_close_price else 1.0,
            "daily_return": 0.0  # Will calculate later
        }
        for r in index_records
    ])
    
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    
    # Calculate daily returns
    if len(df) > 1:
        df["daily_return"] = df["nav"].pct_change() * 100
        df["daily_return"] = df["daily_return"].fillna(0.0)
    
    return df


def calculate_statistics(
    nav_series,
    daily_returns,
    risk_free_rate: float = 0.03  # 3% annual risk-free rate
) -> BacktestStatistics:
    """
    Calculate backtest statistics from NAV series.
    
    Args:
        nav_series: Series of NAV values
        daily_returns: Series of daily returns (percentage)
        risk_free_rate: Annual risk-free rate (default 3%)
    
    Returns:
        BacktestStatistics object
    """
    if len(nav_series) < 2:
        return BacktestStatistics(
            total_return=0.0,
            annual_return=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            volatility=0.0
        )
    
    # Total return
    total_return = ((nav_series.iloc[-1] / nav_series.iloc[0]) - 1) * 100
    
    # Annualized return
    days = len(nav_series)
    years = days / 252.0  # 252 trading days per year
    annual_return = ((nav_series.iloc[-1] / nav_series.iloc[0]) ** (1 / years) - 1) * 100 if years > 0 else 0.0
    
    # Max drawdown
    peak = nav_series.cummax()
    drawdown = (nav_series - peak) / peak * 100
    max_drawdown = drawdown.min()
    
    # Volatility (annualized)
    volatility = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 1 else 0.0
    
    # Sharpe ratio
    excess_return = annual_return - risk_free_rate * 100
    sharpe_ratio = excess_return / volatility if volatility > 0 else 0.0
    
    # Sortino ratio (downside deviation)
    negative_returns = daily_returns[daily_returns < 0]
    downside_std = negative_returns.std() * np.sqrt(252) if len(negative_returns) > 1 else volatility
    sortino_ratio = excess_return / downside_std if downside_std > 0 else 0.0
    
    # Calmar ratio
    calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0.0
    
    return BacktestStatistics(
        total_return=round(total_return, 2),
        annual_return=round(annual_return, 2),
        max_drawdown=round(max_drawdown, 2),
        sharpe_ratio=round(sharpe_ratio, 2),
        volatility=round(volatility, 2),
        sortino_ratio=round(sortino_ratio, 2) if not np.isnan(sortino_ratio) else None,
        calmar_ratio=round(calmar_ratio, 2) if not np.isnan(calmar_ratio) else None
    )


async def run_backtest(
    fund_allocations: List[Dict[str, float]],  # [{"fund_code": "000001", "weight": 0.3}, ...]
    start_date: str,
    end_date: str,
    benchmark: str,
    db: AsyncSession
) -> BacktestResult:
    """
    Run FOF backtest.
    
    Args:
        fund_allocations: List of fund allocations with fund_code and weight
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        benchmark: Benchmark index code (e.g., "000300")
        db: Async database session
    
    Returns:
        BacktestResult with portfolio returns, benchmark returns, and statistics
    
    Raises:
        BacktestError: If backtest calculation fails
    """
    logger.info(f"Running backtest for {len(fund_allocations)} funds from {start_date} to {end_date}")
    
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
    
    # Fetch NAV history for all funds
    fund_navs = {}
    all_dates = None
    
    for allocation in fund_allocations:
        fund_code = str(allocation["fund_code"])  # Ensure string type
        weight = float(allocation["weight"])  # Ensure float type
        
        try:
            nav_df = await get_fund_nav_history(fund_code, start_date, end_date, db)
            fund_navs[fund_code] = {
                "weight": weight,
                "nav_df": nav_df
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
    
    # Find common date range across all funds
    if all_dates:
        common_dates = sorted(list(all_dates))
        if len(common_dates) < 2:
            raise BacktestError("Insufficient overlapping dates across funds")
    else:
        raise BacktestError("No common dates found across funds")
    
    # Build portfolio NAV
    portfolio_nav = []
    date_to_nav = {}
    
    for date in common_dates:
        total_nav = 0.0
        for fund_code, data in fund_navs.items():
            weight = data["weight"]
            nav_df = data["nav_df"]
            
            # Get NAV for this date
            row = nav_df[nav_df["date"] == date]
            if not row.empty:
                total_nav += weight * row.iloc[0]["nav"]
        
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
            return_pct=round(float(row["daily_return"]), 4),
            nav=round(float(row["nav"]), 4)
        )
        for _, row in portfolio_df.iterrows()
    ]
    
    # Fetch benchmark NAV history
    benchmark_returns = None
    try:
        benchmark_df = await get_index_nav_history(benchmark, start_date, end_date, db)
        
        if not benchmark_df.empty and len(benchmark_df) > 1:
            # Align benchmark dates with portfolio dates
            benchmark_df = benchmark_df[benchmark_df["date"].isin(common_dates)]
            
            benchmark_returns = [
                DailyReturn(
                    date=str(row["date"])[:10] if len(str(row["date"])) > 10 else str(row["date"]),
                    return_pct=round(float(row["daily_return"]), 4),
                    nav=round(float(row["nav"]), 4)
                )
                for _, row in benchmark_df.iterrows()
            ]
    except Exception as e:
        logger.warning(f"Failed to fetch benchmark data: {e}")
    
    # Calculate individual fund performance
    fund_performance = []
    for fund_code, data in fund_navs.items():
        nav_df = data["nav_df"]
        weight = data["weight"]
        
        if len(nav_df) > 1:
            fund_total_return = ((nav_df.iloc[-1]["nav"] / nav_df.iloc[0]["nav"]) - 1) * 100
            fund_performance.append({
                "fund_code": fund_code,
                "weight": round(weight, 4),
                "total_return": round(fund_total_return, 2)
            })
    
    return BacktestResult(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        statistics=portfolio_stats,
        fund_performance=fund_performance
    )


def decompose_into_periods(
    daily_returns: List[Dict],
    granularity: str = "monthly"
) -> List[Dict]:
    """
    Decompose daily returns into periods (monthly/weekly/daily).
    
    Args:
        daily_returns: List of daily return dicts with keys:
            - date: str (YYYY-MM-DD)
            - return_pct: float (daily return percentage)
            - nav: float (NAV value)
        granularity: Period granularity - "daily", "weekly", or "monthly"
    
    Returns:
        List of period dicts with keys:
            - period_start: str (YYYY-MM-DD)
            - period_end: str (YYYY-MM-DD)
            - period_return: float (period return as decimal, e.g., 0.05 for 5%)
            - start_nav: float
            - end_nav: float
    
    Examples:
        >>> daily = [
        ...     {"date": "2023-01-01", "return_pct": 1.0, "nav": 1.01},
        ...     {"date": "2023-01-02", "return_pct": 0.5, "nav": 1.015},
        ... ]
        >>> periods = decompose_into_periods(daily, granularity="daily")
        >>> len(periods)
        2
    """
    if not daily_returns:
        return []
    
    # Convert to DataFrame for easier manipulation
    df = pd.DataFrame(daily_returns)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    
    if granularity == "daily":
        # Each day is a period
        periods = []
        for idx, row in df.iterrows():
            periods.append({
                "period_start": str(row["date"].date()),
                "period_end": str(row["date"].date()),
                "period_return": row["return_pct"] / 100.0,  # Convert to decimal
                "start_nav": row["nav"] / (1 + row["return_pct"] / 100.0),
                "end_nav": row["nav"],
            })
        return periods
    
    # Group by period
    if granularity == "weekly":
        # Use ISO week
        df["period_key"] = df["date"].dt.strftime("%Y-W%U")
    elif granularity == "monthly":
        # Use year-month
        df["period_key"] = df["date"].dt.strftime("%Y-%m")
    else:
        raise ValueError(f"Unknown granularity: {granularity}")
    
    periods = []
    for period_key, group in df.groupby("period_key"):
        group = group.sort_values("date")
        
        start_date = group.iloc[0]["date"]
        end_date = group.iloc[-1]["date"]
        start_nav = group.iloc[0]["nav"]
        end_nav = group.iloc[-1]["nav"]
        
        # Calculate period return from NAV
        # If first row has a return, adjust start_nav
        if group.iloc[0]["return_pct"] != 0:
            start_nav = group.iloc[0]["nav"] / (1 + group.iloc[0]["return_pct"] / 100.0)
        
        period_return = (end_nav / start_nav) - 1.0
        
        periods.append({
            "period_start": str(start_date.date()),
            "period_end": str(end_date.date()),
            "period_return": period_return,
            "start_nav": start_nav,
            "end_nav": end_nav,
        })
    
    return periods


def calculate_single_period_brinson(
    portfolio_period_return: float,
    benchmark_period_return: float,
    portfolio_weights: Dict[str, float],
    benchmark_weights: Dict[str, float],
    fund_returns: Dict[str, float],
) -> Dict[str, float]:
    """
    Calculate single-period Brinson attribution.
    
    Args:
        portfolio_period_return: Portfolio return for this period (decimal)
        benchmark_period_return: Benchmark return for this period (decimal)
        portfolio_weights: Portfolio weights per fund {fund_code: weight}
        benchmark_weights: Benchmark weights per fund {fund_code: weight}
        fund_returns: Individual fund returns {fund_code: return}
    
    Returns:
        Dict with allocation_effect, selection_effect, interaction_effect
    """
    allocation_effect = 0.0
    selection_effect = 0.0
    interaction_effect = 0.0
    
    all_funds = set(portfolio_weights.keys()) | set(benchmark_weights.keys())
    
    for fund_code in all_funds:
        w_p = portfolio_weights.get(fund_code, 0.0)
        w_b = benchmark_weights.get(fund_code, 0.0)
        R_p = fund_returns.get(fund_code, 0.0)
        R_b = benchmark_period_return  # Use benchmark return as proxy
        
        # Allocation effect: weight difference * benchmark return
        allocation_effect += (w_p - w_b) * R_b
        
        # Selection effect: benchmark weight * return difference
        selection_effect += w_b * (R_p - R_b)
        
        # Interaction effect: weight difference * return difference
        interaction_effect += (w_p - w_b) * (R_p - R_b)
    
    return {
        "allocation_effect": allocation_effect,
        "selection_effect": selection_effect,
        "interaction_effect": interaction_effect,
    }
