"""
Drip Investment (AIP - Automatic Investment Plan) Calculator Service.
Calculates returns, drawdown, volatility, and lump-sum comparison for regular investments.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict

import numpy as np
import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.fund import FundNavHistory
from backend.utils.formatters import round2, round4

logger = logging.getLogger(__name__)


class AIPCalculatorError(Exception):
    """Raised when AIP calculation fails."""
    pass


@dataclass
class AIPResult:
    """Result of AIP calculation."""
    total_investment: float
    current_value: float
    return_rate: float  # percentage
    max_drawdown: float  # percentage
    volatility: float
    periods: int
    units_total: float
    lump_sum_comparison: Dict[str, float]  # lump_sum_value, lump_sum_return
    investment_dates: List[str]
    nav_history: List[Dict]  # for charting: [{date, nav, units, value, cumulative_return}]


def _get_next_trading_day(date: datetime, trading_days: pd.DatetimeIndex) -> datetime:
    """
    Get the next trading day on or after the given date.
    
    Args:
        date: Target date
        trading_days: Sorted DatetimeIndex of all trading days
    
    Returns:
        Next trading day on or after the given date
    """
    # Find the first trading day >= date
    mask = trading_days >= date
    if mask.any():
        return trading_days[mask][0]
    return None


def calculate_investment_dates(
    start_date: str,
    end_date: str,
    frequency: str,
    trading_days: pd.DatetimeIndex
) -> List[datetime]:
    """
    Calculate investment dates based on frequency.
    
    Args:
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
        frequency: "weekly", "biweekly", or "monthly"
        trading_days: Sorted DatetimeIndex of all trading days
    
    Returns:
        List of datetime objects for investment dates
    
    Raises:
        AIPCalculatorError: If invalid frequency or no valid dates
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    if start >= end:
        raise AIPCalculatorError("start_date must be before end_date")
    
    investment_dates = []
    
    if frequency == "weekly":
        # Every Monday (or next trading day)
        current = start
        while current <= end:
            # Find next Monday
            days_until_monday = (7 - current.weekday()) % 7
            if days_until_monday == 0 and current.weekday() == 0:
                # Already Monday
                monday = current
            else:
                monday = current + timedelta(days=days_until_monday if days_until_monday > 0 else 7)
            
            if monday > end:
                break
            
            # Get next trading day on or after this Monday
            trading_day = _get_next_trading_day(monday, trading_days)
            if trading_day and trading_day <= pd.Timestamp(end):
                investment_dates.append(trading_day.to_pydatetime())
            
            # Move to next week
            current = monday + timedelta(days=7)
    
    elif frequency == "biweekly":
        # Every 2nd Monday
        current = start
        week_count = 0
        while current <= end:
            days_until_monday = (7 - current.weekday()) % 7
            if days_until_monday == 0 and current.weekday() == 0:
                monday = current
            else:
                monday = current + timedelta(days=days_until_monday if days_until_monday > 0 else 7)
            
            if monday > end:
                break
            
            if week_count % 2 == 0:
                trading_day = _get_next_trading_day(monday, trading_days)
                if trading_day and trading_day <= pd.Timestamp(end):
                    investment_dates.append(trading_day.to_pydatetime())
            
            week_count += 1
            current = monday + timedelta(days=7)
    
    elif frequency == "monthly":
        # First trading day of each month
        current = start.replace(day=1)
        while current <= end:
            # Get first trading day of this month
            month_start = current.replace(day=1)
            trading_day = _get_next_trading_day(month_start, trading_days)
            
            if trading_day and trading_day <= pd.Timestamp(end):
                # Only add if >= start_date
                if trading_day >= pd.Timestamp(start):
                    investment_dates.append(trading_day.to_pydatetime())
            
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
    
    else:
        raise AIPCalculatorError(f"Invalid frequency: {frequency}. Must be 'weekly', 'biweekly', or 'monthly'")
    
    if not investment_dates:
        raise AIPCalculatorError("No valid investment dates found in the specified period")
    
    return investment_dates


