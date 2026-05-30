"""
Numeric formatting utilities for consistent decimal output.
Provides centralized rounding functions to ensure consistency across API responses.
"""
from typing import Optional

DECIMAL_STANDARD = 2  # Standard for prices, percentages
DECIMAL_PRECISION = 4  # For domain-specific values (correlations, factors)


def round2(value: Optional[float]) -> Optional[float]:
    """
    Round to 2 decimal places.
    Use for: prices, percentages, returns, scores.
    
    Args:
        value: Float value to round, or None
        
    Returns:
        Rounded float or None if input is None
    """
    if value is None:
        return None
    return round(value, DECIMAL_STANDARD)


def round4(value: Optional[float]) -> Optional[float]:
    """
    Round to 4 decimal places.
    Use for: correlation coefficients, factor exposure weights, NAV.
    
    Args:
        value: Float value to round, or None
        
    Returns:
        Rounded float or None if input is None
    """
    if value is None:
        return None
    return round(value, DECIMAL_PRECISION)


def round_percent(value: Optional[float]) -> Optional[float]:
    """
    Round percentage to 2 decimal places.
    Alias for round2() for semantic clarity.
    
    Args:
        value: Percentage value to round, or None
        
    Returns:
        Rounded percentage or None if input is None
    """
    return round2(value)


def round_price(value: Optional[float]) -> Optional[float]:
    """
    Round price to 2 decimal places.
    Alias for round2() for semantic clarity.
    
    Args:
        value: Price value to round, or None
        
    Returns:
        Rounded price or None if input is None
    """
    return round2(value)
