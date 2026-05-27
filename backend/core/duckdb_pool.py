"""
DuckDB connection pool for thread-safe concurrent access.

Architecture:
- 4 read-only connections for parallel queries
- 1 write connection with asyncio.Lock for serialized writes
- Connection health checks before use
- Automatic connection release via context managers
"""
import asyncio
import duckdb
from pathlib import Path
from typing import Optional, List, Any
from contextlib import asynccontextmanager
from queue import Queue, Empty
import logging
import threading

logger = logging.getLogger(__name__)

# DuckDB database path (separate from SQLite)
DUCKDB_PATH = Path(__file__).parent.parent.parent / "data" / "olap.duckdb"


class DuckDBPool:
    """
    Thread-safe DuckDB connection pool.
    
    Features:
    - Separate pools for read and write connections
    - Read connections: parallel access (max_readers)
    - Write connections: serialized via asyncio.Lock
    - Health check before each use
    - Connection recycling on error
    """
    
    def __init__(self, max_readers: int = 4, max_writers: int = 1):
        """
        Initialize connection pool.
        
        Args:
            max_readers: Maximum read-only connections (default: 4)
            max_writers: Maximum write connections (default: 1)
        """
        self.max_readers = max_readers
        self.max_writers = max_writers
        
        # Connection pools using thread-safe Queue
        self._read_pool: Queue = Queue(maxsize=max_readers)
        self._write_pool: Queue = Queue(maxsize=max_writers)
        
        # Write lock for serialized writes
        self._write_lock = asyncio.Lock()
        
        # Thread lock for pool initialization
        self._init_lock = threading.Lock()
        self._initialized = False
        
        # Initialize pools
        self._initialize_pools()
    
    def _create_connection(self, read_only: bool = False) -> duckdb.DuckDBPyConnection:
        """
        Create a new DuckDB connection.
        
        Note: DuckDB doesn't support mixing read-only and read-write connections
        to the same database file. All connections are read-write for simplicity.
        
        Args:
            read_only: Ignored (kept for API compatibility)
            
        Returns:
            DuckDB connection
        """
        DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # All connections are read-write (DuckDB limitation)
        conn = duckdb.connect(str(DUCKDB_PATH))
        
        # Initialize schema for all connections
        self._init_schema(conn)
        
        return conn
    
    def _init_schema(self, conn: duckdb.DuckDBPyConnection):
        """Initialize DuckDB schema for write connections."""
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
    
    def _initialize_pools(self):
        """Initialize connection pools."""
        with self._init_lock:
            if self._initialized:
                return
            
            # Create read connections
            for i in range(self.max_readers):
                try:
                    conn = self._create_connection(read_only=True)
                    self._read_pool.put(conn)
                    logger.debug(f"Created read connection {i+1}/{self.max_readers}")
                except Exception as e:
                    logger.error(f"Failed to create read connection: {e}")
            
            # Create write connections
            for i in range(self.max_writers):
                try:
                    conn = self._create_connection(read_only=False)
                    self._write_pool.put(conn)
                    logger.debug(f"Created write connection {i+1}/{self.max_writers}")
                except Exception as e:
                    logger.error(f"Failed to create write connection: {e}")
            
            self._initialized = True
            logger.info(f"DuckDB pool initialized: {self.max_readers} readers, {self.max_writers} writers")
    
    def acquire_read(self, timeout: float = 5.0) -> duckdb.DuckDBPyConnection:
        """
        Acquire a read-only connection from the pool.
        
        Args:
            timeout: Maximum time to wait for connection (seconds)
            
        Returns:
            DuckDB read-only connection
            
        Raises:
            TimeoutError: If no connection available within timeout
        """
        try:
            conn = self._read_pool.get(timeout=timeout)
            
            # Health check
            if not self._health_check(conn):
                logger.warning("Read connection failed health check, creating new one")
                conn.close()
                conn = self._create_connection(read_only=True)
            
            return conn
        except Empty:
            raise TimeoutError(f"No read connection available within {timeout}s")
    
    def acquire_write(self, timeout: float = 10.0) -> duckdb.DuckDBPyConnection:
        """
        Acquire a write connection from the pool.
        
        Note: Caller must hold _write_lock before calling this method.
        
        Args:
            timeout: Maximum time to wait for connection (seconds)
            
        Returns:
            DuckDB write connection
            
        Raises:
            TimeoutError: If no connection available within timeout
        """
        try:
            conn = self._write_pool.get(timeout=timeout)
            
            # Health check
            if not self._health_check(conn):
                logger.warning("Write connection failed health check, creating new one")
                conn.close()
                conn = self._create_connection(read_only=False)
            
            return conn
        except Empty:
            raise TimeoutError(f"No write connection available within {timeout}s")
    
    def release(self, conn: duckdb.DuckDBPyConnection, is_write: bool = False):
        """
        Release a connection back to the pool.
        
        Args:
            conn: Connection to release
            is_write: Whether this is a write connection
        """
        try:
            # Check if connection is still valid
            if conn is None:
                conn = self._create_connection(read_only=is_write)
            
            if is_write:
                self._write_pool.put(conn, timeout=1.0)
            else:
                self._read_pool.put(conn, timeout=1.0)
        except Exception as e:
            logger.error(f"Failed to release connection: {e}")
            # Try to close the connection if we can't return it
            try:
                if conn:
                    conn.close()
            except:
                pass
    
    def _health_check(self, conn: duckdb.DuckDBPyConnection) -> bool:
        """
        Check if connection is healthy.
        
        Args:
            conn: Connection to check
            
        Returns:
            True if healthy, False otherwise
        """
        try:
            if conn is None:
                return False
            
            # Simple query to verify connection
            conn.execute("SELECT 1").fetchone()
            return True
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False
    
    def health_check(self) -> bool:
        """
        Check overall pool health.
        
        Returns:
            True if at least one read and one write connection is healthy
        """
        read_healthy = False
        write_healthy = False
        
        # Check read pool
        try:
            conn = self.acquire_read(timeout=1.0)
            read_healthy = self._health_check(conn)
            self.release(conn, is_write=False)
        except:
            pass
        
        # Check write pool
        try:
            conn = self.acquire_write(timeout=1.0)
            write_healthy = self._health_check(conn)
            self.release(conn, is_write=True)
        except:
            pass
        
        return read_healthy and write_healthy
    
    def close(self):
        """Close all connections in the pool."""
        # Close read connections
        while not self._read_pool.empty():
            try:
                conn = self._read_pool.get_nowait()
                if conn and not conn.closed:
                    conn.close()
            except:
                pass
        
        # Close write connections
        while not self._write_pool.empty():
            try:
                conn = self._write_pool.get_nowait()
                if conn and not conn.closed:
                    conn.close()
            except:
                pass
        
        logger.info("DuckDB pool closed")
    
    def get_stats(self) -> dict:
        """
        Get pool statistics.
        
        Returns:
            Dict with pool stats
        """
        return {
            "max_readers": self.max_readers,
            "max_writers": self.max_writers,
            "available_readers": self._read_pool.qsize(),
            "available_writers": self._write_pool.qsize(),
            "initialized": self._initialized
        }


