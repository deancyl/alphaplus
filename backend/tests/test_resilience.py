"""
Unit tests for resilience module retry logic.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from backend.services.resilience import (
    RetryConfig,
    ErrorType,
    classify_error,
    retry_with_backoff,
)


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_retries == 5
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = RetryConfig(
            max_retries=3,
            base_delay=0.5,
            max_delay=10.0,
            exponential_base=3.0,
            jitter=False
        )
        assert config.max_retries == 3
        assert config.base_delay == 0.5
        assert config.max_delay == 10.0
        assert config.exponential_base == 3.0
        assert config.jitter is False
    
    def test_calculate_delay_first_attempt(self):
        """Test delay calculation for first attempt."""
        config = RetryConfig(jitter=False)
        delay = config.calculate_delay(0)
        assert delay == 1.0
    
    def test_calculate_delay_exponential(self):
        """Test exponential backoff formula."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0
        assert config.calculate_delay(3) == 8.0
        assert config.calculate_delay(4) == 16.0
    
    def test_calculate_delay_max_cap(self):
        """Test that delay is capped at max_delay."""
        config = RetryConfig(base_delay=1.0, max_delay=10.0, exponential_base=2.0, jitter=False)
        delay = config.calculate_delay(10)
        assert delay == 10.0
    
    def test_calculate_delay_with_jitter(self):
        """Test that jitter adds random value between 0 and 1."""
        config = RetryConfig(jitter=True)
        with patch('backend.services.resilience.random.uniform', return_value=0.5):
            delay = config.calculate_delay(0)
            assert delay == 1.5


class TestErrorClassification:
    """Tests for error classification."""
    
    def test_network_error_timeout(self):
        """Test classification of timeout errors."""
        error = TimeoutError("Connection timeout")
        assert classify_error(error) == ErrorType.NETWORK_ERROR
    
    def test_network_error_connection(self):
        """Test classification of connection errors."""
        error = ConnectionError("Connection refused")
        assert classify_error(error) == ErrorType.NETWORK_ERROR
    
    def test_rate_limited_error(self):
        """Test classification of rate limit errors."""
        error = Exception("Too many requests - rate limit exceeded")
        assert classify_error(error) == ErrorType.RATE_LIMITED
    
    def test_auth_error_unauthorized(self):
        """Test classification of authentication errors."""
        error = PermissionError("Unauthorized - invalid API key")
        assert classify_error(error) == ErrorType.AUTH_ERROR
    
    def test_data_error_empty(self):
        """Test classification of data errors."""
        error = ValueError("No data found for symbol")
        assert classify_error(error) == ErrorType.DATA_ERROR
    
    def test_unknown_error(self):
        """Test classification of unknown errors."""
        error = RuntimeError("Something went wrong")
        assert classify_error(error) == ErrorType.UNKNOWN


class TestRetryWithBackoff:
    """Tests for retry_with_backoff decorator."""
    
    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        """Test that successful function doesn't retry."""
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_retries=3))
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await successful_func()
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test that function retries on failure."""
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_retries=3, base_delay=0.01, jitter=False))
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "success"
        
        result = await failing_func()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test that exception is raised after max retries."""
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_retries=2, base_delay=0.01, jitter=False))
        async def always_failing_func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Network error")
        
        with pytest.raises(ConnectionError):
            await always_failing_func()
        
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_auth_error_no_retry(self):
        """Test that auth errors don't retry."""
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_retries=3, base_delay=0.01))
        async def auth_error_func():
            nonlocal call_count
            call_count += 1
            raise PermissionError("Unauthorized - invalid token")
        
        with pytest.raises(PermissionError):
            await auth_error_func()
        
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_data_error_no_retry(self):
        """Test that data errors don't retry."""
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_retries=3, base_delay=0.01))
        async def data_error_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("No data found")
        
        with pytest.raises(ValueError):
            await data_error_func()
        
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retryable_exceptions_filter(self):
        """Test that only specified exceptions are retried."""
        call_count = 0
        
        @retry_with_backoff(
            RetryConfig(max_retries=3, base_delay=0.01),
            retryable_exceptions=(ConnectionError,)
        )
        async def specific_error_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not a connection error")
        
        with pytest.raises(ValueError):
            await specific_error_func()
        
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_exponential_delay(self):
        """Test that delay increases exponentially."""
        delays = []
        
        @retry_with_backoff(RetryConfig(max_retries=3, base_delay=0.1, jitter=False))
        async def track_delays():
            if len(delays) < 3:
                raise ConnectionError("Network error")
            return "success"
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = lambda d: delays.append(d)
            await track_delays()
            
            assert len(delays) == 3
            assert delays[0] == pytest.approx(0.1, rel=0.1)
            assert delays[1] == pytest.approx(0.2, rel=0.1)
            assert delays[2] == pytest.approx(0.4, rel=0.1)
    
    @pytest.mark.asyncio
    async def test_rate_limit_doubled_delay(self):
        """Test that rate-limited errors get doubled delay."""
        delays = []
        
        @retry_with_backoff(RetryConfig(max_retries=2, base_delay=0.1, jitter=False))
        async def rate_limited_func():
            if len(delays) < 2:
                raise Exception("Rate limit exceeded - 429")
            return "success"
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = lambda d: delays.append(d)
            await rate_limited_func()
            
            assert len(delays) == 2
            assert delays[0] == pytest.approx(0.2, rel=0.1)
            assert delays[1] == pytest.approx(0.4, rel=0.1)
