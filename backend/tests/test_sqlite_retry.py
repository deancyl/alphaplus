"""
Unit tests for SQLite retry decorator with exponential backoff.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import sqlite3
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.exc import OperationalError

from backend.core.database import retry_on_sqlite_busy


class TestSQLiteRetryDecorator:
    """Tests for retry_on_sqlite_busy decorator."""
    
    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        """Test that successful operation doesn't retry."""
        call_count = 0
        
        @retry_on_sqlite_busy(max_retries=3)
        async def successful_operation():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await successful_operation()
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_lock_then_success(self):
        """Test retry on SQLITE_BUSY then success."""
        call_count = 0
        
        @retry_on_sqlite_busy(max_retries=3, base_delay_ms=10, max_delay_ms=100, jitter=False)
        async def locked_then_success():
            nonlocal call_count
            call_count += 1
            
            if call_count < 2:
                orig_error = sqlite3.OperationalError("database is locked")
                orig_error.sqlite_errorcode = sqlite3.SQLITE_BUSY
                raise OperationalError("database is locked", orig_error, None)
            
            return "success"
        
        result = await locked_then_success()
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test exception raised after max retries."""
        call_count = 0
        
        @retry_on_sqlite_busy(max_retries=3, base_delay_ms=10, max_delay_ms=100, jitter=False)
        async def always_locked():
            nonlocal call_count
            call_count += 1
            
            orig_error = sqlite3.OperationalError("database is locked")
            orig_error.sqlite_errorcode = sqlite3.SQLITE_BUSY
            raise OperationalError("database is locked", orig_error, None)
        
        with pytest.raises(OperationalError) as exc_info:
            await always_locked()
        
        assert "database is locked" in str(exc_info.value)
        assert call_count == 4
    
    @pytest.mark.asyncio
    async def test_non_lock_error_no_retry(self):
        """Test that non-SQLITE_BUSY errors don't retry."""
        call_count = 0
        
        @retry_on_sqlite_busy(max_retries=3)
        async def non_lock_error():
            nonlocal call_count
            call_count += 1
            
            orig_error = sqlite3.OperationalError("no such table")
            orig_error.sqlite_errorcode = sqlite3.SQLITE_ERROR
            raise OperationalError("no such table", orig_error, None)
        
        with pytest.raises(OperationalError) as exc_info:
            await non_lock_error()
        
        assert "no such table" in str(exc_info.value)
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_other_exception_no_retry(self):
        """Test that non-OperationalError exceptions don't retry."""
        call_count = 0
        
        @retry_on_sqlite_busy(max_retries=3)
        async def other_exception():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid data")
        
        with pytest.raises(ValueError) as exc_info:
            await other_exception()
        
        assert "Invalid data" in str(exc_info.value)
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_formula(self):
        """Test exponential backoff delay calculation."""
        delays = []
        
        @retry_on_sqlite_busy(max_retries=3, base_delay_ms=100, max_delay_ms=1000, jitter=False)
        async def track_delays():
            if len(delays) < 4:
                orig_error = sqlite3.OperationalError("database is locked")
                orig_error.sqlite_errorcode = sqlite3.SQLITE_BUSY
                raise OperationalError("database is locked", orig_error, None)
            return "success"
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = lambda d: delays.append(d)
            
            with pytest.raises(OperationalError):
                await track_delays()
            
            assert len(delays) == 3
            assert delays[0] == pytest.approx(0.1, rel=0.01)
            assert delays[1] == pytest.approx(0.2, rel=0.01)
            assert delays[2] == pytest.approx(0.4, rel=0.01)
    
    @pytest.mark.asyncio
    async def test_jitter_added(self):
        """Test that jitter is added to delay."""
        delays = []
        
        @retry_on_sqlite_busy(max_retries=2, base_delay_ms=100, max_delay_ms=1000, jitter=True)
        async def track_jitter():
            if len(delays) < 3:
                orig_error = sqlite3.OperationalError("database is locked")
                orig_error.sqlite_errorcode = sqlite3.SQLITE_BUSY
                raise OperationalError("database is locked", orig_error, None)
            return "success"
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = lambda d: delays.append(d)
            
            with pytest.raises(OperationalError):
                await track_jitter()
            
            assert len(delays) == 2
            assert delays[0] >= 0.1
            assert delays[0] <= 0.2
            assert delays[1] >= 0.2
            assert delays[1] <= 0.3
    
    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        delays = []
        
        @retry_on_sqlite_busy(max_retries=10, base_delay_ms=100, max_delay_ms=500, jitter=False)
        async def test_max_cap():
            if len(delays) < 11:
                orig_error = sqlite3.OperationalError("database is locked")
                orig_error.sqlite_errorcode = sqlite3.SQLITE_BUSY
                raise OperationalError("database is locked", orig_error, None)
            return "success"
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = lambda d: delays.append(d)
            
            with pytest.raises(OperationalError):
                await test_max_cap()
            
            for delay in delays:
                assert delay <= 0.5
    
    @pytest.mark.asyncio
    async def test_configurable_max_retries(self):
        """Test configurable max_retries parameter."""
        call_count = 0
        
        @retry_on_sqlite_busy(max_retries=5, base_delay_ms=10, max_delay_ms=100, jitter=False)
        async def configurable_retries():
            nonlocal call_count
            call_count += 1
            
            orig_error = sqlite3.OperationalError("database is locked")
            orig_error.sqlite_errorcode = sqlite3.SQLITE_BUSY
            raise OperationalError("database is locked", orig_error, None)
        
        with pytest.raises(OperationalError):
            await configurable_retries()
        
        assert call_count == 6
    
    @pytest.mark.asyncio
    async def test_no_jitter_mode(self):
        """Test that jitter can be disabled."""
        delays = []
        
        @retry_on_sqlite_busy(max_retries=2, base_delay_ms=100, max_delay_ms=1000, jitter=False)
        async def no_jitter():
            if len(delays) < 3:
                orig_error = sqlite3.OperationalError("database is locked")
                orig_error.sqlite_errorcode = sqlite3.SQLITE_BUSY
                raise OperationalError("database is locked", orig_error, None)
            return "success"
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = lambda d: delays.append(d)
            
            with pytest.raises(OperationalError):
                await no_jitter()
            
            assert delays[0] == pytest.approx(0.1, rel=0.001)
            assert delays[1] == pytest.approx(0.2, rel=0.001)
    
    @pytest.mark.asyncio
    async def test_retry_with_success_after_multiple_attempts(self):
        """Test retry succeeds after multiple locked attempts."""
        call_count = 0
        
        @retry_on_sqlite_busy(max_retries=3, base_delay_ms=10, max_delay_ms=100, jitter=False)
        async def multi_locked_then_success():
            nonlocal call_count
            call_count += 1
            
            if call_count < 3:
                orig_error = sqlite3.OperationalError("database is locked")
                orig_error.sqlite_errorcode = sqlite3.SQLITE_BUSY
                raise OperationalError("database is locked", orig_error, None)
            
            return {"status": "saved", "id": 123}
        
        result = await multi_locked_then_success()
        assert result["status"] == "saved"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_database_locked_string_detection(self):
        """Test detection via 'database is locked' string."""
        call_count = 0
        
        @retry_on_sqlite_busy(max_retries=2, base_delay_ms=10, jitter=False)
        async def string_detection():
            nonlocal call_count
            call_count += 1
            
            if call_count < 2:
                orig_error = sqlite3.OperationalError("database is locked")
                raise OperationalError("database is locked", orig_error, None)
            
            return "success"
        
        result = await string_detection()
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""
        @retry_on_sqlite_busy(max_retries=3)
        async def documented_function():
            """This is a documented function."""
            return "success"
        
        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is a documented function."
    
    @pytest.mark.asyncio
    async def test_async_context_preserved(self):
        """Test that async context is preserved through retries."""
        results = []
        
        @retry_on_sqlite_busy(max_retries=2, base_delay_ms=10, jitter=False)
        async def context_test():
            results.append(asyncio.current_task().get_name())
            
            if len(results) < 2:
                orig_error = sqlite3.OperationalError("database is locked")
                orig_error.sqlite_errorcode = sqlite3.SQLITE_BUSY
                raise OperationalError("database is locked", orig_error, None)
            
            return results
        
        task_name = asyncio.current_task().get_name()
        result = await context_test()
        
        assert all(name == task_name for name in result)
    
    @pytest.mark.asyncio
    async def test_concurrent_retries_different_timing(self):
        """Test that jitter adds randomness to retry delays."""
        delays_list = []
        
        for i in range(3):
            delays = []
            
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                mock_sleep.side_effect = lambda d: delays.append(d)
                
                @retry_on_sqlite_busy(max_retries=2, base_delay_ms=100, jitter=True)
                async def track():
                    orig_error = sqlite3.OperationalError("database is locked")
                    orig_error.sqlite_errorcode = sqlite3.SQLITE_BUSY
                    raise OperationalError("database is locked", orig_error, None)
                
                with pytest.raises(OperationalError):
                    await track()
                
                delays_list.append(delays.copy())
        
        assert len(delays_list) == 3
        assert all(len(d) == 2 for d in delays_list)
        assert delays_list[0] != delays_list[1] or delays_list[1] != delays_list[2] or delays_list[0] != delays_list[2]