async def calculate_aip(
    fund_code: str,
    frequency: str,
    amount: float,
    start_date: str,
    end_date: Optional[str],
    db: AsyncSession
) -> AIPResult:
    """
    Calculate drip investment returns.
    
    Args:
        fund_code: Fund code (e.g., "000001")
        frequency: "weekly", "biweekly", or "monthly"
        amount: Investment amount per period (元)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD), defaults to today
        db: Async database session
    
    Returns:
        AIPResult with all calculated metrics
    
    Raises:
        AIPCalculatorError: If validation fails or no NAV data available
    """
    # Validate inputs
    if amount <= 0:
        raise AIPCalculatorError("amount must be greater than 0")
    
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    if start >= end:
        raise AIPCalculatorError("start_date must be before end_date")
    
    # Fetch NAV history from database
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
        raise AIPCalculatorError(f"No NAV history found for fund {fund_code} in the specified period")
    
    # Convert to DataFrame for efficient calculation
    nav_df = pd.DataFrame([
        {"date": r.nav_date, "nav": r.nav_value}
        for r in nav_records
    ])
    nav_df["date"] = pd.to_datetime(nav_df["date"])
    nav_df = nav_df.sort_values("date").reset_index(drop=True)
    
    # Get trading days
    trading_days = nav_df["date"].values
    trading_days_idx = pd.DatetimeIndex(trading_days)
    
    # Calculate investment dates
    investment_dates = calculate_investment_dates(start_date, end_date, frequency, trading_days_idx)
    
    # Build NAV lookup for fast access
    nav_lookup = dict(zip(nav_df["date"].dt.strftime("%Y-%m-%d"), nav_df["nav"]))
    
    # Calculate units purchased at each investment date
    investments = []
    for inv_date in investment_dates:
        date_str = inv_date.strftime("%Y-%m-%d")
        
        # Find NAV for this date (or next available)
        nav = None
        for idx, row in nav_df.iterrows():
            if row["date"] >= pd.Timestamp(inv_date):
                nav = row["nav"]
                break
        
        if nav is None:
            # Use last available NAV
            nav = nav_df.iloc[-1]["nav"]
        
        units = amount / nav
        investments.append({
            "date": date_str,
            "nav": nav,
            "units": units,
            "amount": amount
        })
    
    # Create investment DataFrame
    inv_df = pd.DataFrame(investments)
    
    # Calculate cumulative metrics
    periods = len(investments)
    total_investment = periods * amount
    units_total = inv_df["units"].sum()
    
    # Get latest NAV for current value calculation
    latest_nav = nav_df.iloc[-1]["nav"]
    latest_date = nav_df.iloc[-1]["date"].strftime("%Y-%m-%d")
    current_value = units_total * latest_nav
    
    # Calculate return rate
    return_rate = ((current_value - total_investment) / total_investment) * 100 if total_investment > 0 else 0.0
    
    # Calculate portfolio value over time for drawdown and volatility
    # Build daily portfolio value series
    portfolio_values = []
    cumulative_units = 0.0
    
    for idx, row in nav_df.iterrows():
        date = row["date"]
        nav = row["nav"]
        
        # Add units if this is an investment date
        for inv in investments:
            if pd.Timestamp(inv["date"]) <= date and inv not in [p.get("inv") for p in portfolio_values if "inv" in p]:
                # Check if we already added this investment
                inv_date_ts = pd.Timestamp(inv["date"])
                if inv_date_ts <= date:
                    # This is a simplified approach - we'll recalculate properly
                    pass
        
        # Simpler approach: recalculate cumulative units at each date
        cumulative_units = sum(
            inv["units"] for inv in investments 
            if pd.Timestamp(inv["date"]) <= date
        )
        
        portfolio_value = cumulative_units * nav
        portfolio_values.append({
            "date": date.strftime("%Y-%m-%d"),
            "nav": nav,
            "units": cumulative_units,
            "value": portfolio_value
        })
    
    portfolio_df = pd.DataFrame(portfolio_values)
    
    # Calculate cumulative return series
    cumulative_invested = []
    running_total = 0.0
    inv_idx = 0
    for idx, row in portfolio_df.iterrows():
        date = pd.Timestamp(row["date"])
        # Add investment if on or after investment date
        while inv_idx < len(investments) and pd.Timestamp(investments[inv_idx]["date"]) <= date:
            running_total += amount
            inv_idx += 1
        cumulative_invested.append(running_total)
    
    portfolio_df["cumulative_invested"] = cumulative_invested
    portfolio_df["cumulative_return"] = np.where(
        portfolio_df["cumulative_invested"] > 0,
        ((portfolio_df["value"] - portfolio_df["cumulative_invested"]) / portfolio_df["cumulative_invested"]) * 100,
        0.0
    )
    
    # Calculate max drawdown
    # Max drawdown = max peak-to-trough decline in portfolio value
    portfolio_df["peak"] = portfolio_df["value"].cummax()
    portfolio_df["drawdown"] = (portfolio_df["value"] - portfolio_df["peak"]) / portfolio_df["peak"] * 100
    max_drawdown = portfolio_df["drawdown"].min()  # Most negative value
    
    # Calculate volatility (std of daily returns)
    # Only calculate after first investment
    first_inv_date = pd.Timestamp(investments[0]["date"])
    post_inv_df = portfolio_df[portfolio_df["date"] >= first_inv_date.strftime("%Y-%m-%d")].copy()
    
    if len(post_inv_df) > 1:
        # Calculate daily returns of the portfolio
        post_inv_df["daily_return"] = post_inv_df["value"].pct_change()
        volatility = post_inv_df["daily_return"].std() * np.sqrt(252) * 100  # Annualized, in percentage
    else:
        volatility = 0.0
    
    # Lump-sum comparison
    # What if we invested all money at start date?
    start_nav = investments[0]["nav"] if investments else latest_nav
    lump_sum_units = total_investment / start_nav
    lump_sum_value = lump_sum_units * latest_nav
    lump_sum_return = ((lump_sum_value - total_investment) / total_investment) * 100 if total_investment > 0 else 0.0
    
    lump_sum_comparison = {
        "lump_sum_value": round2(lump_sum_value),
        "lump_sum_return": round2(lump_sum_return),
        "lump_sum_units": round4(lump_sum_units)
    }
    
    # Prepare nav_history for charting
    nav_history = portfolio_df[["date", "nav", "units", "value", "cumulative_return"]].to_dict("records")
    nav_history = [
        {
            "date": row["date"],
            "nav": round4(row["nav"]),
            "units": round4(row["units"]),
            "value": round2(row["value"]),
            "cumulative_return": round2(row["cumulative_return"])
        }
        for row in nav_history
    ]
    
    return AIPResult(
        total_investment=round2(total_investment),
        current_value=round2(current_value),
        return_rate=round2(return_rate),
        max_drawdown=round2(max_drawdown),
        volatility=round2(volatility) if not np.isnan(volatility) else 0.0,
        periods=periods,
        units_total=round4(units_total),
        lump_sum_comparison=lump_sum_comparison,
        investment_dates=[inv["date"] for inv in investments],
        nav_history=nav_history
    )
