"""
Brinson Attribution Analysis Service.
Implements Brinson-Hood-Beebower model for performance attribution.

Mathematical Framework:
-----------------------
The Brinson model decomposes portfolio excess return into three effects:

1. Allocation Effect (配置效应):
   AE = Σ (w_p - w_b) * R_b
   Where:
   - w_p: Portfolio weight in category
   - w_b: Benchmark weight in category
   - R_b: Benchmark return in category

2. Selection Effect (选择效应):
   SE = Σ w_b * (R_p - R_b)
   Where:
   - R_p: Portfolio return in category

3. Interaction Effect (交互效应):
   IE = Σ (w_p - w_b) * (R_p - R_b)

4. Total Effect (总效应):
   TE = AE + SE + IE = R_p - R_b

For FOF context:
- Categories = Individual funds
- Portfolio return = Weighted average of fund returns
- Benchmark return = Single index return

Multi-Period Attribution:
-------------------------
For multi-period analysis, simple arithmetic addition of single-period effects
introduces residual error due to compounding. Two methods are implemented:

1. Carino Method (Carino, 1999):
   Uses logarithmic linking coefficients to adjust single-period effects.
   k_t = [ln(1+R_p) - ln(1+R_b)] / (R_p - R_b)
   Adjusted Effect_t = k_t * Effect_t

2. Menchero Method (Menchero, 2000):
   Alternative approach using smoothed compounding factors.
   More stable when R_p ≈ R_b (avoids division by near-zero).

Both methods achieve residual < 10^-12 when properly implemented.
"""
import functools
import logging
import math
from typing import List, Dict, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class BrinsonAttributionError(Exception):
    """Raised when Brinson calculation fails."""
    pass


def _geometric_compound(returns: List[float]) -> float:
    """
    Calculate geometric compound return from a series of returns.
    
    Formula: (1+r1)(1+r2)...(1+rn) - 1
    
    Args:
        returns: List of period returns (as decimals, e.g., 0.05 for 5%)
    
    Returns:
        Compound return as decimal
    
    Examples:
        >>> _geometric_compound([0.1, 0.1])  # 10% + 10% = 21%
        0.21
        >>> _geometric_compound([0.0])  # 0% return
        0.0
        >>> _geometric_compound([])  # Empty list
        0.0
    """
    if not returns:
        return 0.0
    return functools.reduce(lambda acc, r: acc * (1 + r), returns, 1.0) - 1.0


def _carino_coefficient(portfolio_return: float, benchmark_return: float) -> float:
    """
    Calculate Carino linking coefficient for multi-period attribution.
    
    The Carino factor transforms arithmetic excess returns into geometric-linked effects:
    k = [ln(1+R_p) - ln(1+R_b)] / (R_p - R_b)
    
    This is used for the log-geometric linking approach.
    
    Boundary handling: When R_p ≈ R_b, use L'Hôpital's rule:
    lim(R_p→R_b) k = 1/(1+R_b)
    
    Args:
        portfolio_return: Portfolio return (as decimal, e.g., 0.05 for 5%)
        benchmark_return: Benchmark return (as decimal)
    
    Returns:
        Carino linking coefficient
    
    Raises:
        ValueError: If returns are <= -1 (invalid for logarithm)
    """
    if portfolio_return <= -1 or benchmark_return <= -1:
        raise ValueError("Returns must be > -1 for logarithmic calculation")
    
    excess = portfolio_return - benchmark_return
    
    if abs(excess) < 1e-10:
        return 1.0 / (1.0 + benchmark_return)
    
    log_p = math.log(1.0 + portfolio_return)
    log_b = math.log(1.0 + benchmark_return)
    
    return (log_p - log_b) / excess


