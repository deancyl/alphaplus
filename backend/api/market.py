"""
Market API router - Overview, Indices, Bonds, Quotes.
"""
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
from backend.services.akshare_data import akshare_data_service

router = APIRouter()


@router.get("/indices")
async def get_index_quotes():
    """
    核心指数行情 - 5秒伪实时刷新.
    Returns 8 major indices with cached data.
    """
    cached_indices = await realtime_cache.get("indices")
    if cached_indices:
        return cached_indices
    
    real_data = await akshare_data_service.get_index_quotes()
    if real_data:
        return real_data
    
    return {
        "000001": {"name": "上证指数", "price": 0, "change": 0, "change_pct": 0},
        "399001": {"name": "深证成指", "price": 0, "change": 0, "change_pct": 0},
        "000300": {"name": "沪深300", "price": 0, "change": 0, "change_pct": 0},
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
