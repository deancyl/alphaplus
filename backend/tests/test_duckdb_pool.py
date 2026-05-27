"""
Tests for DuckDB connection pool.

Tests cover:
- Pool initialization
- Connection acquisition and release
- Health checks
- Concurrent access
- Write serialization
- Error handling
"""
import pytest
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from backend.core.duckdb_pool import DuckDBPool, DuckDBPoolManager, duckdb_pool_manager
from backend.core.config import settings


class TestDuckDBPool:
    """Test DuckDBPool class."""
    
    @pytest.fixture
    def pool(self):
        """Create a fresh pool for each test."""
        pool = DuckDBPool(
            max_readers=settings.duckdb_pool_readers,
            max_writers=settings.duckdb_pool_writers
        )
        yield pool
        pool.close()
    
    def test_pool_initialization(self, pool):
        """Test pool initializes with correct number of connections."""
        stats = pool.get_stats()
        
        assert stats["max_readers"] == settings.duckdb_pool_readers
        assert stats["max_writers"] == settings.duckdb_pool_writers
        assert stats["available_readers"] == settings.duckdb_pool_readers
        assert stats["available_writers"] == settings.duckdb_pool_writers
        assert stats["initialized"] is True
    
    def test_acquire_read_connection(self, pool):
        """Test acquiring a read connection."""
        conn = pool.acquire_read(timeout=1.0)
        
        assert conn is not None
        
        # Verify it works
        result = conn.execute("SELECT 1").fetchone()
        assert result == (1,)
        
        pool.release(conn, is_write=False)
        
        # Verify connection returned to pool
        stats = pool.get_stats()
        assert stats["available_readers"] == settings.duckdb_pool_readers
    
    def test_acquire_write_connection(self, pool):
        """Test acquiring a write connection."""
        conn = pool.acquire_write(timeout=1.0)
        
        assert conn is not None
        
        # Verify it works
        result = conn.execute("SELECT 1").fetchone()
        assert result == (1,)
        
        pool.release(conn, is_write=True)
        
        # Verify connection returned to pool
        stats = pool.get_stats()
        assert stats["available_writers"] == settings.duckdb_pool_writers
    
    def test_health_check(self, pool):
        """Test pool health check."""
        assert pool.health_check() is True
        
        # Close all connections
        pool.close()
        
        # Health check should fail after close
        assert pool.health_check() is False
    
    def test_connection_recycling_on_error(self, pool):
        """Test that unhealthy connections are replaced."""
        conn = pool.acquire_read(timeout=1.0)
        
        # Close the connection to make it unhealthy
        conn.close()
        
        # Release it back
        pool.release(conn, is_write=False)
        
        # Acquire again - should get a new healthy connection
        conn2 = pool.acquire_read(timeout=1.0)
        result = conn2.execute("SELECT 1").fetchone()
        assert result == (1,)
        
        pool.release(conn2, is_write=False)
    
    def test_concurrent_read_access(self, pool):
        """Test multiple threads can read concurrently."""
        results = []
        errors = []
        
        def read_query(thread_id):
            try:
                conn = pool.acquire_read(timeout=5.0)
                result = conn.execute("SELECT ? as thread_id", [thread_id]).fetchone()
                results.append(result[0])
                pool.release(conn, is_write=False)
            except Exception as e:
                errors.append(str(e))
        
        # Run 10 concurrent reads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_query, i) for i in range(10)]
            for future in futures:
                future.result(timeout=10)
        
        assert len(errors) == 0
        assert len(results) == 10
        assert set(results) == set(range(10))
    
    def test_pool_exhaustion_timeout(self, pool):
        """Test timeout when pool is exhausted."""
        # Acquire all read connections
        connections = []
        for _ in range(settings.duckdb_pool_readers):
            connections.append(pool.acquire_read(timeout=1.0))
        
        # Try to acquire one more - should timeout
        with pytest.raises(TimeoutError):
            pool.acquire_read(timeout=0.5)
        
        # Release connections
        for conn in connections:
            pool.release(conn, is_write=False)
    
    def test_pool_close(self, pool):
        """Test pool closes all connections."""
        pool.close()
        
        stats = pool.get_stats()
        assert stats["available_readers"] == 0
        assert stats["available_writers"] == 0