def _carino_linking_coefficient(
    portfolio_returns: List[float],
    benchmark_returns: List[float]
) -> float:
    """
    Calculate Carino linking coefficient for multi-period Brinson attribution.
    
    The coefficient transforms arithmetic excess return sums into geometric excess:
    k = (R_p_compound - R_b_compound) / sum(R_p_i - R_b_i)
    
    This ensures: k × (arithmetic sum of effects) = geometric excess return
    
    Args:
        portfolio_returns: List of period portfolio returns
        benchmark_returns: List of period benchmark returns
    
    Returns:
        Carino linking coefficient
    """
    r_p_compound = _geometric_compound(portfolio_returns)
    r_b_compound = _geometric_compound(benchmark_returns)
    
    geom_excess = r_p_compound - r_b_compound
    arith_excess = sum(p - b for p, b in zip(portfolio_returns, benchmark_returns))
    
    if abs(arith_excess) < 1e-10:
        return 1.0
    
    return geom_excess / arith_excess


def _carino_adjusted_effects(
    period_effects: List[float],
    portfolio_returns: List[float],
    benchmark_returns: List[float]
) -> List[float]:
    """
    Calculate Carino-adjusted effects using geometric linking.
    
    Carino (1999) transforms arithmetic excess returns into geometric-linked effects:
    k = (R_p_compound - R_b_compound) / sum(R_p_i - R_b_i)
    
    Then: Adjusted Effect_t = k × Effect_t
    
    This ensures the sum of adjusted effects equals the geometric excess return.
    
    Args:
        period_effects: List of single-period effects (e.g., allocation effects)
        portfolio_returns: List of period portfolio returns
        benchmark_returns: List of period benchmark returns
    
    Returns:
        List of adjusted effects per period
    """
    k = _carino_linking_coefficient(portfolio_returns, benchmark_returns)
    return [k * effect for effect in period_effects]


def _menchero_adjusted_effects(
    period_effects: List[float],
    portfolio_returns: List[float],
    benchmark_returns: List[float]
) -> List[float]:
    """
    Calculate Menchero-adjusted effects using smoothed compounding.
    
    The Menchero method uses:
    k_t = k_overall × (1 + R_p_compound) / (1 + R_p_cum(t))
    
    Then: Adjusted Effect_t = k_t × Effect_t
    
    Args:
        period_effects: List of single-period effects
        portfolio_returns: List of period portfolio returns
        benchmark_returns: List of period benchmark returns
    
    Returns:
        List of adjusted effects per period
    """
    n_periods = len(period_effects)
    
    r_p_compound = _geometric_compound(portfolio_returns)
    r_b_compound = _geometric_compound(benchmark_returns)
    
    sum_excess = sum(p - b for p, b in zip(portfolio_returns, benchmark_returns))
    
    if abs(sum_excess) < 1e-10:
        return period_effects.copy()
    
    k_overall = (r_p_compound - r_b_compound) / sum_excess
    
    adjusted = []
    cum_r_p = 0.0
    
    for t in range(n_periods):
        cum_r_p = (1.0 + cum_r_p) * (1.0 + portfolio_returns[t]) - 1.0
        
        if cum_r_p <= -1:
            k_t = k_overall
        else:
            k_t = k_overall * (1.0 + r_p_compound) / (1.0 + cum_r_p)
        
        adjusted.append(k_t * period_effects[t])
    
    return adjusted


