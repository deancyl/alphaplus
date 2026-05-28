"""
Wealth Management Product (WMP) API router.

银行理财产品筛选API端点。
"""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query

from backend.schemas.wmp import (
    WMPItem,
    WMPFilterParams,
    WMPFilterResponse,
    WMPStatistics,
    WMPStatisticsResponse,
)
from backend.services.sources.wmp_source import wmp_gateway, init_wmp_gateway
from backend.services.tiered_cache import tiered_cache

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize gateway on module load
_gateway_initialized = False


def _ensure_gateway_initialized():
    """Ensure WMP gateway is initialized with sources."""
    global _gateway_initialized
    if not _gateway_initialized:
        init_wmp_gateway()
        _gateway_initialized = True


def _filter_products(products: List[dict], params: WMPFilterParams) -> List[dict]:
    """
    Apply filter criteria to WMP products.
    
    Args:
        products: Raw product data from source
        params: Filter parameters
        
    Returns:
        Filtered product list
    """
    filtered = products
    
    # Yield rate filter
    if params.yield_min is not None:
        filtered = [
            p for p in filtered
            if p.get("yield_rate") is not None and p["yield_rate"] >= params.yield_min
        ]
    
    if params.yield_max is not None:
        filtered = [
            p for p in filtered
            if p.get("yield_rate") is not None and p["yield_rate"] <= params.yield_max
        ]
    
    # Risk level filter
    if params.risk_levels:
        filtered = [
            p for p in filtered
            if p.get("risk_level") in params.risk_levels
        ]
    
    # Duration filter
    if params.duration_min is not None:
        filtered = [
            p for p in filtered
            if p.get("duration") is not None and p["duration"] >= params.duration_min
        ]
    
    if params.duration_max is not None:
        filtered = [
            p for p in filtered
            if p.get("duration") is not None and p["duration"] <= params.duration_max
        ]
    
    # Issuer filter (fuzzy match)
    if params.issuer:
        filtered = [
            p for p in filtered
            if p.get("issuer") and params.issuer.lower() in p["issuer"].lower()
        ]
    
    # Issuers filter (exact match)
    if params.issuers:
        filtered = [
            p for p in filtered
            if p.get("issuer") in params.issuers
        ]
    
    # Min amount filter
    if params.min_amount_max is not None:
        filtered = [
            p for p in filtered
            if p.get("min_amount") is not None and p["min_amount"] <= params.min_amount_max
        ]
    
    # Product type filter
    if params.product_types:
        filtered = [
            p for p in filtered
            if p.get("product_type") in params.product_types
        ]
    
    # Currency filter
    if params.currency:
        filtered = [
            p for p in filtered
            if p.get("currency") == params.currency
        ]
    
    # Active status filter
    if params.is_active is not None:
        filtered = [
            p for p in filtered
            if p.get("is_active") == params.is_active
        ]
    
    return filtered


def _sort_products(products: List[dict], sort_by: str, sort_order: str) -> List[dict]:
    """
    Sort products by specified field.
    
    Args:
        products: Product list
        sort_by: Field to sort by
        sort_order: asc or desc
        
    Returns:
        Sorted product list
    """
    reverse = sort_order == "desc"
    
    # Handle None values in sorting
    def sort_key(p):
        value = p.get(sort_by)
        if value is None:
            # Put None values at the end
            return (1, 0) if reverse else (0, float('inf'))
        return (0, value) if reverse else (0, value)
    
    return sorted(products, key=sort_key, reverse=reverse)


def _paginate_products(products: List[dict], page: int, page_size: int) -> List[dict]:
    """
    Paginate products.
    
    Args:
        products: Product list
        page: Page number (1-based)
        page_size: Number of items per page
        
    Returns:
        Paginated product list
    """
    start = (page - 1) * page_size
    end = start + page_size
    return products[start:end]


