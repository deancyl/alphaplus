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