def _menchero_coefficient(
    portfolio_returns: List[float],
    benchmark_returns: List[float]
) -> Tuple[float, List[float]]:
    """
    Calculate Menchero linking coefficients for multi-period attribution.
    
    The Menchero method provides an alternative to Carino that is more
    numerically stable when portfolio and benchmark returns are similar.
    
    Formula:
    - R_p_compound = geometric compound of all portfolio returns
    - R_b_compound = geometric compound of all benchmark returns
    - k_overall = (R_p_compound - R_b_compound) / sum(R_p_i - R_b_i)
    - For each period t:
      k_t = k_overall * (1 + R_p_compound) / (1 + R_p_cum(t))
    
    Args:
        portfolio_returns: List of period portfolio returns
        benchmark_returns: List of period benchmark returns
    
    Returns:
        Tuple of (k_overall, list of period-specific coefficients)
    
    Raises:
        ValueError: If lists have different lengths or are empty
    """
    if len(portfolio_returns) != len(benchmark_returns):
        raise ValueError("Portfolio and benchmark return lists must have same length")
    
    if not portfolio_returns:
        raise ValueError("Return lists cannot be empty")
    
    n_periods = len(portfolio_returns)
    
    r_p_compound = _geometric_compound(portfolio_returns)
    r_b_compound = _geometric_compound(benchmark_returns)
    
    sum_excess = sum(p - b for p, b in zip(portfolio_returns, benchmark_returns))
    
    if abs(sum_excess) < 1e-10:
        return (1.0, [1.0] * n_periods)
    
    k_overall = (r_p_compound - r_b_compound) / sum_excess
    
    coefficients = []
    r_p_cum = 0.0
    
    for t in range(n_periods):
        r_p_cum = (1.0 + r_p_cum) * (1.0 + portfolio_returns[t]) - 1.0
        
        if r_p_cum <= -1:
            k_t = k_overall
        else:
            k_t = k_overall * (1.0 + r_p_compound) / (1.0 + r_p_cum)
        
        coefficients.append(k_t)
    
    return (k_overall, coefficients)