class DuckDBPoolManager:
    """
    Singleton manager for DuckDB connection pool.
    
    Provides high-level async interface for database operations.
    """
    
    _instance: Optional['DuckDBPoolManager'] = None
    _pool: Optional[DuckDBPool] = None
    _write_lock: Optional[asyncio.Lock] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self, max_readers: int = 4, max_writers: int = 1):
        """
        Initialize the connection pool.
        
        Args:
            max_readers: Maximum read connections
            max_writers: Maximum write connections
        """
        if self._pool is None:
            self._pool = DuckDBPool(max_readers=max_readers, max_writers=max_writers)
            self._write_lock = asyncio.Lock()
            logger.info(f"DuckDBPoolManager initialized with {max_readers} readers, {max_writers} writers")
    
    def get_pool(self) -> DuckDBPool:
        """
        Get the connection pool.
        
        Returns:
            DuckDBPool instance
            
        Raises:
            RuntimeError: If pool not initialized
        """
        if self._pool is None:
            raise RuntimeError("DuckDBPoolManager not initialized. Call initialize() first.")
        return self._pool
    
    @asynccontextmanager
    async def acquire_read(self):
        """
        Async context manager for read connections.
        
        Usage:
            async with pool_manager.acquire_read() as conn:
                result = conn.execute("SELECT * FROM table").fetchall()
        """
        pool = self.get_pool()
        conn = None
        try:
            # Run blocking acquire in thread pool
            conn = await asyncio.get_event_loop().run_in_executor(
                None, pool.acquire_read
            )
            yield conn
        finally:
            if conn:
                await asyncio.get_event_loop().run_in_executor(
                    None, pool.release, conn, False
                )
    
    @asynccontextmanager
    async def acquire_write(self):
        """
        Async context manager for write connections with serialization.
        
        Usage:
            async with pool_manager.acquire_write() as conn:
                conn.execute("INSERT INTO table VALUES (?)", [value])
        """
        pool = self.get_pool()
        conn = None
        
        # Acquire write lock to serialize writes
        if self._write_lock is None:
            raise RuntimeError("DuckDBPoolManager not initialized. Call initialize() first.")
        async with self._write_lock:
            try:
                # Run blocking acquire in thread pool
                conn = await asyncio.get_event_loop().run_in_executor(
                    None, pool.acquire_write
                )
                yield conn
            finally:
                if conn:
                    await asyncio.get_event_loop().run_in_executor(
                        None, pool.release, conn, True
                    )
    
    async def execute_read(self, query: str, params: Optional[List[Any]] = None) -> List[tuple]:
        """
        Execute a read query and return results.
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            List of result tuples
        """
        async with self.acquire_read() as conn:
            # Run blocking execute in thread pool
            loop = asyncio.get_event_loop()
            if params:
                result = await loop.run_in_executor(
                    None, conn.execute, query, params
                )
            else:
                result = await loop.run_in_executor(
                    None, conn.execute, query
                )
            return await loop.run_in_executor(None, result.fetchall)
    
    async def execute_write(self, query: str, params: Optional[List[Any]] = None) -> int:
        """
        Execute a write query (serialized via lock).
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            Number of affected rows (best effort, may be 0 for some operations)
        """
        async with self.acquire_write() as conn:
            # Run blocking execute in thread pool
            loop = asyncio.get_event_loop()
            if params:
                result = await loop.run_in_executor(
                    None, conn.execute, query, params
                )
            else:
                result = await loop.run_in_executor(
                    None, conn.execute, query
                )
            # DuckDB doesn't have changes() like SQLite
            # Return 0 for success, actual row count not easily available
            return 0
    
    def health_check(self) -> bool:
        """
        Check pool health.
        
        Returns:
            True if pool is healthy
        """
        if self._pool is None:
            return False
        return self._pool.health_check()
    
    def close(self):
        """Close the pool."""
        if self._pool:
            self._pool.close()
            self._pool = None
            self._write_lock = None
            logger.info("DuckDBPoolManager closed")
    
    def get_stats(self) -> dict:
        """
        Get pool statistics.
        
        Returns:
            Dict with pool stats
        """
        if self._pool is None:
            return {"status": "not_initialized"}
        return self._pool.get_stats()


# Global instance
duckdb_pool_manager = DuckDBPoolManager()


def get_duckdb_pool() -> DuckDBPool:
    """
    Get DuckDB connection pool (dependency injection).
    
    Returns:
        DuckDBPool instance
    """
    return duckdb_pool_manager.get_pool()
