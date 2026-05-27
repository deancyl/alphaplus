"""
Favorites API router - CRUD operations for user favorites.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import get_db
from backend.core.database import retry_on_sqlite_busy
from backend.models.fund import UserFavoritesRegistry
from backend.schemas.favorites import (
    FavoriteCreate,
    FavoriteResponse,
    FavoriteListResponse,
    FavoriteReorderRequest,
)

favorites_router = APIRouter()


@favorites_router.get("/favorites", response_model=FavoriteListResponse)
async def list_favorites(
    user_id: str = Query(default="default", description="User ID"),
    product_type: Optional[str] = Query(default=None, description="Product type filter"),
    db: AsyncSession = Depends(get_db),
):
    """
    List user favorites with optional product type filter.
    Returns favorites sorted by sort_order.
    """
    conditions = [UserFavoritesRegistry.user_id == user_id]
    
    if product_type:
        conditions.append(UserFavoritesRegistry.product_type == product_type)
    
    # Query for items
    query = (
        select(UserFavoritesRegistry)
        .where(and_(*conditions))
        .order_by(UserFavoritesRegistry.sort_order)
    )
    result = await db.execute(query)
    items = result.scalars().all()
    
    # Query for total count
    count_query = select(UserFavoritesRegistry.id).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = len(count_result.all())
    
    return FavoriteListResponse(
        items=[FavoriteResponse.model_validate(item) for item in items],
        total=total,
    )


@favorites_router.post("/favorites", response_model=FavoriteResponse, status_code=201)
@retry_on_sqlite_busy(max_retries=3, base_delay_ms=50, max_delay_ms=500)
async def add_favorite(
    favorite: FavoriteCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a product to favorites.
    Returns 201 on success.
    Raises 400 if already exists.
    """
    # Check if already exists
    existing_query = select(UserFavoritesRegistry).where(
        and_(
            UserFavoritesRegistry.user_id == favorite.user_id,
            UserFavoritesRegistry.product_type == favorite.product_type,
            UserFavoritesRegistry.product_code == favorite.product_code,
        )
    )
    existing_result = await db.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Product already in favorites"
        )
    
    # Create new favorite
    new_favorite = UserFavoritesRegistry(
        user_id=favorite.user_id,
        product_type=favorite.product_type,
        product_code=favorite.product_code,
        product_name=favorite.product_name,
        sort_order=favorite.sort_order,
    )
    db.add(new_favorite)
    await db.flush()
    await db.refresh(new_favorite)
    
    return FavoriteResponse.model_validate(new_favorite)


@favorites_router.delete("/favorites/{favorite_id}", status_code=204)
@retry_on_sqlite_busy(max_retries=3, base_delay_ms=50, max_delay_ms=500)
async def remove_favorite(
    favorite_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Remove a product from favorites.
    Returns 204 on success.
    Raises 404 if not found.
    """
    query = select(UserFavoritesRegistry).where(
        UserFavoritesRegistry.id == favorite_id
    )
    result = await db.execute(query)
    favorite = result.scalar_one_or_none()
    
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    await db.delete(favorite)


@favorites_router.put("/favorites/reorder")
@retry_on_sqlite_busy(max_retries=3, base_delay_ms=50, max_delay_ms=500)
async def reorder_favorites(
    request: FavoriteReorderRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reorder favorites by updating sort_order.
    Swaps sort_order with the item at new_sort_order.
    Returns 200 on success.
    Raises 404 if not found.
    """
    # Get the favorite to reorder
    query = select(UserFavoritesRegistry).where(
        UserFavoritesRegistry.id == request.id
    )
    result = await db.execute(query)
    favorite = result.scalar_one_or_none()
    
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    old_sort_order = favorite.sort_order
    new_sort_order = request.new_sort_order
    
    # Find the item at new_sort_order (if exists)
    swap_query = select(UserFavoritesRegistry).where(
        and_(
            UserFavoritesRegistry.user_id == favorite.user_id,
            UserFavoritesRegistry.product_type == favorite.product_type,
            UserFavoritesRegistry.sort_order == new_sort_order,
            UserFavoritesRegistry.id != request.id,
        )
    )
    swap_result = await db.execute(swap_query)
    swap_favorite = swap_result.scalar_one_or_none()
    
    # Swap sort_order values
    if swap_favorite:
        swap_favorite.sort_order = old_sort_order
    
    favorite.sort_order = new_sort_order
    
    await db.flush()
    
    return {"message": "Reorder successful", "id": request.id, "new_sort_order": new_sort_order}
