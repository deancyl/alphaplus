"""
Tests for AData Direct Mode fallback behavior.

Tests verify:
1. AData client basic functionality
2. Request batching
3. Request deduplication
4. Request coalescing
5. Gateway integration with fallback
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.sources.adata_client import ADataClient, CacheEntry
from backend.services.market_gateway import MarketDataGateway, FetchResult


class TestADataClientBasic:
    """Tests for ADataClient basic functionality."""

    def test_init(self):
        """Test client initialization."""
        client = ADataClient(
            timeout=10.0,
            max_batch_size=50,
            cache_ttl_ms=100,
            coalesce_window_ms=50,
        )

        assert client.name == "adata"
        assert client._timeout == 10.0
        assert client._max_batch_size == 50
        assert client._cache_ttl_ms == 100

    def test_supported_endpoints(self):
        """Test supported endpoints."""
        client = ADataClient()

        endpoints = client.get_supported_endpoints()
        assert "realtime_quotes" in endpoints
        assert "index_quotes" in endpoints
        assert "fund_nav" in endpoints
        assert "stock_quotes" in endpoints

        assert client.supports("realtime_quotes") is True
        assert client.supports("unknown_endpoint") is False

    def test_batch_symbols(self):
        """Test symbol batching logic."""
        client = ADataClient(max_batch_size=50)

        # Test empty list
        batches = client._batch_symbols([])
        assert batches == []

        # Test single batch
        symbols = [str(i) for i in range(30)]
        batches = client._batch_symbols(symbols)
        assert len(batches) == 1
        assert len(batches[0]) == 30

        # Test multiple batches
        symbols = [str(i) for i in range(120)]
        batches = client._batch_symbols(symbols)
        assert len(batches) == 3
        assert len(batches[0]) == 50
        assert len(batches[1]) == 50
        assert len(batches[2]) == 20


class TestADataClientDeduplication:
    """Tests for request deduplication."""

    def test_cache_hit(self):
        """Test cache returns data within TTL."""
        client = ADataClient(cache_ttl_ms=100)

        # Set cache
        data = {"600000": {"price": 10.0}}
        client._set_cache("test_key", data, "test_query")

        # Get from cache
        cached = client._get_cached("test_key", "test_query")
        assert cached == data

    def test_cache_miss_expired(self):
        """Test cache returns None when expired."""
        client = ADataClient(cache_ttl_ms=10)

        # Set cache
        data = {"600000": {"price": 10.0}}
        client._set_cache("test_key", data, "test_query")

        # Wait for expiry
        time.sleep(0.02)

        # Should return None
        cached = client._get_cached("test_key", "test_query")
        assert cached is None

    def test_cache_miss_query_type_mismatch(self):
        """Test cache returns None when query type differs."""
        client = ADataClient(cache_ttl_ms=100)

        # Set cache with one query type
        data = {"600000": {"price": 10.0}}
        client._set_cache("test_key", data, "query_type_a")

        # Try to get with different query type
        cached = client._get_cached("test_key", "query_type_b")
        assert cached is None

    def test_clear_expired_cache(self):
        """Test clearing expired entries."""
        client = ADataClient(cache_ttl_ms=10)

        # Set multiple cache entries
        client._set_cache("key1", {"data": 1}, "query")
        client._set_cache("key2", {"data": 2}, "query")

        # Wait for expiry
        time.sleep(0.02)

        # Add a fresh entry
        client._set_cache("key3", {"data": 3}, "query")

        # Clear expired
        client._clear_expired_cache()

        # Check only fresh entry remains
        assert "key1" not in client._cache
        assert "key2" not in client._cache
        assert "key3" in client._cache


class TestADataClientBatching:
    """Tests for request batching."""

    @pytest.mark.asyncio
    async def test_fetch_quote_batch(self):
        """Test fetching a batch of quotes."""
        client = ADataClient()

        mock_response = {
            "data": {
                "diff": [
                    {"f12": "1.600000", "f14": "浦发银行", "f2": 105000, "f3": 191, "f4": 200, "f5": 12345678, "f6": 129876543},
                    {"f12": "0.000001", "f14": "平安银行", "f2": 120000, "f3": -50, "f4": -60, "f5": 9876543, "f6": 118765432},
                ]
            }
        }

        with patch.object(client, "_fetch_json", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            result = await client._fetch_quote_batch(["600000", "000001"])

            assert "600000" in result
            assert "000001" in result
            assert result["600000"]["price"] == 1050.0  # 105000 / 100
            assert result["600000"]["change_pct"] == 1.91  # 191 / 100
            assert result["000001"]["change_pct"] == -0.5  # -50 / 100

    @pytest.mark.asyncio
    async def test_get_realtime_quotes_batches_large_request(self):
        """Test that large requests are batched."""
        client = ADataClient(max_batch_size=10)

        # Create 25 symbols (should be split into 3 batches)
        symbols = [str(i).zfill(6) for i in range(25)]

        mock_response = {
            "data": {"diff": []}
        }

        with patch.object(client, "_fetch_json", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            await client.get_realtime_quotes(symbols)

            # Should be called 3 times (10 + 10 + 5)
            assert mock_fetch.call_count == 3


class TestADataClientAPI:
    """Tests for ADataClient API methods."""

    @pytest.mark.asyncio
    async def test_get_index_quotes(self):
        """Test fetching index quotes."""
        client = ADataClient()

        mock_response = {
            "data": {
                "diff": [
                    {"f12": "1.000001", "f14": "上证指数", "f2": 300050, "f3": 51, "f4": 1520, "f5": 1234567890, "f6": 123456789012},
                    {"f12": "0.399001", "f14": "深证成指", "f2": 100080, "f3": 42, "f4": 420, "f5": 987654321, "f6": 98765432100},
                ]
            }
        }

        with patch.object(client, "_fetch_json", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            result = await client.get_index_quotes()

            assert "000001" in result
            assert result["000001"]["name"] == "上证指数"
            assert result["000001"]["price"] == 3000.50
            assert result["000001"]["change_pct"] == 0.51

    @pytest.mark.asyncio
    async def test_get_fund_nav(self):
        """Test fetching fund NAV."""
        client = ADataClient()

        mock_response_text = 'jsonpgz({"fundcode":"000001","name":"华夏成长混合","gsz":"1.234","gszzl":"1.56","gztime":"2024-01-15 15:00"})'

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.text = mock_response_text
            mock_get.return_value = mock_response

            result = await client.get_fund_nav("000001")

            assert result["fund_code"] == "000001"
            assert result["name"] == "华夏成长混合"
            assert result["nav"] == 1.234
            assert result["change_pct"] == 1.56

    @pytest.mark.asyncio
    async def test_fetch_adapter_interface(self):
        """Test gateway adapter interface."""
        client = ADataClient()

        # Test realtime_quotes endpoint
        with patch.object(client, "get_realtime_quotes", new_callable=AsyncMock) as mock:
            mock.return_value = {"600000": {}}
            result = await client.fetch("realtime_quotes", {"symbols": ["600000"]})
            mock.assert_called_once_with(["600000"])

        # Test index_quotes endpoint
        with patch.object(client, "get_index_quotes", new_callable=AsyncMock) as mock:
            mock.return_value = {"000001": {}}
            result = await client.fetch("index_quotes")
            mock.assert_called_once()

        # Test fund_nav endpoint
        with patch.object(client, "get_fund_nav", new_callable=AsyncMock) as mock:
            mock.return_value = {"fund_code": "000001"}
            result = await client.fetch("fund_nav", {"fund_code": "000001"})
            mock.assert_called_once_with("000001")

        # Test unsupported endpoint
        with pytest.raises(ValueError):
            await client.fetch("unknown_endpoint")


class TestADataClientCoalescing:
    """Tests for request coalescing."""

    @pytest.mark.asyncio
    async def test_coalesce_request(self):
        """Test request coalescing mechanism."""
        client = ADataClient(coalesce_window_ms=50)

        # Mock the actual fetch
        with patch.object(client, "get_realtime_quotes", new_callable=AsyncMock) as mock:
            mock.return_value = {"600000": {"price": 10.0}}

            # Start coalesced request
            task1 = asyncio.create_task(
                client._coalesce_request("realtime_quotes", "600000")
            )
            task2 = asyncio.create_task(
                client._coalesce_request("realtime_quotes", "000001")
            )

            # Wait for completion
            await asyncio.gather(task1, task2)

            # Both should complete (though implementation details may vary)


class TestGatewayIntegration:
    """Tests for gateway integration with AData."""

    @pytest.mark.asyncio
    async def test_adata_registered_as_primary(self):
        """Test AData is registered as primary source."""
        from backend.core.config import settings

        gateway = MarketDataGateway()

        # Mock ADataClient
        with patch("backend.services.sources.adata_client.ADataClient") as MockClient:
            mock_client = MagicMock()
            mock_client.name = "adata"
            mock_client.supports.return_value = True
            mock_client.fetch = AsyncMock(return_value={"test": "data"})
            MockClient.return_value = mock_client

            # Register AData
            gateway.register_source("adata", mock_client, priority=1)

            assert "adata" in gateway._sources
            assert gateway._sources["adata"].priority == 1

    @pytest.mark.asyncio
    async def test_fallback_to_akshare(self):
        """Test fallback from AData to AkShare on failure."""
        gateway = MarketDataGateway()

        # Create failing AData source
        adata_source = MagicMock()
        adata_source.name = "adata"
        adata_source.supports.return_value = True
        adata_source.fetch = AsyncMock(side_effect=Exception("AData failed"))

        # Create working AkShare source
        akshare_source = MagicMock()
        akshare_source.name = "akshare"
        akshare_source.supports.return_value = True
        akshare_source.fetch = AsyncMock(return_value={"test": "from_akshare"})

        gateway.register_source("adata", adata_source, priority=1, failure_threshold=1)
        gateway.register_source("akshare", akshare_source, priority=2)

        # Fetch should fallback to akshare
        result = await gateway.fetch("test_endpoint")

        assert result.success is True
        assert result.source == "akshare"
        assert result.value == {"test": "from_akshare"}
        assert result.fallback_chain == ["adata", "akshare"]

    @pytest.mark.asyncio
    async def test_adata_cache_prevents_redundant_calls(self):
        """Test that caching prevents redundant API calls."""
        client = ADataClient(cache_ttl_ms=100)

        mock_response = {
            "data": {
                "diff": [
                    {"f12": "1.600000", "f14": "浦发银行", "f2": 105000, "f3": 191, "f4": 200, "f5": 12345678, "f6": 129876543},
                ]
            }
        }

        with patch.object(client, "_fetch_json", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            # First call
            result1 = await client.get_realtime_quotes(["600000"])
            assert mock_fetch.call_count == 1

            # Second call within cache TTL should use cache
            result2 = await client.get_realtime_quotes(["600000"])
            assert mock_fetch.call_count == 1  # No additional call

            assert result1 == result2

    @pytest.mark.asyncio
    async def test_parallel_batch_fetching(self):
        """Test parallel fetching of multiple batches."""
        client = ADataClient(max_batch_size=5)

        # Create 15 symbols (3 batches)
        symbols = [str(i).zfill(6) for i in range(15)]

        mock_response = {
            "data": {"diff": []}
        }

        with patch.object(client, "_fetch_quote_batch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {}

            # Fetch all batches in parallel
            await client.get_realtime_quotes(symbols)

            # Should be called 3 times (5 + 5 + 5)
            assert mock_fetch.call_count == 3


class TestConfig:
    """Tests for AData configuration."""

    def test_config_defaults(self):
        """Test default AData config values."""
        from backend.core.config import settings

        assert settings.adata_enabled is True
        assert settings.adata_fallback_to_akshare is True
        assert settings.adata_cache_ttl_ms == 100
        assert settings.adata_batch_size == 50
        assert settings.adata_coalesce_window_ms == 50


class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_full_gateway_flow(self):
        """Test full gateway flow with AData."""
        gateway = MarketDataGateway()

        # Mock AData client
        adata = ADataClient(max_batch_size=10)

        # Mock HTTP responses
        mock_response = {
            "data": {
                "diff": [
                    {"f12": "1.600000", "f14": "浦发银行", "f2": 105000, "f3": 191, "f4": 200, "f5": 12345678, "f6": 129876543},
                ]
            }
        }

        with patch.object(adata, "_fetch_json", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_response

            gateway.register_source("adata", adata, priority=1)

            result = await gateway.fetch("realtime_quotes", {"symbols": ["600000"]})

            assert result.success is True
            assert result.source == "adata"

        await adata.close()
