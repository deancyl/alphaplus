"""
Tests for Fund API endpoints.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_fund_filter_empty(client: AsyncClient):
    """Test fund filter with empty database."""
    response = await client.post(
        "/api/v1/fund/filter",
        json={
            "page": 1,
            "page_size": 50,
            "sort_by": "return_1y",
            "sort_order": "desc",
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "funds" in data
    assert isinstance(data["funds"], list)


@pytest.mark.asyncio
async def test_market_indices(client: AsyncClient):
    """Test market indices endpoint."""
    response = await client.get("/api/v1/market/indices")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_fear_greed_index(client: AsyncClient):
    """Test fear/greed index endpoint."""
    response = await client.get("/api/v1/analytics/fear-greed")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