@router.post("/filter", response_model=WMPFilterResponse)
async def filter_wmp_products(params: WMPFilterParams):
    """
    银行理财产品筛选 - 多维度筛选与分页.
    
    Features:
    - Multi-source data fetching with failover
    - Tiered cache (L1 memory + L2 Parquet, 1-hour TTL)
    - Flexible filtering by yield, risk, duration, issuer, etc.
    - Pagination and sorting
    
    Filter dimensions:
    - yield_rate: 收益率范围
    - risk_level: 风险等级 PR1-PR5
    - duration: 产品期限(天)
    - issuer: 发行机构
    - min_amount: 起购金额
    
    Example:
        POST /api/v1/wmp/filter
        {
            "yield_min": 3.0,
            "risk_levels": ["PR2", "PR3"],
            "duration_min": 90,
            "duration_max": 365,
            "issuer": "工商银行",
            "page": 1,
            "page_size": 50,
            "sort_by": "yield_rate",
            "sort_order": "desc"
        }
    """
    _ensure_gateway_initialized()
    
    # Check cache first (1-hour TTL for WMP data)
    cache_key = f"wmp:list:all"
    cached_data = tiered_cache.get(cache_key)
    
    if cached_data is not None:
        logger.info("WMP data found in cache")
        products = cached_data
        data_source = "cache"
        fallback_chain = []
    else:
        # Fetch from gateway with multi-source failover
        products, data_source, fallback_chain = await wmp_gateway.fetch_wmp_list()
        
        if products:
            # Cache results for 1 hour
            tiered_cache.set(cache_key, products, ttl=3600)
            logger.info(f"Cached WMP data ({len(products)} products) for 1 hour")
    
    # Apply filters
    filtered_products = _filter_products(products, params)
    
    # Apply sorting
    sorted_products = _sort_products(
        filtered_products, 
        params.sort_by or "yield_rate", 
        params.sort_order
    )
    
    # Apply pagination
    paginated_products = _paginate_products(
        sorted_products, 
        params.page, 
        params.page_size
    )
    
    # Convert to WMPItem schema
    wmp_items = [WMPItem(**p) for p in paginated_products]
    
    return WMPFilterResponse(
        total=len(filtered_products),
        page=params.page,
        page_size=params.page_size,
        products=wmp_items,
        data_source=data_source,
        fallback_chain=fallback_chain,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@router.get("/list", response_model=WMPFilterResponse)
async def get_wmp_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    sort_by: str = Query("yield_rate", description="排序字段"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="排序方向"),
):
    """
    银行理财产品列表 - 获取所有产品(无筛选).
    
    Returns paginated list of all WMP products.
    """
    _ensure_gateway_initialized()
    
    # Use default params
    params = WMPFilterParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    
    return await filter_wmp_products(params)


@router.get("/statistics", response_model=WMPStatisticsResponse)
async def get_wmp_statistics():
    """
    银行理财产品统计 - 收益率分布、风险等级分布等.
    
    Returns aggregated statistics for WMP market.
    """
    _ensure_gateway_initialized()
    
    # Fetch all products
    cache_key = f"wmp:list:all"
    cached_data = tiered_cache.get(cache_key)
    
    if cached_data is not None:
        products = cached_data
    else:
        products, _, _ = await wmp_gateway.fetch_wmp_list()
        if products:
            tiered_cache.set(cache_key, products, ttl=3600)
    
    # Calculate statistics
    total_count = len(products)
    
    # Yield statistics
    yields = [p.get("yield_rate") for p in products if p.get("yield_rate") is not None]
    avg_yield = sum(yields) / len(yields) if yields else None
    yield_range = {
        "min": min(yields) if yields else None,
        "max": max(yields) if yields else None,
    }
    
    # Risk distribution
    risk_distribution = {}
    for p in products:
        risk = p.get("risk_level")
        if risk:
            risk_distribution[risk] = risk_distribution.get(risk, 0) + 1
    
    # Duration distribution
    duration_distribution = {}
    for p in products:
        duration = p.get("duration")
        if duration:
            bucket = "短期(≤90天)" if duration <= 90 else "中期(90-365天)" if duration <= 365 else "长期(>365天)"
            duration_distribution[bucket] = duration_distribution.get(bucket, 0) + 1
    
    # Issuer count
    issuers = set(p.get("issuer") for p in products if p.get("issuer"))
    issuer_count = len(issuers)
    
    stats = WMPStatistics(
        total_count=total_count,
        avg_yield=round(avg_yield, 2) if avg_yield else None,
        yield_range=yield_range,
        risk_distribution=risk_distribution,
        duration_distribution=duration_distribution,
        issuer_count=issuer_count,
    )
    
    return WMPStatisticsResponse(
        statistics=stats,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@router.get("/sources")
async def get_wmp_sources_status():
    """
    WMP数据源状态 - 返回所有数据源健康状态.
    
    Returns registered sources and their priorities.
    """
    _ensure_gateway_initialized()
    
    sources = [
        {
            "name": name,
            "priority": priority,
        }
        for name, (_, priority) in wmp_gateway._sources.items()
    ]
    
    return {
        "sources": sources,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }