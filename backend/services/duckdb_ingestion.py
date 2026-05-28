"""
DuckDB data ingestion and OLAP query functions.

Uses connection pool for thread-safe concurrent access.
"""
from datetime import date
from typing import List, Dict, Optional
import duckdb
from backend.core.duckdb_pool import duckdb_pool_manager
import logging

logger = logging.getLogger(__name__)


async def insert_holdings_batch(holdings: List[Dict]) -> int:
    """
    Insert fund portfolio holdings batch into DuckDB.
    
    Uses write lock for serialized writes to prevent concurrency issues.
    
    Args:
        holdings: List of holding dicts with keys:
            - fund_code: str
            - quarter_date: date
            - stock_code: str
            - stock_name: str
            - holding_ratio: float
            - holding_value: Optional[float]
            - holding_change: Optional[str]
    
    Returns:
        Number of rows inserted
    """
    if not holdings:
        return 0
    
    # Delete existing records for same fund+quarter (serialized write)
    fund_code = holdings[0]['fund_code']
    quarter_date = holdings[0]['quarter_date']
    
    await duckdb_pool_manager.execute_write(
        "DELETE FROM fund_portfolio_holdings WHERE fund_code = ? AND quarter_date = ?",
        [fund_code, quarter_date]
    )
    
    # Insert new records (serialized write)
    rows_inserted = 0
    for h in holdings:
        await duckdb_pool_manager.execute_write("""
            INSERT INTO fund_portfolio_holdings 
            (fund_code, quarter_date, stock_code, stock_name, holding_ratio, holding_value, holding_change)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            h['fund_code'],
            h['quarter_date'],
            h['stock_code'],
            h['stock_name'],
            h['holding_ratio'],
            h.get('holding_value'),
            h.get('holding_change')
        ])
        rows_inserted += 1
    
    logger.info(f"Inserted {rows_inserted} holdings records")
    return rows_inserted


async def search_funds_by_stock(stock_code: str, limit: int = 100) -> Dict:
    """
    Reverse lookup: Find all funds holding a specific stock.
    
    Uses read connection from pool for parallel query execution.
    
    Args:
        stock_code: Stock code to search (e.g., '600519')
        limit: Maximum number of funds to return
    
    Returns:
        Dict with stock info and list of fund holdings sorted by holding_ratio DESC
    """
    result = await duckdb_pool_manager.execute_read("""
        SELECT 
            fund_code,
            stock_name,
            quarter_date,
            holding_ratio,
            holding_value,
            COUNT(*) OVER() as total_funds,
            SUM(holding_ratio) OVER() as aggregate_exposure
        FROM fund_portfolio_holdings
        WHERE stock_code = ?
        ORDER BY holding_ratio DESC
        LIMIT ?
    """, [stock_code, limit])
    
    if not result:
        return {
            'stock_code': stock_code,
            'stock_name': '',
            'total_funds': 0,
            'aggregate_exposure': 0.0,
            'funds': []
        }
    
    # Get aggregate stats from first row
    total_funds = result[0][5] if result else 0
    aggregate_exposure = result[0][6] if result else 0.0
    
    funds = [{
        'fund_code': row[0],
        'stock_name': row[1],
        'quarter_date': str(row[2]),
        'holding_ratio': row[3],
        'holding_value': row[4],
    } for row in result]
    
    return {
        'stock_code': stock_code,
        'stock_name': funds[0]['stock_name'] if funds else '',
        'total_funds': total_funds,
        'aggregate_exposure': aggregate_exposure,
        'funds': funds
    }


async def aggregate_by_stock(stock_code: str) -> Dict:
    """
    Aggregate holdings statistics for a specific stock across all funds.
    
    Provides comprehensive aggregation metrics for crowding analysis.
    
    Args:
        stock_code: Stock code to aggregate (e.g., '600519')
    
    Returns:
        Dict with aggregated statistics:
            - stock_code: str
            - total_funds: int
            - total_weight: float (sum of holding ratios)
            - avg_weight: float
            - max_weight: float
            - weight_std: float
            - top_fund: str (fund_code with highest weight)
            - quarter_distribution: Dict[str, int] (funds count per quarter)
    """
    result = await duckdb_pool_manager.execute_read("""
        SELECT 
            fund_code,
            quarter_date,
            holding_ratio,
            stock_name
        FROM fund_portfolio_holdings
        WHERE stock_code = ?
        ORDER BY holding_ratio DESC
    """, [stock_code])
    
    if not result:
        return {
            'stock_code': stock_code,
            'total_funds': 0,
            'total_weight': 0.0,
            'avg_weight': 0.0,
            'max_weight': 0.0,
            'weight_std': 0.0,
            'top_fund': '',
            'quarter_distribution': {}
        }
    
    weights = [row[2] for row in result]
    total_weight = sum(weights)
    avg_weight = total_weight / len(weights)
    max_weight = max(weights)
    
    # Calculate standard deviation
    if len(weights) > 1:
        variance = sum((w - avg_weight) ** 2 for w in weights) / len(weights)
        weight_std = variance ** 0.5
    else:
        weight_std = 0.0
    
    top_fund = result[0][0] if result else ''
    stock_name = result[0][3] if result else ''
    
    # Quarter distribution
    quarter_dist = {}
    for row in result:
        quarter = str(row[1])
        quarter_dist[quarter] = quarter_dist.get(quarter, 0) + 1
    
    return {
        'stock_code': stock_code,
        'stock_name': stock_name,
        'total_funds': len(result),
        'total_weight': round(total_weight, 4),
        'avg_weight': round(avg_weight, 4),
        'max_weight': round(max_weight, 4),
        'weight_std': round(weight_std, 4),
        'top_fund': top_fund,
        'quarter_distribution': quarter_dist
    }


async def calculate_crowding_score(stock_code: str) -> Dict:
    """
    Calculate crowding score for institutional holdings.
    
    Crowding score measures concentration risk based on:
    - Number of funds holding the stock
    - Weight concentration (HHI - Herfindahl-Hirschman Index)
    - Overlap degree between funds
    
    Args:
        stock_code: Stock code to analyze
    
    Returns:
        Dict with crowding metrics:
            - stock_code: str
            - crowding_score: float (0-100)
            - hhi_index: float (0-10000)
            - concentration_level: str (low/medium/high/extreme)
            - num_funds: int
            - avg_weight: float
    """
    aggregation = await aggregate_by_stock(stock_code)
    
    if aggregation['total_funds'] == 0:
        return {
            'stock_code': stock_code,
            'crowding_score': 0.0,
            'hhi_index': 0.0,
            'concentration_level': 'none',
            'num_funds': 0,
            'avg_weight': 0.0,
            'top_5_weight_pct': 0.0
        }
    
    # Calculate HHI (Herfindahl-Hirschman Index)
    weights = []
    result = await duckdb_pool_manager.execute_read("""
        SELECT holding_ratio
        FROM fund_portfolio_holdings
        WHERE stock_code = ?
        ORDER BY holding_ratio DESC
    """, [stock_code])
    
    if result:
        total_weight = sum(row[0] for row in result)
        weights = [(row[0] / total_weight * 100) if total_weight > 0 else 0 for row in result]
    
    hhi = sum(w ** 2 for w in weights)
    
    # Normalize crowding score (0-100 scale)
    # HHI range: 0 (perfect competition) to 10000 (monopoly)
    # Map to 0-100 crowding score
    crowding_score = min(100, hhi / 100)
    
    # Calculate top 5 concentration
    top_5_weights = weights[:5] if len(weights) >= 5 else weights
    top_5_weight_pct = sum(top_5_weights)
    
    # Determine concentration level
    if crowding_score < 15:
        concentration_level = 'low'
    elif crowding_score < 40:
        concentration_level = 'medium'
    elif crowding_score < 70:
        concentration_level = 'high'
    else:
        concentration_level = 'extreme'
    
    return {
        'stock_code': stock_code,
        'crowding_score': round(crowding_score, 2),
        'hhi_index': round(hhi, 2),
        'concentration_level': concentration_level,
        'num_funds': aggregation['total_funds'],
        'avg_weight': aggregation['avg_weight'],
        'top_5_weight_pct': round(top_5_weight_pct, 2)
    }