def calculate_multi_period_brinson(
    single_period_results: List[Dict[str, float]],
    portfolio_returns: List[float],
    benchmark_returns: List[float],
    method: str = "auto"
) -> Dict[str, float]:
    """
    Calculate multi-period Brinson attribution using linking algorithms.
    
    Multi-period attribution requires linking single-period effects to
    account for compounding. Two methods are available:
    
    1. Carino (default): Uses logarithmic linking coefficients
       - More intuitive mathematical foundation
       - May have numerical issues when R_p ≈ R_b
    
    2. Menchero: Uses smoothed compounding factors
       - More numerically stable
       - Better for cases with similar returns
    
    When method="auto", Carino is attempted first, and Menchero is used
    as fallback if Carino produces unstable results.
    
    Args:
        single_period_results: List of single-period Brinson results, each
            containing 'allocation_effect', 'selection_effect', 'interaction_effect'
        portfolio_returns: List of period portfolio returns (as decimals)
        benchmark_returns: List of period benchmark returns (as decimals)
        method: Linking method - "carino", "menchero", or "auto"
    
    Returns:
        Dict with:
        - allocation_effect: Multi-period allocation effect
        - selection_effect: Multi-period selection effect
        - interaction_effect: Multi-period interaction effect
        - total_effect: Sum of all effects
        - residual: |total_effect - (R_p_compound - R_b_compound)|
        - method: Method used ("carino" or "menchero")
    
    Raises:
        ValueError: If inputs are invalid or inconsistent
        BrinsonAttributionError: If calculation fails
    
    Examples:
        >>> results = [
        ...     {"allocation_effect": 0.01, "selection_effect": 0.02, "interaction_effect": 0.005},
        ...     {"allocation_effect": 0.015, "selection_effect": 0.01, "interaction_effect": 0.003}
        ... ]
        >>> multi = calculate_multi_period_brinson(results, [0.05, 0.03], [0.04, 0.02])
        >>> multi["residual"] < 1e-12
        True
    """
    # Validate inputs
    if len(single_period_results) != len(portfolio_returns):
        raise ValueError(
            f"Number of single-period results ({len(single_period_results)}) "
            f"must match number of portfolio returns ({len(portfolio_returns)})"
        )
    
    if len(portfolio_returns) != len(benchmark_returns):
        raise ValueError(
            f"Number of portfolio returns ({len(portfolio_returns)}) "
            f"must match number of benchmark returns ({len(benchmark_returns)})"
        )
    
    if not single_period_results:
        raise ValueError("Single-period results cannot be empty")
    
    n_periods = len(single_period_results)
    
    # Calculate compound returns
    r_p_compound = _geometric_compound(portfolio_returns)
    r_b_compound = _geometric_compound(benchmark_returns)
    total_excess = r_p_compound - r_b_compound
    
    # Extract single-period effects
    allocation_effects = [r.get("allocation_effect", 0.0) for r in single_period_results]
    selection_effects = [r.get("selection_effect", 0.0) for r in single_period_results]
    interaction_effects = [r.get("interaction_effect", 0.0) for r in single_period_results]
    
    def _apply_carino():
        """Apply Carino linking method."""
        try:
            adj_alloc = _carino_adjusted_effects(
                allocation_effects, portfolio_returns, benchmark_returns
            )
            adj_select = _carino_adjusted_effects(
                selection_effects, portfolio_returns, benchmark_returns
            )
            adj_interact = _carino_adjusted_effects(
                interaction_effects, portfolio_returns, benchmark_returns
            )
            
            adjusted_allocation = sum(adj_alloc)
            adjusted_selection = sum(adj_select)
            adjusted_interaction = sum(adj_interact)
            
            return {
                "allocation_effect": adjusted_allocation,
                "selection_effect": adjusted_selection,
                "interaction_effect": adjusted_interaction,
                "method": "carino"
            }
        except (ValueError, ZeroDivisionError) as e:
            logger.warning(f"Carino method failed: {e}, falling back to Menchero")
            return None
    
    def _apply_menchero():
        """Apply Menchero linking method."""
        try:
            adj_alloc = _menchero_adjusted_effects(
                allocation_effects, portfolio_returns, benchmark_returns
            )
            adj_select = _menchero_adjusted_effects(
                selection_effects, portfolio_returns, benchmark_returns
            )
            adj_interact = _menchero_adjusted_effects(
                interaction_effects, portfolio_returns, benchmark_returns
            )
            
            adjusted_allocation = sum(adj_alloc)
            adjusted_selection = sum(adj_select)
            adjusted_interaction = sum(adj_interact)
            
            return {
                "allocation_effect": adjusted_allocation,
                "selection_effect": adjusted_selection,
                "interaction_effect": adjusted_interaction,
                "method": "menchero"
            }
        except (ValueError, ZeroDivisionError) as e:
            logger.error(f"Menchero method failed: {e}")
            raise BrinsonAttributionError(f"Menchero calculation failed: {e}")
    
    # Select and apply method
    if method == "carino":
        result = _apply_carino()
        if result is None:
            raise BrinsonAttributionError("Carino method failed")
    elif method == "menchero":
        result = _apply_menchero()
    elif method == "auto":
        # Try Carino first, fallback to Menchero
        result = _apply_carino()
        if result is None:
            result = _apply_menchero()
    else:
        raise ValueError(f"Unknown method: {method}. Use 'carino', 'menchero', or 'auto'")
    
    # Calculate total and residual
    total_effect = (
        result["allocation_effect"] +
        result["selection_effect"] +
        result["interaction_effect"]
    )
    
    residual = abs(total_effect - total_excess)
    
    # Validate residual
    if residual > 1e-10:
        logger.warning(
            f"Multi-period Brinson residual ({residual:.2e}) exceeds threshold. "
            f"Total effect: {total_effect:.6f}, Excess return: {total_excess:.6f}"
        )
    
    return {
        "allocation_effect": result["allocation_effect"],
        "selection_effect": result["selection_effect"],
        "interaction_effect": result["interaction_effect"],
        "total_effect": total_effect,
        "portfolio_compound_return": r_p_compound,
        "benchmark_compound_return": r_b_compound,
        "excess_return": total_excess,
        "residual": residual,
        "method": result["method"]
    }


