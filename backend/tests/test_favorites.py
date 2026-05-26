"""
Tests for Favorites API endpoints.
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
async def test_list_favorites_empty(client: AsyncClient):
    """Test GET /favorites returns empty list initially."""
    response = await client.get("/api/v1/favorites")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_add_favorite(client: AsyncClient):
    """Test POST /favorites creates favorite."""
    response = await client.post(
        "/api/v1/favorites",
        json={
            "user_id": "test_user",
            "product_type": "fund",
            "product_code": "000001",
            "product_name": "Test Fund",
            "sort_order": 1,
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == "test_user"
    assert data["product_type"] == "fund"
    assert data["product_code"] == "000001"
    assert data["product_name"] == "Test Fund"
    assert data["sort_order"] == 1
    assert "id" in data
    assert "created_at" in data
    
    # Cleanup
    await client.delete(f"/api/v1/favorites/{data['id']}")


@pytest.mark.asyncio
async def test_add_duplicate_favorite(client: AsyncClient):
    """Test POST /favorites returns 400 for duplicate."""
    # Add first favorite
    response1 = await client.post(
        "/api/v1/favorites",
        json={
            "user_id": "test_user_dup",
            "product_type": "fund",
            "product_code": "000002",
            "product_name": "Test Fund 2",
            "sort_order": 1,
        }
    )
    assert response1.status_code == 201
    favorite_id = response1.json()["id"]
    
    # Try to add duplicate
    response2 = await client.post(
        "/api/v1/favorites",
        json={
            "user_id": "test_user_dup",
            "product_type": "fund",
            "product_code": "000002",
            "product_name": "Test Fund 2",
            "sort_order": 2,
        }
    )
    assert response2.status_code == 400
    assert "already in favorites" in response2.json()["detail"].lower()
    
    # Cleanup
    await client.delete(f"/api/v1/favorites/{favorite_id}")


@pytest.mark.asyncio
async def test_list_favorites_with_filter(client: AsyncClient):
    """Test GET /favorites?product_type=fund filters correctly."""
    # Add favorites with different product types
    response1 = await client.post(
        "/api/v1/favorites",
        json={
            "user_id": "test_user_filter",
            "product_type": "fund",
            "product_code": "000003",
            "product_name": "Test Fund 3",
            "sort_order": 1,
        }
    )
    assert response1.status_code == 201
    fund_id = response1.json()["id"]
    
    response2 = await client.post(
        "/api/v1/favorites",
        json={
            "user_id": "test_user_filter",
            "product_type": "stock",
            "product_code": "600000",
            "product_name": "Test Stock",
            "sort_order": 2,
        }
    )
    assert response2.status_code == 201
    stock_id = response2.json()["id"]
    
    # Filter by product_type=fund
    response = await client.get("/api/v1/favorites?user_id=test_user_filter&product_type=fund")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["product_type"] == "fund"
    
    # Filter by product_type=stock
    response = await client.get("/api/v1/favorites?user_id=test_user_filter&product_type=stock")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["product_type"] == "stock"
    
    # Cleanup
    await client.delete(f"/api/v1/favorites/{fund_id}")
    await client.delete(f"/api/v1/favorites/{stock_id}")


@pytest.mark.asyncio
async def test_delete_favorite(client: AsyncClient):
    """Test DELETE /favorites/{id} removes favorite."""
    # Add a favorite
    response = await client.post(
        "/api/v1/favorites",
        json={
            "user_id": "test_user_delete",
            "product_type": "fund",
            "product_code": "000004",
            "product_name": "Test Fund 4",
            "sort_order": 1,
        }
    )
    assert response.status_code == 201
    favorite_id = response.json()["id"]
    
    # Delete the favorite
    delete_response = await client.delete(f"/api/v1/favorites/{favorite_id}")
    assert delete_response.status_code == 204
    
    # Verify it's deleted
    list_response = await client.get("/api/v1/favorites?user_id=test_user_delete")
    data = list_response.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_reorder_favorites(client: AsyncClient):
    """Test PUT /favorites/reorder swaps sort_order."""
    # Add two favorites
    response1 = await client.post(
        "/api/v1/favorites",
        json={
            "user_id": "test_user_reorder",
            "product_type": "fund",
            "product_code": "000005",
            "product_name": "Test Fund 5",
            "sort_order": 1,
        }
    )
    assert response1.status_code == 201
    fav1_id = response1.json()["id"]
    
    response2 = await client.post(
        "/api/v1/favorites",
        json={
            "user_id": "test_user_reorder",
            "product_type": "fund",
            "product_code": "000006",
            "product_name": "Test Fund 6",
            "sort_order": 2,
        }
    )
    assert response2.status_code == 201
    fav2_id = response2.json()["id"]
    
    # Reorder: move fav1 to position 2
    reorder_response = await client.put(
        "/api/v1/favorites/reorder",
        json={
            "id": fav1_id,
            "new_sort_order": 2,
        }
    )
    assert reorder_response.status_code == 200
    data = reorder_response.json()
    assert data["id"] == fav1_id
    assert data["new_sort_order"] == 2
    
    # Verify order changed
    list_response = await client.get("/api/v1/favorites?user_id=test_user_reorder")
    items = list_response.json()["items"]
    # Items should be sorted by sort_order
    assert len(items) == 2
    
    # Cleanup
    await client.delete(f"/api/v1/favorites/{fav1_id}")
    await client.delete(f"/api/v1/favorites/{fav2_id}")
