"""
Crowding analysis for institutional holdings.

Provides overlap calculation and crowding score computation.
"""
from typing import Dict, List
from backend.services.duckdb_ingestion import (
    aggregate_by_stock,
    calculate_crowding_score as calc_crowding_score,
    search_funds_by_stock,
)
import logging

logger = logging.getLogger(__name__)


async def calculate_holding_overlap(funds: List[Dict]) -> float:
    """
    Calculate holding overlap coefficient between funds.
    
    Measures how similar fund portfolios are based on shared holdings.
    Overlap = sum(min(w_i_a, w_i_b)) for all stocks i across funds a and b.
    
    Args:
        funds: List of fund dicts with 'fund_code' and 'holding_ratio'
    
    Returns:
        Overlap coefficient (0-1), where 1 means perfect overlap
    """
    if len(funds) < 2:
        return 0.0
    
    fund_codes = [f['fund_code'] for f in funds]
    
    overlap_scores = []
    for i in range(len(fund_codes)):
        for j in range(i + 1, len(fund_codes)):
            overlap = await _calculate_pairwise_overlap(fund_codes[i], fund_codes[j])
            overlap_scores.append(overlap)
    
    return sum(overlap_scores) / len(overlap_scores) if overlap_scores else 0.0


async def _calculate_pairwise_overlap(fund_a: str, fund_b: str) -> float:
    """
    Calculate overlap between two funds.
    
    Uses Jaccard-like similarity on top holdings.
    """
    from backend.core.duckdb_pool import duckdb_pool_manager
    
    result_a = await duckdb_pool_manager.execute_read("""
        SELECT stock_code, holding_ratio
        FROM fund_portfolio_holdings
        WHERE fund_code = ?
        ORDER BY holding_ratio DESC
        LIMIT 50
    """, [fund_a])
    
    result_b = await duckdb_pool_manager.execute_read("""
        SELECT stock_code, holding_ratio
        FROM fund_portfolio_holdings
        WHERE fund_code = ?
        ORDER BY holding_ratio DESC
        LIMIT 50
    """, [fund_b])
    
    if not result_a or not result_b:
        return 0.0
    
    holdings_a = {row[0]: row[1] for row in result_a}
    holdings_b = {row[0]: row[1] for row in result_b}
    
    common_stocks = set(holdings_a.keys()) & set(holdings_b.keys())
    
    if not common_stocks:
        return 0.0
    
    overlap_sum = sum(min(holdings_a[s], holdings_b[s]) for s in common_stocks)
    min_total = min(sum(holdings_a.values()), sum(holdings_b.values()))
    
    return overlap_sum / min_total if min_total > 0 else 0.0


async def get_crowding_score(stock_code: str) -> Dict:
    """
    Get comprehensive crowding analysis for a stock.
    
    Aggregates multiple metrics:
    - Basic aggregation (funds count, weights)
    - HHI index
    - Overlap coefficient
    - Concentration level
    
    Args:
        stock_code: Stock code to analyze
    
    Returns:
        Dict with all crowding metrics
    """
    aggregation = await aggregate_by_stock(stock_code)
    crowding = await calc_crowding_score(stock_code)
    
    funds_data = await search_funds_by_stock(stock_code, limit=50)
    overlap = await calculate_holding_overlap(funds_data.get('funds', []))
    
    return {
        'stock_code': stock_code,
        'stock_name': aggregation.get('stock_name', ''),
        'total_funds': crowding['num_funds'],
        'crowding_score': crowding['crowding_score'],
        'hhi_index': crowding['hhi_index'],
        'concentration_level': crowding['concentration_level'],
        'overlap_coefficient': round(overlap, 4),
        'avg_weight': crowding['avg_weight'],
        'total_weight': aggregation['total_weight'],
        'max_weight': aggregation['max_weight'],
        'weight_std': aggregation['weight_std'],
        'top_fund': aggregation['top_fund'],
        'top_5_weight_pct': crowding['top_5_weight_pct'],
        'quarter_distribution': aggregation['quarter_distribution'],
    }
