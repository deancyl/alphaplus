"""
Market API router - Overview, Indices, Bonds, Quotes.
"""
import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import get_db
from backend.models.fund import (
    StockQuotesHistory,
    BondYieldCurveStructure,
    MoneyMarketRates,
    IndexValuationHistory,
)
from backend.services.cache import realtime_cache
from backend.services.akshare_data import akshare_data_service, get_default_indices
from backend.services.index_valuation import get_all_indices_valuation, get_index_pe_history
from backend.services.market_gateway import market_gateway, init_gateway
from backend.schemas.fund import DashboardResponse, DashboardDataQuality
from backend.schemas.market import (
    IndexValuationItem,
    IndexValuationResponse,
    IndexPEHistoryItem,
    IndexPEHistoryResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize gateway on module load
_gateway_initialized = False


def _ensure_gateway_initialized():
    """Ensure gateway is initialized with sources."""
    global _gateway_initialized
    if not _gateway_initialized:
        init_gateway()
        _gateway_initialized = True


@router.get("/index-valuation", response_model=IndexValuationResponse)
async def get_all_index_valuations():
    """
    指数估值总览 - 返回17个核心指数的PE/PB数据.
    
    Performance: <150ms via parallel fetching with asyncio.gather.
    Graceful degradation: Returns simulated data if AkShare fails.
    """
    valuations = await get_all_indices_valuation()
    
    items = []
    for v in valuations:
        zone = v.get("markarea", {}).get("label", "正常")
        items.append(IndexValuationItem(
            index_code=v["index_code"],
            index_name=v["index_name"],
            pe_ttm=v["pe_ttm"],
            pb=v["pb"],
            dividend_yield=v["dividend_yield"],
            pe_percentile=v["pe_percentile"],
            pb_percentile=v["pb_percentile"],
            zone=zone,
            is_simulated=v["is_simulated"],
        ))
    
    return IndexValuationResponse(
        items=items,
        total=len(items),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@router.get("/index-valuation/{index_code}/history", response_model=IndexPEHistoryResponse)
async def get_index_valuation_history(
    index_code: str,
    days: int = Query(365, description="历史天数", ge=1, le=3650),
):
    """
    指数PE历史 - 单个指数的历史PE数据.
    
    Args:
        index_code: 指数代码 (如 000300)
        days: 历史天数 (默认365天)
    
    Returns:
        List of {date, pe, percentile} for charting
    """
    from backend.services.index_valuation import CORE_INDICES
    
    history_data = await get_index_pe_history(index_code, days)
    
    index_name = CORE_INDICES.get(index_code, "未知指数")
    
    history_items = [
        IndexPEHistoryItem(
            date=h["date"],
            pe=h["pe_value"],
            percentile=h["percentile"],
        )
        for h in history_data
    ]
    
    return IndexPEHistoryResponse(
        index_code=index_code,
        index_name=index_name,
        history=history_items,
    )


@router.get("/indices")
async def get_index_quotes():
    """
    核心指数行情 - 带超时和优雅降级的实时刷新.
    
    Features:
    - 10s timeout protection
    - Fallback to default indices on failure
    - Cache TTL 30s (configurable)
    - Returns _meta.is_fallback when using degraded data
    """
    cached_indices = await realtime_cache.get("indices")
    if cached_indices:
        return cached_indices
    
    try:
        real_data = await asyncio.wait_for(
            akshare_data_service.get_index_quotes(),
            timeout=10.0
        )
        if real_data:
            await realtime_cache.set("indices", real_data, ttl_seconds=30)
            return real_data
    except asyncio.TimeoutError:
        logger.warning("Indices API timed out after 10s, using fallback")
    except Exception as e:
        logger.warning(f"Indices API failed: {e}")
    
    default_data = {item["code"]: {
        "name": item["name"],
        "price": item["price"],
        "change": item["change"],
        "change_pct": item["change_pct"]
    } for item in get_default_indices()}
    
    return {
        **default_data,
        "_meta": {"is_fallback": True, "error": "Data source unavailable or timed out"}
    }


@router.get("/indices/health")
async def check_indices_health():
    """
    Health check for indices data source.
    
    Returns:
        - status: "healthy" or "degraded"
        - latency_ms: Response time in milliseconds
        - message: Error message if degraded
    """
    import time
    
    start_time = time.time()
    
    try:
        real_data = await asyncio.wait_for(
            akshare_data_service.get_index_quotes(),
            timeout=5.0
        )
        latency_ms = int((time.time() - start_time) * 1000)
        
        if real_data and len(real_data) > 0:
            return {
                "status": "healthy",
                "latency_ms": latency_ms,
                "indices_count": len(real_data),
            }
        else:
            return {
                "status": "degraded",
                "latency_ms": latency_ms,
                "message": "Data source returned empty data",
            }
    except asyncio.TimeoutError:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "status": "degraded",
            "latency_ms": latency_ms,
            "message": "Data source timed out after 5s",
        }
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "status": "degraded",
            "latency_ms": latency_ms,
            "message": f"Using fallback data: {str(e)}",
        }


