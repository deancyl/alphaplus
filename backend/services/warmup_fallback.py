"""
Fallback data for cache warmup when external APIs fail.
Provides default/synthetic data to ensure service availability.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


async def inject_fallback_data():
    """
    Inject fallback data into cache for all critical endpoints.
    This ensures service availability even when external APIs fail.
    Called immediately on startup for non-blocking availability.
    """
    from backend.services.tiered_cache import tiered_cache
    from backend.services.cache import realtime_cache
    
    logger.info("Injecting fallback data into cache...")
    
    for idx_data in get_fallback_index_valuations():
        key = f"index_valuation:{idx_data['index_code']}"
        tiered_cache.set(key, idx_data, ttl=3600)
    
    tiered_cache.set("fear_greed:latest", get_fallback_fear_greed(), ttl=300)
    
    fallback_quotes = get_fallback_index_quotes()
    tiered_cache.set("index_quotes:all", fallback_quotes, ttl=300)
    await realtime_cache.set("indices", fallback_quotes, ttl_seconds=300)
    
    await realtime_cache.set("domestic_sectors", get_fallback_sectors(), ttl_seconds=300)
    
    await realtime_cache.set("top_funds:10", get_fallback_top_funds(), ttl_seconds=300)
    
    await realtime_cache.set("market:heatmap", get_fallback_heatmap(), ttl_seconds=3600)
    
    logger.info("Fallback data injection complete - service available immediately")

# Core indices mapping (code -> name)
CORE_INDICES = {
    "000001": "上证指数",
    "000300": "沪深300",
    "000905": "中证500",
    "000852": "中证1000",
    "399006": "创业板指",
    "399102": "创业板综",
    "000016": "上证50",
    "000688": "科创50",
    "399303": "国证2000",
    "000922": "中证红利",
    "000932": "中证消费",
    "000933": "中证医药",
    "000971": "中证科技",
    "399971": "中证传媒",
    "000986": "全指金融",
    "000987": "全指可选",
    "000988": "全指信息",
}

# Index symbol mapping for alternative data source
INDEX_SYMBOL_MAPPING = {
    "000001": ("sh000001", "上证指数"),
    "000300": ("sh000300", "沪深300"),
    "000905": ("sh000905", "中证500"),
    "000852": ("sh000852", "中证1000"),
    "399006": ("sz399006", "创业板指"),
    "000688": ("sh000688", "科创50"),
    "000016": ("sh000016", "上证50"),
    "399001": ("sz399001", "深证成指"),
}

def get_fallback_index_valuations() -> List[Dict[str, Any]]:
    """Return fallback valuation data for core indices."""
    return [
        {
            "index_code": code,
            "index_name": name,
            "pe_ttm": 15.0,
            "pb": 1.5,
            "dividend_yield": 2.5,
            "pe_percentile": 50.0,
            "pb_percentile": 50.0,
            "markarea": {"zone": "normal", "label": "正常", "color": "#eab308"},
            "is_fallback": True,
            "timestamp": datetime.now().isoformat(),
        }
        for code, name in CORE_INDICES.items()
    ]

def get_fallback_fear_greed() -> List[Dict[str, Any]]:
    """Return fallback fear-greed data (neutral sentiment)."""
    return [{
        "trade_date": datetime.now().strftime("%Y-%m-%d"),
        "composite_score": 50.0,
        "sentiment_status": "中性",
        "is_fallback": True,
    }]

def _fetch_from_daily_historical() -> Dict[str, Dict]:
    """Fetch real quotes from daily historical endpoint."""
    import akshare as ak
    
    result = {}
    success_count = 0
    
    for code, (symbol, name) in INDEX_SYMBOL_MAPPING.items():
        try:
            df = ak.stock_zh_index_daily(symbol=symbol)
            
            if df is None or df.empty:
                logger.warning(f"No data for index {code} ({name})")
                continue
            
            latest = df.iloc[-1]
            previous = df.iloc[-2] if len(df) > 1 else latest
            
            close = float(latest['close'])
            prev_close = float(previous['close'])
            change = close - prev_close
            change_pct = (change / prev_close * 100) if prev_close != 0 else 0.0
            
            result[code] = {
                "name": name,
                "price": close,
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "is_fallback": False,
            }
            success_count += 1
            
        except Exception as e:
            logger.warning(f"Failed to fetch {code} ({name}): {e}")
            continue
    
    if success_count == 0:
        raise Exception("All index fetches failed")
    
    result["_meta"] = {
        "is_fallback": False,
        "source": "alternative_akshare",
        "data_quality": "real",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "success_count": success_count,
        "total_count": len(INDEX_SYMBOL_MAPPING),
    }
    
    return result


def _get_static_fallback() -> Dict[str, Dict]:
    """Return static fallback index quotes."""
    reference_values = {
        "000001": {"name": "上证指数", "price": 3200.0, "change": 0.0, "change_pct": 0.0},
        "000300": {"name": "沪深300", "price": 4000.0, "change": 0.0, "change_pct": 0.0},
        "000905": {"name": "中证500", "price": 5500.0, "change": 0.0, "change_pct": 0.0},
        "000852": {"name": "中证1000", "price": 6500.0, "change": 0.0, "change_pct": 0.0},
        "399006": {"name": "创业板指", "price": 2200.0, "change": 0.0, "change_pct": 0.0},
        "000688": {"name": "科创50", "price": 950.0, "change": 0.0, "change_pct": 0.0},
        "000016": {"name": "上证50", "price": 2600.0, "change": 0.0, "change_pct": 0.0},
        "399001": {"name": "深证成指", "price": 10500.0, "change": 0.0, "change_pct": 0.0},
    }
    
    result = {}
    for code, data in reference_values.items():
        result[code] = {
            **data,
            "is_fallback": True,
        }
    
    result["_meta"] = {
        "is_fallback": True,
        "source": "fallback_static",
        "error": "Using reference values - live data unavailable",
        "data_quality": "fallback",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    return result


def get_fallback_index_quotes() -> Dict[str, Dict]:
    """Try alternative source first, then static fallback.
    
    Returns:
        Dict mapping index code to quote data with _meta.source indicator.
    """
    try:
        return _fetch_from_daily_historical()
    except Exception as e:
        logger.warning(f"Alternative source failed: {e}")
        return _get_static_fallback()


def get_fallback_sectors() -> List[Dict[str, Any]]:
    """Return static fallback sector performance data.
    
    Provides realistic sector names and change percentages when live data is unavailable.
    Used as final fallback layer in market.py for homepage load optimization.
    
    Returns:
        List of 15 sector dictionaries with 'name' and 'change_pct' fields.
        Sectors use realistic Chinese names and change_pct values in range [-3.0, +3.0].
    """
    return [
        {"name": "电子", "change_pct": 1.85},
        {"name": "计算机", "change_pct": 2.32},
        {"name": "医药生物", "change_pct": -0.76},
        {"name": "食品饮料", "change_pct": 0.54},
        {"name": "电气设备", "change_pct": 1.92},
        {"name": "化工", "change_pct": -1.23},
        {"name": "机械设备", "change_pct": 0.88},
        {"name": "汽车", "change_pct": 1.45},
        {"name": "有色金属", "change_pct": -2.15},
        {"name": "银行", "change_pct": -0.32},
        {"name": "非银金融", "change_pct": 0.67},
        {"name": "房地产", "change_pct": -1.88},
        {"name": "建筑材料", "change_pct": -0.95},
        {"name": "建筑装饰", "change_pct": 0.23},
        {"name": "通信", "change_pct": 2.78},
    ]


def get_fallback_top_funds() -> Dict[str, Any]:
    """Return static fallback top funds data.
    
    Provides placeholder top gainers and losers when pandas cache is not loaded.
    Used during startup warmup to ensure endpoint availability.
    
    Returns:
        Dict with 'gainers' and 'losers' lists, each containing 10 placeholder funds.
        Each fund has fund_code, fund_name, fund_type, and return_1y fields.
    """
    gainers = [
        {"fund_code": "000001", "fund_name": "Placeholder Gainer 1", "fund_type": "股票型", "return_1y": 0.45},
        {"fund_code": "000002", "fund_name": "Placeholder Gainer 2", "fund_type": "混合型", "return_1y": 0.42},
        {"fund_code": "000003", "fund_name": "Placeholder Gainer 3", "fund_type": "股票型", "return_1y": 0.38},
        {"fund_code": "000004", "fund_name": "Placeholder Gainer 4", "fund_type": "指数型", "return_1y": 0.35},
        {"fund_code": "000005", "fund_name": "Placeholder Gainer 5", "fund_type": "混合型", "return_1y": 0.32},
        {"fund_code": "000006", "fund_name": "Placeholder Gainer 6", "fund_type": "股票型", "return_1y": 0.28},
        {"fund_code": "000007", "fund_name": "Placeholder Gainer 7", "fund_type": "指数型", "return_1y": 0.25},
        {"fund_code": "000008", "fund_name": "Placeholder Gainer 8", "fund_type": "混合型", "return_1y": 0.22},
        {"fund_code": "000009", "fund_name": "Placeholder Gainer 9", "fund_type": "股票型", "return_1y": 0.18},
        {"fund_code": "000010", "fund_name": "Placeholder Gainer 10", "fund_type": "指数型", "return_1y": 0.15},
    ]
    
    losers = [
        {"fund_code": "999991", "fund_name": "Placeholder Loser 1", "fund_type": "股票型", "return_1y": -0.35},
        {"fund_code": "999992", "fund_name": "Placeholder Loser 2", "fund_type": "混合型", "return_1y": -0.32},
        {"fund_code": "999993", "fund_name": "Placeholder Loser 3", "fund_type": "股票型", "return_1y": -0.28},
        {"fund_code": "999994", "fund_name": "Placeholder Loser 4", "fund_type": "指数型", "return_1y": -0.25},
        {"fund_code": "999995", "fund_name": "Placeholder Loser 5", "fund_type": "混合型", "return_1y": -0.22},
        {"fund_code": "999996", "fund_name": "Placeholder Loser 6", "fund_type": "股票型", "return_1y": -0.18},
        {"fund_code": "999997", "fund_name": "Placeholder Loser 7", "fund_type": "指数型", "return_1y": -0.15},
        {"fund_code": "999998", "fund_name": "Placeholder Loser 8", "fund_type": "混合型", "return_1y": -0.12},
        {"fund_code": "999999", "fund_name": "Placeholder Loser 9", "fund_type": "股票型", "return_1y": -0.08},
        {"fund_code": "999990", "fund_name": "Placeholder Loser 10", "fund_type": "指数型", "return_1y": -0.05},
    ]
    
    return {
        "gainers": gainers,
        "losers": losers,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_fallback": True,
    }


def get_fallback_heatmap() -> dict:
    """
    Static fallback data for market heatmap when AkShare API fails.
    Returns multi-period returns for 6 indices across 9 time periods.
    """
    rows = ["沪深300", "中证500", "创业板指", "科创50", "上证50", "中证1000"]
    cols = ["近1周", "近1月", "近3月", "近6月", "YTD", "近1年", "近3年", "近5年", "近10年"]
    
    # Realistic return values (percentages)
    # Example: 沪深300: 近1周 +1.2%, 近1月 +3.5%, etc.
    return_values = {
        "沪深300": [1.2, 3.5, 8.2, 12.5, 5.8, 15.2, 25.6, 45.8, 82.3],
        "中证500": [1.8, 4.2, 9.5, 15.8, 7.2, 18.6, 32.5, 58.2, 95.6],
        "创业板指": [2.5, 5.8, 12.3, 18.6, 9.5, 22.3, 38.6, 68.5, 112.8],
        "科创50": [3.2, 6.5, 14.2, 22.5, 11.2, 28.5, 45.2, 82.3, 135.6],
        "上证50": [0.8, 2.5, 6.8, 10.2, 4.5, 12.3, 20.5, 38.6, 68.2],
        "中证1000": [2.1, 5.2, 11.5, 17.8, 8.6, 20.5, 35.8, 62.5, 102.3],
    }
    
    cells = []
    for row in rows:
        for i, col in enumerate(cols):
            value = return_values[row][i]
            if value > 0:
                color = f"rgba(0,204,0,{min(abs(value)/20, 0.8)})"
            else:
                color = f"rgba(204,0,0,{min(abs(value)/20, 0.8)})"
            cells.append({
                "row": row,
                "col": col,
                "value": value,
                "color": color,
            })
    
    return {
        "rows": rows,
        "cols": cols,
        "cells": cells,
        "_meta": {
            "is_fallback": True,
            "source": "static",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    }
