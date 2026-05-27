"""
Pool API router - Fund pool management endpoints.
"""
import time
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.core import get_db
from backend.core.database import retry_on_sqlite_busy
from backend.models.fund import FundPoolRegistry
from backend.schemas.pool import (
    PoolAddRequest,
    PoolBulkAddRequest,
    PoolTransferRequest,
    PoolStatusUpdateRequest,
    PoolFundResponse,
    PoolListResponse,
)

pool_router = APIRouter()


@pool_router.get("/pool", response_model=PoolListResponse)
async def list_pools(
    pool_type: Optional[str] = Query(None, description="Filter by pool type: entry, focus, exit"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: active, removed"),
    db: AsyncSession = Depends(get_db),
):
    """
    List funds in pool with optional filters.
    Returns pool funds filtered by type and status.
    """
    query = select(FundPoolRegistry)
    conditions = []
    
    if pool_type:
        conditions.append(FundPoolRegistry.pool_type == pool_type)
    
    if status_filter:
        conditions.append(FundPoolRegistry.status == status_filter)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(FundPoolRegistry.added_date.desc())
    
    result = await db.execute(query)
    funds = result.scalars().all()
    
    fund_responses = [PoolFundResponse.model_validate(f) for f in funds]
    
    return PoolListResponse(
        pool_type=pool_type or "all",
        funds=fund_responses,
        total=len(fund_responses),
    )


@pool_router.post("/pool/add", response_model=PoolFundResponse, status_code=status.HTTP_201_CREATED)
async def add_to_pool(
    request: PoolAddRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a single fund to pool.
    Returns 409 Conflict if fund already exists in the pool.
    """
    # Check if fund already exists in this pool
    existing_query = select(FundPoolRegistry).where(
        and_(
            FundPoolRegistry.pool_type == request.pool_type,
            FundPoolRegistry.fund_code == request.fund_code,
        )
    )
    existing_result = await db.execute(existing_query)
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Fund {request.fund_code} already exists in {request.pool_type} pool",
        )
    
    # Create new pool entry
    pool_entry = FundPoolRegistry(
        pool_type=request.pool_type,
        fund_code=request.fund_code,
        fund_name=request.fund_name,
        status="active",
        added_date=date.today(),
        notes=request.notes,
    )
    
    db.add(pool_entry)
    await db.commit()
    await db.refresh(pool_entry)
    
    return PoolFundResponse.model_validate(pool_entry)


@pool_router.post("/pool/bulk-add", status_code=status.HTTP_201_CREATED)
@retry_on_sqlite_busy(max_retries=3, base_delay_ms=50, max_delay_ms=500)
async def bulk_add_to_pool(
    request: PoolBulkAddRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Bulk add funds to pool (max 50 funds).
    Performance target: <200ms for 50 funds.
    Returns 409 Conflict if any fund already exists in the pool.
    """
    start_time = time.time()
    
    # Validate max 50 funds
    if len(request.funds) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 funds allowed per bulk add",
        )
    
    # Get existing fund codes in this pool
    fund_codes = [f.fund_code for f in request.funds]
    existing_query = select(FundPoolRegistry.fund_code).where(
        and_(
            FundPoolRegistry.pool_type == request.pool_type,
            FundPoolRegistry.fund_code.in_(fund_codes),
        )
    )
    existing_result = await db.execute(existing_query)
    existing_codes = {row[0] for row in existing_result.all()}
    
    if existing_codes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Funds already exist in {request.pool_type} pool: {', '.join(existing_codes)}",
        )
    
    # Create pool entries
    pool_entries = [
        FundPoolRegistry(
            pool_type=request.pool_type,
            fund_code=fund.fund_code,
            fund_name=fund.fund_name,
            status="active",
            added_date=date.today(),
            notes=fund.notes,
        )
        for fund in request.funds
    ]
    
    # Use add_all for efficiency
    db.add_all(pool_entries)
    await db.commit()
    
    elapsed_ms = (time.time() - start_time) * 1000
    
    return {
        "message": f"Successfully added {len(pool_entries)} funds to {request.pool_type} pool",
        "count": len(pool_entries),
        "elapsed_ms": round(elapsed_ms, 2),
    }


@pool_router.delete("/pool/{id}", status_code=status.HTTP_204_NO_CONTENT)
@retry_on_sqlite_busy(max_retries=3, base_delay_ms=50, max_delay_ms=500)
async def remove_from_pool(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Remove a fund from pool (hard delete).
    Returns 404 if entry not found.
    """
    query = select(FundPoolRegistry).where(FundPoolRegistry.id == id)
    result = await db.execute(query)
    pool_entry = result.scalar_one_or_none()
    
    if not pool_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pool entry with id {id} not found",
        )
    
    await db.delete(pool_entry)
    await db.commit()
    
    return None


@pool_router.put("/pool/status", response_model=PoolFundResponse)
async def update_pool_status(
    request: PoolStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update pool entry status (active → removed).
    Sets removed_date when status changes to removed.
    Returns 404 if entry not found.
    """
    query = select(FundPoolRegistry).where(FundPoolRegistry.id == request.id)
    result = await db.execute(query)
    pool_entry = result.scalar_one_or_none()
    
    if not pool_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pool entry with id {request.id} not found",
        )
    
    pool_entry.status = request.status
    
    if request.status == "removed":
        pool_entry.removed_date = request.removed_date or date.today()
    else:
        pool_entry.removed_date = None
    
    await db.commit()
    await db.refresh(pool_entry)
    
    return PoolFundResponse.model_validate(pool_entry)


@pool_router.post("/pool/transfer", response_model=PoolFundResponse)
@retry_on_sqlite_busy(max_retries=3, base_delay_ms=50, max_delay_ms=500)
async def transfer_between_pools(
    request: PoolTransferRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Transfer fund between pools (entry → focus, focus → exit, etc.).
    Returns 404 if entry not found.
    Returns 409 if fund already exists in target pool.
    """
    # Get source entry
    query = select(FundPoolRegistry).where(FundPoolRegistry.id == request.id)
    result = await db.execute(query)
    pool_entry = result.scalar_one_or_none()
    
    if not pool_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pool entry with id {request.id} not found",
        )
    
    # Check if fund already exists in target pool
    existing_query = select(FundPoolRegistry).where(
        and_(
            FundPoolRegistry.pool_type == request.new_pool_type,
            FundPoolRegistry.fund_code == pool_entry.fund_code,
            FundPoolRegistry.id != request.id,
        )
    )
    existing_result = await db.execute(existing_query)
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Fund {pool_entry.fund_code} already exists in {request.new_pool_type} pool",
        )
    
    # Update pool type
    pool_entry.pool_type = request.new_pool_type
    pool_entry.added_date = date.today()
    
    await db.commit()
    await db.refresh(pool_entry)
    
    return PoolFundResponse.model_validate(pool_entry)
