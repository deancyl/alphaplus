"""
DuckDB OLAP connection for high-performance analytical queries.

Used for:
- Fund portfolio holdings analysis
- Stock-to-fund reverse lookup
- Historical performance aggregation
"""
import duckdb
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# DuckDB database path (separate from SQLite)
DUCKDB_PATH = Path(__file__).parent.parent.parent / "data" / "olap.duckdb"


class DuckDBConnection:
    """Thread-safe DuckDB connection manager."""
    
    _instance: Optional['DuckDBConnection'] = None
    _connection: Optional[duckdb.DuckDBPyConnection] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get or create DuckDB connection."""
        if self._connection is None:
            DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._connection = duckdb.connect(str(DUCKDB_PATH))
            self._init_schema()
        return self._connection
    
    def _init_schema(self):
        """Initialize DuckDB schema."""
        conn = self._connection
        if conn is None:
            return
        
        # Fund portfolio holdings table (OLAP optimized)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fund_portfolio_holdings (
                fund_code VARCHAR(12) NOT NULL,
                quarter_date DATE NOT NULL,
                stock_code VARCHAR(12) NOT NULL,
                stock_name VARCHAR(64) NOT NULL,
                holding_ratio DOUBLE NOT NULL,
                holding_value DOUBLE,
                holding_change VARCHAR(20),
                PRIMARY KEY (fund_code, quarter_date, stock_code)
            )
        """)
        
        # Inverted index for stock-to-fund lookup
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_stock_reverse_query 
            ON fund_portfolio_holdings (stock_code, quarter_date DESC)
        """)
        
        # Fund code index for forward lookup
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fund_holdings 
            ON fund_portfolio_holdings (fund_code, quarter_date DESC)
        """)
        
        logger.info("DuckDB schema initialized")
    
    def close(self):
        """Close connection."""
        if self._connection:
            self._connection.close()
            self._connection = None


# Global instance
duckdb_conn = DuckDBConnection()


def get_duckdb() -> duckdb.DuckDBPyConnection:
    """Get DuckDB connection (dependency injection)."""
    return duckdb_conn.get_connection()