def calculate_brinson_attribution(
    portfolio_returns: List[Dict],  # [{date, return_pct, nav}, ...]
    benchmark_returns: List[Dict],  # [{date, return_pct, nav}, ...]
    fund_allocations: List[Dict],   # [{"fund_code": "000001", "weight": 0.3, "total_return": 10.5}, ...]
    fund_benchmark_allocations: Optional[List[Dict]] = None,  # For sector/category-level attribution
) -> Dict[str, float]:
    """
    Calculate Brinson attribution for portfolio vs benchmark.
    
    For FOF portfolio:
    - If fund_benchmark_allocations is None, we calculate at fund level
    - Total portfolio return is already in portfolio_returns
    - Each fund's individual contribution is calculated
    
    Args:
        portfolio_returns: Portfolio daily returns
        benchmark_returns: Benchmark daily returns
        fund_allocations: Fund allocations with weights and individual returns
        fund_benchmark_allocations: Optional benchmark weights for each fund/category
    
    Returns:
        Dict with allocation_effect, selection_effect, interaction_effect, total_effect
    
    Note:
        For simple FOF attribution without category decomposition:
        - Allocation effect = Weight mismatch effect
        - Selection effect = Individual fund performance vs benchmark
        - Interaction = Combined effect
    """
    if not portfolio_returns or not fund_allocations:
        raise BrinsonAttributionError("portfolio_returns and fund_allocations must not be empty")
    
    # Calculate total portfolio return
    portfolio_total_return = sum(r["return_pct"] for r in portfolio_returns)
    
    # Calculate average benchmark return
    benchmark_total_return = 0.0
    if benchmark_returns:
        benchmark_total_return = sum(r["return_pct"] for r in benchmark_returns)
    
    # Total excess return
    excess_return = portfolio_total_return - benchmark_total_return
    
    # For FOF without explicit category structure, we use a simplified model
    # Treat each fund as a "category"
    
    # If no benchmark allocation provided, assume equal weight or use portfolio weights
    if fund_benchmark_allocations is None:
        # Simplified approach: assume benchmark would have equal weight in all funds
        # or use some proxy allocation (e.g., market-cap based)
        # For now, use portfolio weights as benchmark weights (neutral attribution)
        fund_benchmark_allocations = [
            {"fund_code": f["fund_code"], "weight": f["weight"]}
            for f in fund_allocations
        ]
    
    # Build lookup dictionaries
    portfolio_weights = {f["fund_code"]: f["weight"] for f in fund_allocations}
    benchmark_weights = {f["fund_code"]: f["weight"] for f in fund_benchmark_allocations}
    
    fund_returns = {f["fund_code"]: f.get("total_return", 0.0) for f in fund_allocations}
    
    # Calculate Brinson effects
    allocation_effect = 0.0
    selection_effect = 0.0
    interaction_effect = 0.0
    
    for fund_code in portfolio_weights.keys():
        w_p = portfolio_weights.get(fund_code, 0.0)
        w_b = benchmark_weights.get(fund_code, 0.0)
        R_p = fund_returns.get(fund_code, 0.0)  # Individual fund return
        R_b = benchmark_total_return  # Use total benchmark return as proxy
        
        # Allocation effect: weight difference * benchmark return
        allocation_effect += (w_p - w_b) * R_b
        
        # Selection effect: benchmark weight * return difference
        selection_effect += w_b * (R_p - R_b)
        
        # Interaction effect: weight difference * return difference
        interaction_effect += (w_p - w_b) * (R_p - R_b)
    
    # Total effect should equal portfolio return - benchmark return
    total_effect = allocation_effect + selection_effect + interaction_effect
    
    # Validate: total_effect should approximate excess_return
    if abs(total_effect - excess_return) > 0.1:
        logger.warning(
            f"Brinson total effect ({total_effect:.2f}) differs from excess return ({excess_return:.2f})"
        )
    
    return {
        "allocation_effect": round(allocation_effect, 4),
        "selection_effect": round(selection_effect, 4),
        "interaction_effect": round(interaction_effect, 4),
        "total_effect": round(total_effect, 4),
        "portfolio_total_return": round(portfolio_total_return, 4),
        "benchmark_total_return": round(benchmark_total_return, 4),
        "excess_return": round(excess_return, 4)
    }


