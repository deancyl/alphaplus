"""
Pool schemas - Pydantic models for fund pool management API.
"""
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, List


class PoolAddRequest(BaseModel):
    """Request schema for adding a single fund to pool."""
    pool_type: str = Field(..., description="Pool type: entry, focus, exit")
    fund_code: str = Field(..., description="Fund code")
    fund_name: str = Field(..., description="Fund name")
    notes: Optional[str] = Field(None, description="Optional notes")


class PoolBulkAddRequest(BaseModel):
    """Request schema for bulk adding funds to pool."""
    pool_type: str = Field(..., description="Pool type: entry, focus, exit")
    funds: List[PoolAddRequest] = Field(..., max_length=50, description="List of funds to add (max 50)")


class PoolTransferRequest(BaseModel):
    """Request schema for transferring fund between pools."""
    id: int = Field(..., description="Pool entry ID")
    new_pool_type: str = Field(..., description="New pool type: entry, focus, exit")


class PoolStatusUpdateRequest(BaseModel):
    """Request schema for updating pool entry status."""
    id: int = Field(..., description="Pool entry ID")
    status: str = Field(..., description="Status: active, removed")
    removed_date: Optional[date] = Field(None, description="Removed date (required if status is removed)")


class PoolFundResponse(BaseModel):
    """Response schema for a single pool fund entry."""
    id: int
    pool_type: str
    fund_code: str
    fund_name: str
    status: str
    added_date: date
    removed_date: Optional[date]
    notes: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class PoolListResponse(BaseModel):
    """Response schema for pool list."""
    pool_type: str
    funds: List[PoolFundResponse]
    total: int
