"""
Fund quantitative metrics calculation services.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.fund import FundIndicators, FundNavHistory
from backend.utils.formatters import round2


async def calculate_new_high_ratio(
    fund_code: str,
    db: AsyncSession,
    lookback_days: int = 250
) -> Optional[float]:
    """
    Calculate Within-1Y New High Ratio.
    
    Formula: Count of days where NAV >= max(NAV in past year) / total days
    
    This measures how often the fund reaches new highs, indicating
    strong momentum and good holding experience.
    
    Args:
        fund_code: Fund code to calculate
        db: Database session
        lookback_days: Number of trading days to look back (default 250)
    
    Returns:
        New high ratio as percentage (0-100), or None if insufficient data
    """
    # Get NAV history for past year
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=int(lookback_days * 1.5))).strftime("%Y-%m-%d")
    
    result = await db.execute(
        select(FundNavHistory)
        .where(FundNavHistory.fund_code == fund_code)
        .where(FundNavHistory.nav_date >= start_date)
        .order_by(FundNavHistory.nav_date)
    )
    nav_records = result.scalars().all()
    
    if len(nav_records) < lookback_days * 0.5:  # Need at least half the data
        return None
    
    # Convert to pandas for rolling calculation
    df = pd.DataFrame([
        {'date': r.nav_date, 'nav': r.nav_value}
        for r in nav_records
    ])
    
    if df.empty:
        return None
    
    # Calculate rolling max
    df = df.sort_values('date').tail(lookback_days)
    df['rolling_max'] = df['nav'].expanding().max()
    
    # Count days where NAV equals rolling max (new high)
    new_high_days = (df['nav'] == df['rolling_max']).sum()
    total_days = len(df)
    
    if total_days == 0:
        return None
    
    return round2(float(new_high_days / total_days * 100))


async def batch_calculate_new_high_ratio(
    fund_codes: list[str],
    db: AsyncSession,
    lookback_days: int = 250
) -> dict[str, Optional[float]]:
    """
    Calculate new high ratio for multiple funds.
    
    Args:
        fund_codes: List of fund codes
        db: Database session
        lookback_days: Number of trading days to look back
    
    Returns:
        Dictionary mapping fund_code to new_high_ratio
    """
    results = {}
    for fund_code in fund_codes:
        ratio = await calculate_new_high_ratio(fund_code, db, lookback_days)
        results[fund_code] = ratio
    return results