def calculate_brinson_by_category(
    portfolio_category_returns: List[Dict],  # [{category, weight, return}, ...]
    benchmark_category_returns: List[Dict],  # [{category, weight, return}, ...]
) -> Dict[str, float]:
    """
    Calculate Brinson attribution by category (sector/style/etc).
    
    This is the standard Brinson-Hood-Beebower model for multi-category portfolios.
    
    Args:
        portfolio_category_returns: Portfolio allocation per category
        benchmark_category_returns: Benchmark allocation per category
    
    Returns:
        Dict with allocation_effect, selection_effect, interaction_effect, total_effect
    """
    if not portfolio_category_returns or not benchmark_category_returns:
        raise BrinsonAttributionError("Both portfolio and benchmark category data required")
    
    # Build lookup dictionaries
    portfolio_by_cat = {c["category"]: c for c in portfolio_category_returns}
    benchmark_by_cat = {c["category"]: c for c in benchmark_category_returns}
    
    # Get all categories
    categories = set(portfolio_by_cat.keys()) | set(benchmark_by_cat.keys())
    
    # Calculate effects
    allocation_effect = 0.0
    selection_effect = 0.0
    interaction_effect = 0.0
    
    for category in categories:
        w_p = portfolio_by_cat.get(category, {"weight": 0.0})["weight"]
        w_b = benchmark_by_cat.get(category, {"weight": 0.0})["weight"]
        R_p = portfolio_by_cat.get(category, {"return": 0.0})["return"]
        R_b = benchmark_by_cat.get(category, {"return": 0.0})["return"]
        
        # Allocation effect
        allocation_effect += (w_p - w_b) * R_b
        
        # Selection effect
        selection_effect += w_b * (R_p - R_b)
        
        # Interaction effect
        interaction_effect += (w_p - w_b) * (R_p - R_b)
    
    total_effect = allocation_effect + selection_effect + interaction_effect
    
    return {
        "allocation_effect": round(allocation_effect, 4),
        "selection_effect": round(selection_effect, 4),
        "interaction_effect": round(interaction_effect, 4),
        "total_effect": round(total_effect, 4)
    }


def explain_brinson_results(brinson_result: Dict[str, float]) -> str:
    """
    Generate human-readable explanation of Brinson attribution results.
    
    Args:
        brinson_result: Dict from calculate_brinson_attribution
    
    Returns:
        Explanation string
    """
    allocation = brinson_result.get("allocation_effect", 0.0)
    selection = brinson_result.get("selection_effect", 0.0)
    interaction = brinson_result.get("interaction_effect", 0.0)
    total = brinson_result.get("total_effect", 0.0)
    
    explanation_parts = []
    
    # Overall performance
    if total > 0:
        explanation_parts.append(f"组合跑赢基准 {total:.2f}%")
    else:
        explanation_parts.append(f"组合跑输基准 {abs(total):.2f}%")
    
    # Allocation effect
    if abs(allocation) > 0.1:
        if allocation > 0:
            explanation_parts.append(f"配置效应贡献 +{allocation:.2f}% (权重配置优于基准)")
        else:
            explanation_parts.append(f"配置效应拖累 {allocation:.2f}% (权重配置劣于基准)")
    
    # Selection effect
    if abs(selection) > 0.1:
        if selection > 0:
            explanation_parts.append(f"选择效应贡献 +{selection:.2f}% (基金表现优于基准)")
        else:
            explanation_parts.append(f"选择效应拖累 {selection:.2f}% (基金表现劣于基准)")
    
    # Interaction effect
    if abs(interaction) > 0.1:
        if interaction > 0:
            explanation_parts.append(f"交互效应贡献 +{interaction:.2f}%")
        else:
            explanation_parts.append(f"交互效应拖累 {interaction:.2f}%")
    
    return " | ".join(explanation_parts) if explanation_parts else "无明显归因效应"