class TestDuckDBPoolManager:
    """Test DuckDBPoolManager singleton."""
    
    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """Reset manager before and after each test."""
        duckdb_pool_manager.close()
        duckdb_pool_manager._pool = None
        duckdb_pool_manager._write_lock = None
        yield
        duckdb_pool_manager.close()
        duckdb_pool_manager._pool = None
        duckdb_pool_manager._write_lock = None
    
    def test_singleton_pattern(self):
        """Test that manager is a singleton."""
        manager1 = DuckDBPoolManager()
        manager2 = DuckDBPoolManager()
        
        assert manager1 is manager2
        assert manager1 is duckdb_pool_manager
    
    def test_initialize(self):
        """Test manager initialization."""
        duckdb_pool_manager.initialize(
            max_readers=settings.duckdb_pool_readers,
            max_writers=settings.duckdb_pool_writers
        )
        
        assert duckdb_pool_manager._pool is not None
        assert duckdb_pool_manager._write_lock is not None
        
        stats = duckdb_pool_manager.get_stats()
        assert stats["max_readers"] == settings.duckdb_pool_readers
        assert stats["max_writers"] == settings.duckdb_pool_writers
    
    def test_get_pool_before_init(self):
        """Test get_pool raises error if not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            duckdb_pool_manager.get_pool()
    
    @pytest.mark.asyncio
    async def test_async_read_query(self):
        """Test async read query execution."""
        duckdb_pool_manager.initialize(
            max_readers=settings.duckdb_pool_readers,
            max_writers=settings.duckdb_pool_writers
        )
        
        result = await duckdb_pool_manager.execute_read("SELECT 1 as value")
        assert result == [(1,)]
    
    @pytest.mark.asyncio
    async def test_async_write_query(self):
        """Test async write query execution with serialization."""
        duckdb_pool_manager.initialize(
            max_readers=settings.duckdb_pool_readers,
            max_writers=settings.duckdb_pool_writers
        )
        
        # Create test table
        await duckdb_pool_manager.execute_write("""
            CREATE TABLE IF NOT EXISTS test_pool_write (
                id INTEGER,
                value VARCHAR
            )
        """)
        
        # Insert data
        rows = await duckdb_pool_manager.execute_write(
            "INSERT INTO test_pool_write VALUES (?, ?)",
            [1, "test"]
        )
        assert rows >= 0
        
        # Verify insert
        result = await duckdb_pool_manager.execute_read(
            "SELECT * FROM test_pool_write WHERE id = ?",
            [1]
        )
        assert len(result) == 1
        assert result[0] == (1, "test")
        
        # Cleanup
        await duckdb_pool_manager.execute_write("DROP TABLE test_pool_write")
    
    @pytest.mark.asyncio
    async def test_concurrent_writes_serialized(self):
        """Test that concurrent writes are serialized via lock."""
        duckdb_pool_manager.initialize(
            max_readers=settings.duckdb_pool_readers,
            max_writers=settings.duckdb_pool_writers
        )
        
        # Create test table
        await duckdb_pool_manager.execute_write("""
            CREATE TABLE IF NOT EXISTS test_concurrent (
                id INTEGER,
                thread_id INTEGER
            )
        """)
        
        # Run 10 concurrent writes
        async def write_value(i):
            await duckdb_pool_manager.execute_write(
                "INSERT INTO test_concurrent VALUES (?, ?)",
                [i, i]
            )
        
        tasks = [write_value(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        # Verify all writes succeeded
        result = await duckdb_pool_manager.execute_read(
            "SELECT COUNT(*) FROM test_concurrent"
        )
        assert result[0][0] == 10
        
        # Cleanup
        await duckdb_pool_manager.execute_write("DROP TABLE test_concurrent")
    
    @pytest.mark.asyncio
    async def test_acquire_read_context_manager(self):
        """Test async context manager for read connections."""
        duckdb_pool_manager.initialize(
            max_readers=settings.duckdb_pool_readers,
            max_writers=settings.duckdb_pool_writers
        )
        
        async with duckdb_pool_manager.acquire_read() as conn:
            result = conn.execute("SELECT 1").fetchone()
            assert result == (1,)
        
        # Connection should be returned to pool
        stats = duckdb_pool_manager.get_stats()
        assert stats["available_readers"] == settings.duckdb_pool_readers
    
    @pytest.mark.asyncio
    async def test_acquire_write_context_manager(self):
        """Test async context manager for write connections."""
        duckdb_pool_manager.initialize(
            max_readers=settings.duckdb_pool_readers,
            max_writers=settings.duckdb_pool_writers
        )
        
        async with duckdb_pool_manager.acquire_write() as conn:
            result = conn.execute("SELECT 1").fetchone()
            assert result == (1,)
        
        # Connection should be returned to pool
        stats = duckdb_pool_manager.get_stats()
        assert stats["available_writers"] == settings.duckdb_pool_writers
    
    def test_health_check(self):
        """Test manager health check."""
        # Not initialized
        assert duckdb_pool_manager.health_check() is False
        
        # Initialized
        duckdb_pool_manager.initialize(
            max_readers=settings.duckdb_pool_readers,
            max_writers=settings.duckdb_pool_writers
        )
        assert duckdb_pool_manager.health_check() is True
        
        # Closed
        duckdb_pool_manager.close()
        assert duckdb_pool_manager.health_check() is False
    
    def test_close(self):
        """Test manager close."""
        duckdb_pool_manager.initialize(
            max_readers=settings.duckdb_pool_readers,
            max_writers=settings.duckdb_pool_writers
        )
        
        duckdb_pool_manager.close()
        
        assert duckdb_pool_manager._pool is None
        assert duckdb_pool_manager._write_lock is None


class TestConnectionPoolIntegration:
    """Integration tests for connection pool with actual queries."""
    
    @pytest.fixture(autouse=True)
    def setup_pool(self):
        """Setup and teardown pool for integration tests."""
        duckdb_pool_manager.close()
        duckdb_pool_manager._pool = None
        duckdb_pool_manager._write_lock = None
        
        duckdb_pool_manager.initialize(
            max_readers=settings.duckdb_pool_readers,
            max_writers=settings.duckdb_pool_writers
        )
        
        yield
        
        duckdb_pool_manager.close()
        duckdb_pool_manager._pool = None
        duckdb_pool_manager._write_lock = None
    
    @pytest.mark.asyncio
    async def test_holdings_table_operations(self):
        """Test CRUD operations on fund_portfolio_holdings table."""
        # Clean up test data first
        await duckdb_pool_manager.execute_write(
            "DELETE FROM fund_portfolio_holdings WHERE fund_code = ?",
            ['TEST001']
        )
        
        # Insert test data
        await duckdb_pool_manager.execute_write("""
            INSERT INTO fund_portfolio_holdings 
            (fund_code, quarter_date, stock_code, stock_name, holding_ratio)
            VALUES (?, ?, ?, ?, ?)
        """, ['TEST001', '2024-03-31', '600519', '贵州茅台', 5.5])
        
        # Read data
        result = await duckdb_pool_manager.execute_read(
            "SELECT * FROM fund_portfolio_holdings WHERE fund_code = ?",
            ['TEST001']
        )
        assert len(result) == 1
        assert result[0][0] == 'TEST001'
        assert result[0][2] == '600519'
        
        # Delete data
        await duckdb_pool_manager.execute_write(
            "DELETE FROM fund_portfolio_holdings WHERE fund_code = ?",
            ['TEST001']
        )
        
        # Verify delete
        result = await duckdb_pool_manager.execute_read(
            "SELECT * FROM fund_portfolio_holdings WHERE fund_code = ?",
            ['TEST001']
        )
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_parallel_reads_with_write(self):
        """Test parallel reads don't block writes and vice versa."""
        # Clean up test data first
        await duckdb_pool_manager.execute_write(
            "DELETE FROM fund_portfolio_holdings WHERE fund_code LIKE 'PARALLEL%'"
        )
        
        # Insert test data
        await duckdb_pool_manager.execute_write("""
            INSERT INTO fund_portfolio_holdings 
            (fund_code, quarter_date, stock_code, stock_name, holding_ratio)
            VALUES (?, ?, ?, ?, ?)
        """, ['PARALLEL001', '2024-03-31', '000001', '平安银行', 3.0])
        
        # Run parallel reads and a write
        async def read_query():
            return await duckdb_pool_manager.execute_read(
                "SELECT COUNT(*) FROM fund_portfolio_holdings"
            )
        
        async def write_query():
            await duckdb_pool_manager.execute_write("""
                INSERT INTO fund_portfolio_holdings 
                (fund_code, quarter_date, stock_code, stock_name, holding_ratio)
                VALUES (?, ?, ?, ?, ?)
            """, ['PARALLEL002', '2024-03-31', '000002', '万科A', 2.0])
        
        # Execute in parallel
        results = await asyncio.gather(
            read_query(),
            read_query(),
            write_query(),
            read_query()
        )
        
        # All should succeed
        assert len(results) == 4
        
        # Cleanup
        await duckdb_pool_manager.execute_write(
            "DELETE FROM fund_portfolio_holdings WHERE fund_code LIKE 'PARALLEL%'"
        )


class TestPoolSettings:
    """Test pool configuration from settings."""
    
    def test_settings_exist(self):
        """Test that pool settings are defined."""
        assert hasattr(settings, 'duckdb_pool_readers')
        assert hasattr(settings, 'duckdb_pool_writers')
        assert settings.duckdb_pool_readers == 4
        assert settings.duckdb_pool_writers == 1
    
    def test_pool_uses_settings(self):
        """Test that pool uses settings values."""
        pool = DuckDBPool(
            max_readers=settings.duckdb_pool_readers,
            max_writers=settings.duckdb_pool_writers
        )
        
        stats = pool.get_stats()
        assert stats["max_readers"] == settings.duckdb_pool_readers
        assert stats["max_writers"] == settings.duckdb_pool_writers
        
        pool.close()
