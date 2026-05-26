"""
Tests for Index Valuation API endpoints.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_index_valuation_endpoint_returns_17_indices(client: AsyncClient):
    """Should return all 17 core indices with PE/PB data"""
    response = await client.get("/api/v1/market/index-valuation")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 17
    assert len(data["items"]) == 17


@pytest.mark.asyncio
async def test_index_valuation_pe_percentile_range_0_100(client: AsyncClient):
    """PE percentile should be normalized to 0-100 range"""
    response = await client.get("/api/v1/market/index-valuation")
    data = response.json()
    for item in data["items"]:
        assert 0 <= item["pe_percentile"] <= 100
        assert 0 <= item["pb_percentile"] <= 100


@pytest.mark.asyncio
async def test_index_valuation_includes_zone(client: AsyncClient):
    """Response should include zone (低估/正常/高估)"""
    response = await client.get("/api/v1/market/index-valuation")
    data = response.json()
    for item in data["items"]:
        assert item["zone"] in ["低估", "正常", "高估"]


@pytest.mark.asyncio
async def test_index_valuation_has_simulated_flag(client: AsyncClient):
    """Each item should have is_simulated flag"""
    response = await client.get("/api/v1/market/index-valuation")
    data = response.json()
    for item in data["items"]:
        assert "is_simulated" in item
        assert isinstance(item["is_simulated"], bool)


@pytest.mark.asyncio
async def test_index_pe_history_endpoint(client: AsyncClient):
    """Should return historical PE data for single index"""
    response = await client.get("/api/v1/market/index-valuation/000300/history?days=30")
    assert response.status_code == 200
    data = response.json()
    assert data["index_code"] == "000300"
    assert len(data["history"]) > 0


@pytest.mark.asyncio
async def test_index_pe_history_includes_date_pe_percentile(client: AsyncClient):
    """History items should have date, pe, percentile"""
    response = await client.get("/api/v1/market/index-valuation/000300/history")
    data = response.json()
    for item in data["history"]:
        assert "date" in item
        assert "pe" in item
        assert "percentile" in item


@pytest.mark.asyncio
async def test_index_valuation_invalid_code(client: AsyncClient):
    """Should return simulated data for invalid index code (graceful degradation)"""
    response = await client.get("/api/v1/market/index-valuation/INVALID/history")
    assert response.status_code == 200
    data = response.json()
    assert data["index_code"] == "INVALID"
    assert data["index_name"] == "未知指数"
    assert len(data["history"]) > 0


@pytest.mark.asyncio
async def test_index_valuation_performance(client: AsyncClient):
    """API response time should be under 150ms"""
    import time
    start = time.time()
    response = await client.get("/api/v1/market/index-valuation")
    elapsed = (time.time() - start) * 1000
    assert elapsed < 150
