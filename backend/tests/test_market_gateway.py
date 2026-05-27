"""
Tests for MarketDataGateway and CircuitBreaker.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.circuit_breaker import (
    AsyncCircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    Result,
)
from backend.services.market_gateway import (
    MarketDataGateway,
    FetchResult,
    SourceConfig,
)


class TestResult:
    """Tests for Result dataclass."""

    def test_ok_result(self):
        """Test creating successful result."""
        result = Result.ok({"data": "value"}, source="test")
        assert result.success is True
        assert result.value == {"data": "value"}
        assert result.source == "test"
        assert result.error is None

    def test_err_result(self):
        """Test creating failed result."""
        error = ValueError("test error")
        result = Result.err(error, source="test")
        assert result.success is False
        assert result.value is None
        assert result.error == error
        assert result.source == "test"


class TestAsyncCircuitBreaker:
    """Tests for AsyncCircuitBreaker."""

    def test_initial_state(self):
        """Test circuit breaker starts in CLOSED state."""
        cb = AsyncCircuitBreaker(name="test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed() is True
        assert cb.is_open() is False

    @pytest.mark.asyncio
    async def test_successful_call(self):
        """Test successful call passes through."""
        cb = AsyncCircuitBreaker(name="test", failure_threshold=3)

        async def success_func():
            return "success"

        result = await cb.call(success_func)
        assert result.success is True
        assert result.value == "success"
        assert cb.stats.successful_calls == 1
        assert cb.stats.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_failed_call_records_failure(self):
        """Test failed call increments failure count."""
        cb = AsyncCircuitBreaker(name="test", failure_threshold=3)

        async def fail_func():
            raise ValueError("test error")

        result = await cb.call(fail_func)
        assert result.success is False
        assert isinstance(result.error, ValueError)
        assert cb.stats.failed_calls == 1
        assert cb.stats.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        """Test circuit opens after reaching failure threshold."""
        cb = AsyncCircuitBreaker(name="test", failure_threshold=2)

        async def fail_func():
            raise ValueError("test error")

        # First failure
        await cb.call(fail_func)
        assert cb.is_closed() is True

        # Second failure - should open circuit
        await cb.call(fail_func)
        assert cb.is_open() is True

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self):
        """Test open circuit rejects calls."""
        cb = AsyncCircuitBreaker(name="test", failure_threshold=1)

        async def fail_func():
            raise ValueError("test error")

        # Trigger open
        await cb.call(fail_func)
        assert cb.is_open() is True

        # Next call should be rejected
        async def success_func():
            return "success"

        result = await cb.call(success_func)
        assert result.success is False
        assert isinstance(result.error, CircuitBreakerOpenError)

    @pytest.mark.asyncio
    async def test_half_open_allows_test_call(self):
        """Test half-open state allows one test call."""
        cb = AsyncCircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1)

        async def fail_func():
            raise ValueError("test error")

        # Trigger open
        await cb.call(fail_func)
        assert cb.is_open() is True

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Next call should transition to half-open and execute
        async def success_func():
            return "success"

        result = await cb.call(success_func)
        assert result.success is True
        assert cb.is_closed() is True  # Should close after success

    @pytest.mark.asyncio
    async def test_half_open_reopens_on_failure(self):
        """Test half-open reopens on test call failure."""
        cb = AsyncCircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1)

        async def fail_func():
            raise ValueError("test error")

        # Trigger open
        await cb.call(fail_func)
        assert cb.is_open() is True

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Next call should transition to half-open, fail, and reopen
        result = await cb.call(fail_func)
        assert result.success is False
        assert cb.is_open() is True

    def test_reset(self):
        """Test manual reset."""
        cb = AsyncCircuitBreaker(name="test", failure_threshold=1)
        cb.force_open()
        assert cb.is_open() is True

        cb.reset()
        assert cb.is_closed() is True
        assert cb.stats.consecutive_failures == 0

    def test_get_status(self):
        """Test status reporting."""
        cb = AsyncCircuitBreaker(name="test", failure_threshold=3, recovery_timeout=60)
        status = cb.get_status()

        assert status["name"] == "test"
        assert status["state"] == "closed"
        assert status["is_open"] is False
        assert status["config"]["failure_threshold"] == 3
        assert status["config"]["recovery_timeout"] == 60


class TestFetchResult:
    """Tests for FetchResult dataclass."""

    def test_ok_result(self):
        """Test creating successful fetch result."""
        result = FetchResult.ok({"data": "value"}, source="akshare")
        assert result.success is True
        assert result.value == {"data": "value"}
        assert result.source == "akshare"

    def test_err_result(self):
        """Test creating failed fetch result."""
        error = ValueError("test error")
        result = FetchResult.err(error, fallback_chain=["akshare", "eastmoney"])
        assert result.success is False
        assert result.error == error
        assert result.fallback_chain == ["akshare", "eastmoney"]


class MockSource:
    """Mock data source for testing."""

    def __init__(self, name: str, should_fail: bool = False, data: any = None):
        self.name = name
        self._should_fail = should_fail
        self._data = data or {"test": "data"}
        self.fetch_count = 0

    async def fetch(self, endpoint: str, params: dict = None):
        self.fetch_count += 1
        if self._should_fail:
            raise ValueError(f"{self.name} failed")
        return self._data

    def supports(self, endpoint: str) -> bool:
        return endpoint in ["index_quotes", "futures_quotes", "test_endpoint"]


class TestMarketDataGateway:
    """Tests for MarketDataGateway."""

    def test_register_source(self):
        """Test registering a data source."""
        gateway = MarketDataGateway()
        source = MockSource("test")

        gateway.register_source("test", source, priority=1)

        assert "test" in gateway._sources
        assert gateway._sources["test"].priority == 1
        assert gateway._sources["test"].enabled is True

    def test_unregister_source(self):
        """Test unregistering a data source."""
        gateway = MarketDataGateway()
        source = MockSource("test")

        gateway.register_source("test", source)
        assert "test" in gateway._sources

        result = gateway.unregister_source("test")
        assert result is True
        assert "test" not in gateway._sources

    def test_enable_disable_source(self):
        """Test enabling and disabling sources."""
        gateway = MarketDataGateway()
        source = MockSource("test")

        gateway.register_source("test", source)
        gateway.disable_source("test")
        assert gateway._sources["test"].enabled is False

        gateway.enable_source("test")
        assert gateway._sources["test"].enabled is True

    @pytest.mark.asyncio
    async def test_fetch_from_single_source(self):
        """Test fetching from single source."""
        gateway = MarketDataGateway()
        source = MockSource("test", data={"indices": [1, 2, 3]})

        gateway.register_source("test", source, priority=1)

        result = await gateway.fetch("test_endpoint")

        assert result.success is True
        assert result.value == {"indices": [1, 2, 3]}
        assert result.source == "test"

    @pytest.mark.asyncio
    async def test_fetch_with_failover(self):
        """Test automatic failover to next source."""
        gateway = MarketDataGateway()
        failing_source = MockSource("failing", should_fail=True)
        working_source = MockSource("working", data={"data": "success"})

        gateway.register_source("failing", failing_source, priority=1)
        gateway.register_source("working", working_source, priority=2)

        result = await gateway.fetch("test_endpoint")

        assert result.success is True
        assert result.value == {"data": "success"}
        assert result.source == "working"
        assert result.fallback_chain == ["failing", "working"]

    @pytest.mark.asyncio
    async def test_fetch_all_sources_fail(self):
        """Test when all sources fail."""
        gateway = MarketDataGateway()
        source1 = MockSource("s1", should_fail=True)
        source2 = MockSource("s2", should_fail=True)

        gateway.register_source("s1", source1, priority=1)
        gateway.register_source("s2", source2, priority=2)

        result = await gateway.fetch("test_endpoint")

        assert result.success is False
        assert result.fallback_chain == ["s1", "s2"]

    @pytest.mark.asyncio
    async def test_fetch_with_preferred_source(self):
        """Test preferring specific source."""
        gateway = MarketDataGateway()
        source1 = MockSource("s1", data={"source": "s1"})
        source2 = MockSource("s2", data={"source": "s2"})

        gateway.register_source("s1", source1, priority=1)
        gateway.register_source("s2", source2, priority=2)

        # Prefer s2 even though s1 has higher priority
        result = await gateway.fetch("test_endpoint", preferred_source="s2")

        assert result.success is True
        assert result.source == "s2"

    @pytest.mark.asyncio
    async def test_fetch_parallel(self):
        """Test parallel fetching of multiple endpoints."""
        gateway = MarketDataGateway()
        source = MockSource("test", data={"data": "value"})

        gateway.register_source("test", source, priority=1)

        results = await gateway.fetch_parallel(["test_endpoint", "test_endpoint"])

        assert len(results) == 2
        assert all(r.success for r in results)
        assert source.fetch_count == 2

    @pytest.mark.asyncio
    async def test_fetch_from_specific_source(self):
        """Test fetching from specific source only."""
        gateway = MarketDataGateway()
        source1 = MockSource("s1", data={"source": "s1"})
        source2 = MockSource("s2", data={"source": "s2"})

        gateway.register_source("s1", source1, priority=1)
        gateway.register_source("s2", source2, priority=2)

        result = await gateway.fetch_from_source("s2", "test_endpoint")

        assert result.success is True
        assert result.source == "s2"
        assert source1.fetch_count == 0  # s1 should not be called

    @pytest.mark.asyncio
    async def test_circuit_breaker_protection(self):
        """Test circuit breaker opens after failures."""
        gateway = MarketDataGateway()
        source = MockSource("test", should_fail=True)

        gateway.register_source("test", source, priority=1, failure_threshold=2)

        # Trigger failures
        await gateway.fetch("test_endpoint")
        await gateway.fetch("test_endpoint")

        # Circuit should be open now
        status = gateway.get_source_status("test")
        assert status["circuit_state"] == "open"

        # Next call should skip this source
        result = await gateway.fetch("test_endpoint")
        assert result.success is False
        assert result.fallback_chain == []  # No sources tried

    def test_get_all_sources_status(self):
        """Test getting status for all sources."""
        gateway = MarketDataGateway()
        source1 = MockSource("s1")
        source2 = MockSource("s2")

        gateway.register_source("s1", source1, priority=1)
        gateway.register_source("s2", source2, priority=2)

        statuses = gateway.get_all_sources_status()

        assert len(statuses) == 2
        assert statuses[0]["name"] == "s1"
        assert statuses[1]["name"] == "s2"

    def test_reset_circuit(self):
        """Test resetting circuit breaker."""
        gateway = MarketDataGateway()
        source = MockSource("test")

        gateway.register_source("test", source, priority=1)
        gateway._sources["test"].circuit_breaker.force_open()

        assert gateway._sources["test"].circuit_breaker.is_open()

        gateway.reset_circuit("test")
        assert gateway._sources["test"].circuit_breaker.is_closed()


class TestGatewayIntegration:
    """Integration tests for gateway with real source adapters."""

    @pytest.mark.asyncio
    async def test_akshare_source_endpoints(self):
        """Test AkshareSource supported endpoints."""
        from backend.services.sources.akshare_source import AkshareSource

        source = AkshareSource()
        endpoints = source.get_supported_endpoints()

        assert "index_quotes" in endpoints
        assert "stock_spot" in endpoints
        assert "futures_quotes" in endpoints
        assert "fund_nav" in endpoints

    @pytest.mark.asyncio
    async def test_eastmoney_source_endpoints(self):
        """Test EastmoneySource supported endpoints."""
        from backend.services.sources.eastmoney_source import EastmoneySource

        source = EastmoneySource()
        endpoints = source.get_supported_endpoints()

        assert "index_quotes" in endpoints
        assert "stock_quotes" in endpoints
        assert "fund_quotes" in endpoints
        assert "north_bound" in endpoints

    @pytest.mark.asyncio
    async def test_sina_source_endpoints(self):
        """Test SinaSource supported endpoints."""
        from backend.services.sources.sina_source import SinaSource

        source = SinaSource()
        endpoints = source.get_supported_endpoints()

        assert "index_quotes" in endpoints
        assert "stock_quotes" in endpoints
        assert "futures_quotes" in endpoints

    @pytest.mark.asyncio
    async def test_gateway_initialization(self):
        """Test gateway initialization with all sources."""
        from backend.services.market_gateway import MarketDataGateway, init_gateway

        gateway = MarketDataGateway()
        init_gateway()

        # Should have 3 sources registered
        assert len(gateway._sources) == 3
        assert "akshare" in gateway._sources
        assert "eastmoney" in gateway._sources
        assert "sina" in gateway._sources

        # Check priorities
        assert gateway._sources["akshare"].priority == 1
        assert gateway._sources["eastmoney"].priority == 2
        assert gateway._sources["sina"].priority == 3
