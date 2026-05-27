"""
Insurance product calculation services.
IRR (Internal Rate of Return) for cash value projection.
"""
import numpy as np
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class InsurancePolicy:
    premium: float  # Annual premium
    payment_years: int  # Payment period
    age: int  # Current age
    gender: str  # 'M' or 'F'


@dataclass
class CashValueProjection:
    year: int
    premium_paid: float
    cash_value: float
    death_benefit: float
    irr: Optional[float]


def calculate_irr(cash_flows: List[float]) -> Optional[float]:
    """
    Calculate IRR using numpy's irr function.
    
    Args:
        cash_flows: List of cash flows (negative for payments, positive for withdrawal)
    
    Returns:
        IRR as percentage, or None if calculation fails
    """
    if not cash_flows or len(cash_flows) < 2:
        return None
    
    try:
        result = np.irr(cash_flows)
        if np.isnan(result) or np.isinf(result):
            return None
        return result * 100  # Convert to percentage
    except (ValueError, RuntimeError):
        return None


def project_cash_values(
    policy: InsurancePolicy,
    projection_years: int = 30,
    assumed_growth: float = 3.5  # Assumed annual growth rate (%)
) -> List[CashValueProjection]:
    """
    Project cash values over time.
    Uses standard insurance cash value formula.
    
    Args:
        policy: Insurance policy parameters
        projection_years: Number of years to project (default 30)
        assumed_growth: Assumed annual growth rate in percentage (default 3.5%)
    
    Returns:
        List of CashValueProjection for each year
    """
    projections = []
    total_premium = 0.0
    cash_value = 0.0
    
    for year in range(1, projection_years + 1):
        # Premium payment (only during payment period)
        if year <= policy.payment_years:
            total_premium += policy.premium
            cash_flows = [-policy.premium] * year
        else:
            cash_flows = [-policy.premium] * policy.payment_years
        
        # Cash value grows at assumed rate
        # Formula: total_premium * (1 + growth_rate)^year * surrender_ratio
        # Surrender value ratio typically 85% for life insurance products
        cash_value = total_premium * (1 + assumed_growth / 100) ** year * 0.85
        
        # Death benefit (typically higher than cash value)
        # Standard formula: total_premium * 1.5 + accumulated cash_value
        death_benefit = total_premium * 1.5 + cash_value
        
        # Add terminal cash flow for IRR calculation
        # If policyholder surrenders at this year, they receive cash_value
        irr_flows = cash_flows + [cash_value]
        irr = calculate_irr(irr_flows)
        
        projections.append(CashValueProjection(
            year=year,
            premium_paid=total_premium,
            cash_value=round(cash_value, 2),
            death_benefit=round(death_benefit, 2),
            irr=round(irr, 2) if irr is not None else None
        ))
    
    return projections


def find_break_even_year(projections: List[CashValueProjection]) -> Optional[int]:
    """
    Find the break-even year where cash value >= premium paid.
    
    Args:
        projections: List of cash value projections
    
    Returns:
        Break-even year number, or None if never breaks even
    """
    for p in projections:
        if p.cash_value >= p.premium_paid:
            return p.year
    return None
