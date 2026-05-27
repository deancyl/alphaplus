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
"""
import logging
from typing import List, Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)


class BrinsonAttributionError(Exception):
    """Raised when Brinson calculation fails."""
    pass


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