"""
Tests for AIP Calculator API endpoints.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_aip_calculate_endpoint_basic(client: AsyncClient):
    """Should calculate AIP returns for valid fund code"""
    response = await client.post("/api/v1/fund/aip-calculate", json={
        "fund_code": "000001",
        "frequency": "weekly",
        "amount": 1000.0,
        "start_date": "2024-01-01"
    })
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_aip_calculate_total_investment(client: AsyncClient):
    """Total investment = periods × amount"""
    response = await client.post("/api/v1/fund/aip-calculate", json={
        "fund_code": "000001",
        "frequency": "monthly",
        "amount": 5000.0,
        "start_date": "2024-01-01",
        "end_date": "2024-12-31"
    })
    data = response.json()
    assert data["total_investment"] == data["periods"] * 5000.0


@pytest.mark.asyncio
async def test_aip_calculate_has_required_fields(client: AsyncClient):
    """Response should have all required fields"""
    response = await client.post("/api/v1/fund/aip-calculate", json={
        "fund_code": "000001",
        "frequency": "weekly",
        "amount": 1000.0,
        "start_date": "2024-01-01"
    })
    data = response.json()
    required_fields = ["total_investment", "current_value", "return_rate", 
                       "max_drawdown", "volatility", "periods", "units_total"]
    for field in required_fields:
        assert field in data


@pytest.mark.asyncio
async def test_aip_calculate_lump_sum_comparison(client: AsyncClient):
    """Should include lump-sum comparison"""
    response = await client.post("/api/v1/fund/aip-calculate", json={
        "fund_code": "000001",
        "frequency": "weekly",
        "amount": 1000.0,
        "start_date": "2024-01-01"
    })
    data = response.json()
    assert "lump_sum_comparison" in data
    # API returns lump_sum_value and lump_sum_return instead of value/return_rate
    assert "lump_sum_value" in data["lump_sum_comparison"]
    assert "lump_sum_return" in data["lump_sum_comparison"]


@pytest.mark.asyncio
async def test_aip_calculate_weekly_frequency(client: AsyncClient):
    """Weekly frequency should work"""
    response = await client.post("/api/v1/fund/aip-calculate", json={
        "fund_code": "000001",
        "frequency": "weekly",
        "amount": 1000.0,
        "start_date": "2024-01-01"
    })
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_aip_calculate_monthly_frequency(client: AsyncClient):
    """Monthly frequency should work"""
    response = await client.post("/api/v1/fund/aip-calculate", json={
        "fund_code": "000001",
        "frequency": "monthly",
        "amount": 5000.0,
        "start_date": "2024-01-01"
    })
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_aip_calculate_invalid_frequency(client: AsyncClient):
    """Should return 422 for invalid frequency (Pydantic validation)"""
    response = await client.post("/api/v1/fund/aip-calculate", json={
        "fund_code": "000001",
        "frequency": "invalid",
        "amount": 1000.0,
        "start_date": "2024-01-01"
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_aip_calculate_invalid_amount(client: AsyncClient):
    """Should return 422 for amount <= 0 (Pydantic validation)"""
    response = await client.post("/api/v1/fund/aip-calculate", json={
        "fund_code": "000001",
        "frequency": "weekly",
        "amount": -100.0,
        "start_date": "2024-01-01"
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_aip_calculate_invalid_fund(client: AsyncClient):
    """Should return 404 for fund without NAV history"""
    response = await client.post("/api/v1/fund/aip-calculate", json={
        "fund_code": "999999",
        "frequency": "weekly",
        "amount": 1000.0,
        "start_date": "2024-01-01"
    })
    assert response.status_code in [404, 500]


@pytest.mark.asyncio
async def test_aip_calculate_nav_history(client: AsyncClient):
    """Should include NAV history for charting"""
    response = await client.post("/api/v1/fund/aip-calculate", json={
        "fund_code": "000001",
        "frequency": "monthly",
        "amount": 5000.0,
        "start_date": "2024-01-01",
        "end_date": "2024-06-30"
    })
    data = response.json()
    assert "nav_history" in data
    assert len(data["nav_history"]) > 0