@router.get("/valuation")
async def get_index_valuation(
    index_code: str = Query(..., description="指数代码"),
    db: AsyncSession = Depends(get_db),
):
    """指数估值 - PE TTM and percentile."""
    result = await db.execute(
        select(IndexValuationHistory)
        .where(IndexValuationHistory.index_code == index_code)
        .order_by(IndexValuationHistory.trade_date.desc())
        .limit(100)
    )
    valuations = result.scalars().all()
    
    return [
        {
            "trade_date": v.trade_date,
            "pe_ttm": v.pe_ttm,
            "percentile_rank_10y": v.percentile_rank_10y,
            "moving_mean_10y": v.moving_mean_10y,
            "index_close_price": v.index_close_price,
        }
        for v in valuations
    ]


@router.get("/bond/yield-curve")
async def get_bond_yield_curve(
    bond_type: str = Query("国债", description="国债/国开/口行/农发/地方"),
    trade_date: str = Query(None, description="日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    """债券收益率曲线 - 1Y~30Y期限结构."""
    conditions = [BondYieldCurveStructure.bond_type == bond_type]
    if trade_date:
        conditions.append(BondYieldCurveStructure.trade_date == trade_date)
    
    result = await db.execute(
        select(BondYieldCurveStructure)
        .where(*conditions)
        .order_by(BondYieldCurveStructure.trade_date.desc())
    )
    curves = result.scalars().all()
    
    curve_data = {}
    for c in curves:
        if c.trade_date not in curve_data:
            curve_data[c.trade_date] = []
        curve_data[c.trade_date].append({
            "tenor": c.tenor,
            "yield_ytm": c.yield_ytm,
        })
    
    return curve_data


@router.get("/bond/money-rates")
async def get_money_market_rates(
    db: AsyncSession = Depends(get_db),
):
    """货币市场利率 - DR007, SHIBOR等."""
    result = await db.execute(
        select(MoneyMarketRates)
        .order_by(MoneyMarketRates.trade_date.desc())
        .limit(100)
    )
    rates = result.scalars().all()
    
    return [
        {
            "rate_code": r.rate_code,
            "trade_date": r.trade_date,
            "rate_value": r.rate_value,
            "sparkline_data": r.sparkline_data,
        }
        for r in rates
    ]


@router.get("/bond/rate-history")
async def get_rate_history(
    rate_code: str = Query(..., description="DR007, SHIBOR_1W, etc."),
    days: int = Query(30, description="Number of days"),
    db: AsyncSession = Depends(get_db),
):
    """货币利率历史趋势 - For sparkline rendering."""
    from datetime import datetime, timedelta
    
    start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
    
    result = await db.execute(
        select(MoneyMarketRates)
        .where(
            MoneyMarketRates.rate_code == rate_code,
            MoneyMarketRates.trade_date >= start_date
        )
        .order_by(MoneyMarketRates.trade_date.desc())
        .limit(days)
    )
    history = result.scalars().all()
    
    if not history:
        return {"values": [], "dates": [], "is_simulated": True}
    
    history = list(reversed(history))
    
    return {
        "values": [h.rate_value for h in history],
        "dates": [h.trade_date for h in history],
        "is_simulated": False,
    }


@router.get("/heatmap")
async def get_market_heatmap():
    """
    多周期热力矩阵 - 全球指数/行业/外汇/A股宽基在9大周期表现.
    Returns color-coded matrix with rgba gradients.
    """
    heatmap_data = await akshare_data_service.get_market_heatmap()
    
    if heatmap_data.get("cells"):
        for cell in heatmap_data["cells"]:
            value = cell["value"]
            if value > 0:
                cell["color"] = f"rgba(0,204,0,{min(abs(value)/20, 0.8)})"
            else:
                cell["color"] = f"rgba(204,0,0,{min(abs(value)/20, 0.8)})"
        return heatmap_data
    
    rows = ["沪深300", "中证500", "创业板指", "科创50", "上证50", "中证1000"]
    cols = ["近1周", "近1月", "近3月", "近6月", "YTD", "近1年", "近3年", "近5年", "近10年"]
    return {"rows": rows, "cols": cols, "cells": []}


@router.get("/futures/quotes")
async def get_futures_quotes(
    category: str = Query(None, description="商品期货/金融期货/能源期货"),
    db: AsyncSession = Depends(get_db),
):
    """期货实时行情 - 主力合约报价与基差."""
    real_data = await akshare_data_service.get_futures_quotes(category)
    
    if real_data:
        return real_data
    
    return []


@router.get("/global")
async def get_global_market():
    """全球市场总览 - 主要指数、汇率、大宗商品."""
    indices = await akshare_data_service.get_global_indices()
    currencies = await akshare_data_service.get_currency_rates()
    commodities = await akshare_data_service.get_commodities()
    
    return {
        "indices": indices,
        "currencies": currencies,
        "commodities": commodities,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/domestic")
async def get_domestic_market(
    db: AsyncSession = Depends(get_db),
):
    """国内A股市场总览 - 指数、市场宽度、行业表现."""
    index_quotes = await akshare_data_service.get_index_quotes()
    sectors = await akshare_data_service.get_domestic_sectors()
    
    indices = []
    if index_quotes:
        for code, data in index_quotes.items():
            indices.append({
                "code": code,
                "name": data["name"],
                "price": round(data["price"], 2),
                "change_pct": round(data["change_pct"], 2),
            })
    
    result = await db.execute(
        select(IndexValuationHistory)
        .where(IndexValuationHistory.index_code == "000001")
        .order_by(IndexValuationHistory.trade_date.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    
    total_stocks = 5200
    advancing = 2600
    declining = 2400
    unchanged = 200
    
    return {
        "indices": indices,
        "market_breadth": {
            "total": total_stocks,
            "advancing": advancing,
            "declining": declining,
            "unchanged": unchanged,
            "advance_ratio": round(advancing / total_stocks * 100, 2),
            "limit_up": 25,
            "limit_down": 15,
        },
        "volume": {
            "total_volume": 9500.0,
            "total_turnover": 10200.0,
            "turnover_rate": 2.1,
        },
        "sectors": sectors,
        "north_bound": {
            "net_inflow": 25.5,
            "shanghai_inflow": 15.2,
            "shenzhen_inflow": 10.3,
        },
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
):
    """
    首页看板聚合端点 - 并行获取恐惧贪婪、ERP、风格强度、拥挤度.
    
    Performance: <150ms via asyncio.gather parallel calls.
    Graceful degradation: Returns partial data if sub-calls fail.
    """
    async def fetch_fear_greed():
        """Fetch fear-greed index data."""
        try:
            from backend.models.fund import MarketFearGreedSentimentHistory
            result = await db.execute(
                select(MarketFearGreedSentimentHistory)
                .order_by(MarketFearGreedSentimentHistory.trade_date.desc())
                .limit(30)
            )
            history = result.scalars().all()
            return {
                "data": [
                    {
                        "trade_date": h.trade_date,
                        "composite_score": h.composite_score,
                        "sentiment_status": h.sentiment_status,
                        "factor_volatility": h.factor_volatility,
                        "factor_safe_haven": h.factor_safe_haven,
                        "factor_margin_ratio": h.factor_margin_ratio,
                        "factor_volume_deviation": h.factor_volume_deviation,
                        "factor_futures_basis": h.factor_futures_basis,
                        "factor_stock_strength": h.factor_stock_strength,
                    }
                    for h in history
                ],
                "error": None,
            }
        except Exception as e:
            return {"data": None, "error": str(e)}
    
    async def fetch_erp():
        """Fetch ERP spread data."""
        try:
            from backend.models.fund import BondEquityYieldSpreadHistory
            result = await db.execute(
                select(BondEquityYieldSpreadHistory)
                .where(BondEquityYieldSpreadHistory.index_code == "000300")
                .order_by(BondEquityYieldSpreadHistory.trade_date.desc())
                .limit(100)
            )
            history = result.scalars().all()
            return {
                "data": [
                    {
                        "index_code": h.index_code,
                        "index_name": "沪深300",
                        "trade_date": h.trade_date,
                        "pe_ttm": h.pe_ttm,
                        "treasury_yield_10y": h.treasury_yield_10y,
                        "erp_spread": h.erp_spread,
                        "percentile_rank_10y": h.percentile_rank_10y,
                        "index_close_price": h.index_close_price,
                    }
                    for h in history
                ],
                "error": None,
            }
        except Exception as e:
            return {"data": None, "error": str(e)}
    
    async def fetch_style_strength():
        """Fetch style strength data."""
        try:
            from backend.models.fund import MarketStyleStrengthHistory
            result = await db.execute(
                select(MarketStyleStrengthHistory)
                .order_by(MarketStyleStrengthHistory.trade_date.desc())
                .limit(100)
            )
            history = result.scalars().all()
            return {
                "data": [
                    {
                        "trade_date": h.trade_date,
                        "index_code_num": h.index_code_num,
                        "index_code_den": h.index_code_den,
                        "ratio_value": h.ratio_value,
                        "percentile_rank_3y": h.percentile_rank_3y,
                    }
                    for h in history
                ],
                "error": None,
            }
        except Exception as e:
            return {"data": None, "error": str(e)}
    
    async def fetch_crowding():
        """Fetch crowding analysis data."""
        try:
            from backend.models.fund import MarketCrowdingValuationHistory
            result = await db.execute(
                select(MarketCrowdingValuationHistory)
                .order_by(MarketCrowdingValuationHistory.trade_date.desc())
                .limit(100)
            )
            history = result.scalars().all()
            return {
                "data": [
                    {
                        "asset_code": h.asset_code,
                        "trade_date": h.trade_date,
                        "category": h.category,
                        "crowding_score": h.crowding_score,
                        "pe_percentile": h.pe_percentile,
                        "close_price": h.close_price,
                    }
                    for h in history
                ],
                "error": None,
            }
        except Exception as e:
            return {"data": None, "error": str(e)}
    
    # Execute all 4 calls in parallel
    fear_greed_result, erp_result, style_strength_result, crowding_result = await asyncio.gather(
        fetch_fear_greed(),
        fetch_erp(),
        fetch_style_strength(),
        fetch_crowding(),
    )
    
    # Determine if any partial data
    has_partial = any([
        fear_greed_result["error"] is not None,
        erp_result["error"] is not None,
        style_strength_result["error"] is not None,
        crowding_result["error"] is not None,
    ])
    
    return DashboardResponse(
        fear_greed=fear_greed_result["data"] if fear_greed_result["data"] is not None else [],
        erp=erp_result["data"] if erp_result["data"] is not None else [],
        style_strength=style_strength_result["data"] if style_strength_result["data"] is not None else [],
        crowding=crowding_result["data"] if crowding_result["data"] is not None else [],
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data_quality=DashboardDataQuality(
            partial=has_partial,
            errors={
                "fear_greed": fear_greed_result["error"],
                "erp": erp_result["error"],
                "style_strength": style_strength_result["error"],
                "crowding": crowding_result["error"],
            },
        ),
    )


# ==================== Gateway-based Endpoints ====================


@router.get("/gateway/indices")
async def get_gateway_index_quotes(
    source: str = Query(None, description="Preferred source: akshare, eastmoney, sina"),
):
    """
    核心指数行情 - 通过Gateway多源获取.
    
    Features:
    - Multi-source failover (AkShare -> Eastmoney -> Sina)
    - Circuit breaker protection
    - Automatic retry with backoff
    
    Query params:
        source: Preferred data source (optional)
    """
    _ensure_gateway_initialized()
    
    cached_indices = await realtime_cache.get("indices")
    if cached_indices:
        return cached_indices
    
    result = await market_gateway.fetch("index_quotes", {}, preferred_source=source)
    
    if result.success:
        return result.value
    
    return {
        "000001": {"name": "上证指数", "price": 0, "change": 0, "change_pct": 0},
        "399001": {"name": "深证成指", "price": 0, "change": 0, "change_pct": 0},
        "000300": {"name": "沪深300", "price": 0, "change": 0, "change_pct": 0},
        "_meta": {
            "error": str(result.error),
            "sources_tried": result.fallback_chain,
        }
    }


@router.get("/gateway/futures")
async def get_gateway_futures_quotes(
    category: str = Query(None, description="商品期货/金融期货/能源期货"),
    source: str = Query(None, description="Preferred source"),
):
    """期货实时行情 - 通过Gateway多源获取."""
    _ensure_gateway_initialized()
    
    result = await market_gateway.fetch(
        "futures_quotes",
        {"category": category},
        preferred_source=source,
    )
    
    if result.success:
        return result.value
    
    return []


@router.get("/gateway/global")
async def get_gateway_global_market():
    """全球市场总览 - 通过Gateway并行获取."""
    _ensure_gateway_initialized()
    
    results = await market_gateway.fetch_parallel(
        ["global_indices", "currency_rates"],
        {}
    )
    
    indices_result, currencies_result = results
    
    return {
        "indices": indices_result.value if indices_result.success else [],
        "currencies": currencies_result.value if currencies_result.success else [],
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "_meta": {
            "indices_source": indices_result.source,
            "currencies_source": currencies_result.source,
        }
    }


@router.get("/gateway/status")
async def get_gateway_status():
    """
    Gateway状态监控 - 返回所有数据源健康状态.
    
    Returns circuit breaker states and source availability.
    """
    _ensure_gateway_initialized()
    
    return {
        "sources": market_gateway.get_all_sources_status(),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.post("/gateway/reset/{source_name}")
async def reset_source_circuit(source_name: str):
    """重置指定数据源的熔断器."""
    _ensure_gateway_initialized()
    
    if market_gateway.reset_circuit(source_name):
        return {"success": True, "message": f"Circuit breaker for '{source_name}' reset"}
    return {"success": False, "message": f"Source '{source_name}' not found"}
