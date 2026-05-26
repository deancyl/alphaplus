"""
Tests for Pool API endpoints.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

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
async def test_list_pool_empty(client: AsyncClient):
    """Test GET /pool returns empty list initially."""
    response = await client.get("/api/v1/pool")
    assert response.status_code == 200
    data = response.json()
    assert "funds" in data
    assert "total" in data
    assert "pool_type" in data
    assert isinstance(data["funds"], list)
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_add_to_pool(client: AsyncClient):
    """Test POST /pool/add adds fund to pool."""
    response = await client.post(
        "/api/v1/pool/add",
        json={
            "pool_type": "entry",
            "fund_code": "000001",
            "fund_name": "Test Fund 1",
            "notes": "Test note",
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["pool_type"] == "entry"
    assert data["fund_code"] == "000001"
    assert data["fund_name"] == "Test Fund 1"
    assert data["status"] == "active"
    assert data["notes"] == "Test note"
    assert "id" in data
    assert "added_date" in data
    
    # Cleanup
    await client.delete(f"/api/v1/pool/{data['id']}")


@pytest.mark.asyncio
async def test_bulk_add_to_pool(client: AsyncClient):
    """Test POST /pool/bulk-add adds multiple funds."""
    response = await client.post(
        "/api/v1/pool/bulk-add",
        json={
            "pool_type": "focus",
            "funds": [
                {"pool_type": "focus", "fund_code": "000010", "fund_name": "Test Fund 10"},
                {"pool_type": "focus", "fund_code": "000011", "fund_name": "Test Fund 11"},
                {"pool_type": "focus", "fund_code": "000012", "fund_name": "Test Fund 12"},
            ]
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "count" in data
    assert data["count"] == 3
    assert "Successfully added" in data["message"]
    assert "elapsed_ms" in data
    
    # Verify funds were added
    list_response = await client.get("/api/v1/pool?pool_type=focus")
    funds = list_response.json()["funds"]
    added_codes = {f["fund_code"] for f in funds}
    assert "000010" in added_codes
    assert "000011" in added_codes
    assert "000012" in added_codes
    
    # Cleanup
    for fund in funds:
        if fund["fund_code"] in ["000010", "000011", "000012"]:
            await client.delete(f"/api/v1/pool/{fund['id']}")


@pytest.mark.asyncio
async def test_transfer_between_pools(client: AsyncClient):
    """Test POST /pool/transfer moves fund between pools."""
    # Add fund to entry pool
    add_response = await client.post(
        "/api/v1/pool/add",
        json={
            "pool_type": "entry",
            "fund_code": "000020",
            "fund_name": "Test Fund 20",
        }
    )
    assert add_response.status_code == 201
    pool_id = add_response.json()["id"]
    
    # Transfer to focus pool
    transfer_response = await client.post(
        "/api/v1/pool/transfer",
        json={
            "id": pool_id,
            "new_pool_type": "focus",
        }
    )
    assert transfer_response.status_code == 200
    data = transfer_response.json()
    assert data["pool_type"] == "focus"
    assert data["fund_code"] == "000020"
    
    # Verify it's in focus pool
    list_response = await client.get("/api/v1/pool?pool_type=focus")
    funds = list_response.json()["funds"]
    fund_codes = [f["fund_code"] for f in funds]
    assert "000020" in fund_codes
    
    # Cleanup
    await client.delete(f"/api/v1/pool/{pool_id}")


@pytest.mark.asyncio
async def test_remove_from_pool(client: AsyncClient):
    """Test DELETE /pool/{id} removes fund."""
    # Add fund to pool
    add_response = await client.post(
        "/api/v1/pool/add",
        json={
            "pool_type": "exit",
            "fund_code": "000030",
            "fund_name": "Test Fund 30",
        }
    )
    assert add_response.status_code == 201
    pool_id = add_response.json()["id"]
    
    # Remove from pool
    delete_response = await client.delete(f"/api/v1/pool/{pool_id}")
    assert delete_response.status_code == 204
    
    # Verify it's removed
    list_response = await client.get("/api/v1/pool?pool_type=exit")
    funds = list_response.json()["funds"]
    fund_codes = [f["fund_code"] for f in funds]
    assert "000030" not in fund_codes


@pytest.mark.asyncio
async def test_update_status(client: AsyncClient):
    """Test PUT /pool/status changes status."""
    # Add fund to pool
    add_response = await client.post(
        "/api/v1/pool/add",
        json={
            "pool_type": "entry",
            "fund_code": "000040",
            "fund_name": "Test Fund 40",
        }
    )
    assert add_response.status_code == 201
    pool_id = add_response.json()["id"]
    assert add_response.json()["status"] == "active"
    
    # Update status to removed
    update_response = await client.put(
        "/api/v1/pool/status",
        json={
            "id": pool_id,
            "status": "removed",
        }
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["status"] == "removed"
    assert data["removed_date"] is not None
    
    # Verify status changed
    list_response = await client.get("/api/v1/pool?pool_type=entry&status=removed")
    funds = list_response.json()["funds"]
    fund_codes = [f["fund_code"] for f in funds]
    assert "000040" in fund_codes
    
    # Cleanup
    await client.delete(f"/api/v1/pool/{pool_id}")
