"""
Pydantic schemas for favorites API.
"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List


class FavoriteCreate(BaseModel):
    """Schema for creating a favorite."""
    user_id: str = "default"
    product_type: str  # "fund", "wmp", "stock", "insurance"
    product_code: str
    product_name: str
    sort_order: int = 0


class FavoriteResponse(BaseModel):
    """Schema for favorite response."""
    id: int
    user_id: str
    product_type: str
    product_code: str
    product_name: str
    sort_order: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class FavoriteListResponse(BaseModel):
    """Schema for list of favorites."""
    items: List[FavoriteResponse]
    total: int


class FavoriteReorderRequest(BaseModel):
    """Schema for reordering favorites."""
    id: int
    new_sort_order: int
