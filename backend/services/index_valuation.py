"""
Index Valuation Service for 财富 Alpha+ 投研工作台.
Fetches PE, PB, dividend yield data from AkShare with percentile calculation.
Implements graceful degradation with GBM simulation fallback.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import numpy as np

from backend.services.resilience import retry_with_backoff, RetryConfig
from backend.services.simulators import GBMSimulator

logger = logging.getLogger(__name__)

# Core indices configuration (17 total)
CORE_INDICES = {
    # 宽基指数
    "000300": "沪深300",
    "000905": "中证500",
    "000852": "中证1000",
    "000016": "上证50",
    "000001": "上证指数",
    "399001": "深证成指",
    "399006": "创业板指",
    "000688": "科创50",
    # 红利指数
    "000922": "中证红利",
    # 主题指数
    "399971": "中证传媒",
    "399986": "中证银行",
    "399997": "中证白酒",
    # 其他
    "000903": "中证100",
    "000906": "中证800",
    "399330": "深证100",
    "399673": "创业板50",
    "000015": "上证红利",
}

# Cache for valuation data (1 hour TTL)
_valuation_cache: Dict[str, Dict[str, Any]] = {}
_cache_timestamps: Dict[str, datetime] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


def _get_cache_key(index_code: str) -> str:
    """Generate cache key for index valuation."""
    return f"valuation_{index_code}"


def _is_cache_valid(index_code: str) -> bool:
    """Check if cached data is still valid."""
    key = _get_cache_key(index_code)
    if key not in _cache_timestamps:
        return False
    elapsed = (datetime.now() - _cache_timestamps[key]).total_seconds()
    return elapsed < CACHE_TTL_SECONDS


def _set_cache(index_code: str, data: Dict[str, Any]) -> None:
    """Store data in cache."""
    key = _get_cache_key(index_code)
    _valuation_cache[key] = data
    _cache_timestamps[key] = datetime.now()


def _get_cached(index_code: str) -> Optional[Dict[str, Any]]:
    """Get cached data if valid."""
    if _is_cache_valid(index_code):
        key = _get_cache_key(index_code)
        return _valuation_cache.get(key)
    return None


def _calculate_percentile(current_value: float, historical_values: List[float]) -> float:
    """
    Calculate percentile of current value within historical data.
    
    Args:
        current_value: Current PE/PB/dividend yield value
        historical_values: List of historical values
    
    Returns:
        Percentile (0-100)
    """
    if not historical_values or len(historical_values) < 2:
        return 50.0  # Default to middle if insufficient data
    
    historical_array = np.array(historical_values)
    # Count values below current
    below_count = np.sum(historical_array < current_value)
    # Count values equal to current (for ties)
    equal_count = np.sum(historical_array == current_value)
    
    # Percentile formula: (below + 0.5 * equal) / total * 100
    percentile = (below_count + 0.5 * equal_count) / len(historical_array) * 100
    return round(percentile, 2)


def _get_markarea_zones(percentile: float) -> Dict[str, Any]:
    """
    Define markArea zones for ECharts based on percentile.
    
    Args:
        percentile: Current percentile (0-100)
    
    Returns:
        Dict with zone classification and color
    """
    if percentile <= 25:
        return {
            "zone": "undervalued",
            "label": "低估",
            "color": "#22c55e",  # Green
            "range": [0, 25]
        }
    elif percentile <= 75:
        return {
            "zone": "normal",
            "label": "正常",
            "color": "#eab308",  # Yellow
            "range": [25, 75]
        }
    else:
        return {
            "zone": "overvalued",
            "label": "高估",
            "color": "#ef4444",  # Red
            "range": [75, 100]
        }


def _generate_simulated_valuation(index_code: str, index_name: str) -> Dict[str, Any]:
    """
    Generate simulated valuation data using GBM when AkShare fails.
    
    Args:
        index_code: Index code
        index_name: Index name
    
    Returns:
        Simulated valuation data with is_simulated=True flag
    """
    # Default PE/PB ranges based on index type
    default_params = {
        "pe_mean": 15.0,
        "pe_std": 5.0,
        "pb_mean": 1.5,
        "pb_std": 0.5,
        "dividend_mean": 2.5,
        "dividend_std": 1.0,
    }
    
    # Adjust for specific indices
    if "红利" in index_name:
        default_params["pe_mean"] = 8.0
        default_params["dividend_mean"] = 4.5
    elif "银行" in index_name:
        default_params["pe_mean"] = 6.0
        default_params["pb_mean"] = 0.7
    elif "白酒" in index_name:
        default_params["pe_mean"] = 30.0
        default_params["pb_mean"] = 6.0
    elif "创业板" in index_name or "科创" in index_name:
        default_params["pe_mean"] = 40.0
        default_params["pb_mean"] = 4.0
    
    # Generate simulated current values using GBM
    # Use hash of index_code for seed to handle non-numeric codes
    try:
        seed = int(index_code[:6]) % 10000
    except ValueError:
        seed = hash(index_code) % 10000
    
    pe_sim = GBMSimulator(
        S0=default_params["pe_mean"],
        mu=0.0,  # No drift for valuation
        sigma=default_params["pe_std"] / default_params["pe_mean"],
        T=1.0,
        N=252,
        n_paths=1
    )
    pe_paths = pe_sim.simulate(seed=seed)
    current_pe = float(pe_paths[0, -1])
    
    pb_sim = GBMSimulator(
        S0=default_params["pb_mean"],
        mu=0.0,
        sigma=default_params["pb_std"] / default_params["pb_mean"],
        T=1.0,
        N=252,
        n_paths=1
    )
    pb_paths = pb_sim.simulate(seed=seed + 1000)
    current_pb = float(pb_paths[0, -1])
    
    dividend_sim = GBMSimulator(
        S0=default_params["dividend_mean"],
        mu=0.0,
        sigma=default_params["dividend_std"] / default_params["dividend_mean"],
        T=1.0,
        N=252,
        n_paths=1
    )
    dividend_paths = dividend_sim.simulate(seed=seed + 2000)
    current_dividend = float(dividend_paths[0, -1])
    
    # Generate simulated history for percentile calculation
    pe_history = list(pe_paths[0, :])
    pb_history = list(pb_paths[0, :])
    
    pe_percentile = _calculate_percentile(current_pe, pe_history)
    pb_percentile = _calculate_percentile(current_pb, pb_history)
    
    return {
        "index_code": index_code,
        "index_name": index_name,
        "pe_ttm": round(current_pe, 2),
        "pb": round(current_pb, 2),
        "dividend_yield": round(current_dividend, 2),
        "pe_percentile": pe_percentile,
        "pb_percentile": pb_percentile,
        "markarea": _get_markarea_zones(pe_percentile),
        "is_simulated": True,
        "data_source": "simulation",
        "timestamp": datetime.now().isoformat(),
    }


@retry_with_backoff(RetryConfig(max_retries=3, base_delay=1.0))
async def _fetch_pe_data(index_name: str) -> Optional[Dict[str, Any]]:
    """
    Fetch PE(TTM) data from AkShare.
    
    Args:
        index_name: Index name in Chinese (e.g., "沪深300")
    
    Returns:
        Dict with PE data or None on failure
    """
    try:
        import akshare as ak
        # AkShare uses Chinese index names
        df = ak.stock_index_pe_lg(symbol=index_name)
        if df is not None and not df.empty:
            # Get latest PE value - use 滚动市盈率 (TTM PE)
            latest = df.iloc[-1]
            # Try different PE column names
            pe_col = None
            for col in ["滚动市盈率", "市盈率", "静态市盈率"]:
                if col in df.columns:
                    pe_col = col
                    break
            
            if pe_col:
                current_pe = float(latest[pe_col])
                historical_pe = df[pe_col].tolist()
            else:
                current_pe = 0.0
                historical_pe = []
            
            return {
                "current_pe": current_pe,
                "historical_pe": historical_pe,
                "date": str(latest.get("日期", "")),
            }
    except Exception as e:
        logger.warning(f"Failed to fetch PE data for {index_name}: {e}")
    return None


@retry_with_backoff(RetryConfig(max_retries=3, base_delay=1.0))
async def _fetch_pb_data(index_name: str) -> Optional[Dict[str, Any]]:
    """
    Fetch PB data from AkShare.
    
    Args:
        index_name: Index name in Chinese (e.g., "沪深300")
    
    Returns:
        Dict with PB data or None on failure
    """
    try:
        import akshare as ak
        df = ak.stock_index_pb_lg(symbol=index_name)
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            pb_col = "市净率" if "市净率" in df.columns else None
            if pb_col:
                current_pb = float(latest[pb_col])
                historical_pb = df[pb_col].tolist()
            else:
                current_pb = 0.0
                historical_pb = []
            return {
                "current_pb": current_pb,
                "historical_pb": historical_pb,
                "date": str(latest.get("日期", "")),
            }
    except Exception as e:
        logger.warning(f"Failed to fetch PB data for {index_name}: {e}")
    return None


@retry_with_backoff(RetryConfig(max_retries=3, base_delay=1.0))
async def _fetch_dividend_data(index_name: str) -> Optional[float]:
    """
    Fetch dividend yield from AkShare.
    Note: stock_a_gxl_lg may not support all indices.
    
    Args:
        index_name: Index name in Chinese (e.g., "沪深300")
    
    Returns:
        Dividend yield percentage or None on failure
    """
    try:
        import akshare as ak
        df = ak.stock_a_gxl_lg(symbol=index_name)
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            div_col = "股息率" if "股息率" in df.columns else None
            if div_col:
                return float(latest[div_col])
    except Exception as e:
        logger.debug(f"Dividend data not available for {index_name}: {e}")
    return None


async def get_index_valuation_data(index_code: str) -> Dict[str, Any]:
    """
    Fetch PE, PB, dividend yield for a single index with percentile calculation.
    
    Args:
        index_code: Index code (e.g., "000300")
    
    Returns:
        Dict with valuation data including:
        - index_code, index_name
        - pe_ttm, pb, dividend_yield
        - pe_percentile, pb_percentile
        - markarea (undervalued/normal/overvalued zones)
        - is_simulated flag
    """
    # Check cache first
    cached = _get_cached(index_code)
    if cached:
        return cached
    
    index_name = CORE_INDICES.get(index_code, "未知指数")
    
    try:
        # Fetch all data in parallel
        pe_task = _fetch_pe_data(index_name)
        pb_task = _fetch_pb_data(index_name)
        dividend_task = _fetch_dividend_data(index_name)
        
        pe_data, pb_data, dividend_yield = await asyncio.gather(
            pe_task, pb_task, dividend_task
        )
        
        # Check if we got real data
        if pe_data and pb_data:
            current_pe = pe_data["current_pe"]
            current_pb = pb_data["current_pb"]
            historical_pe = pe_data["historical_pe"]
            historical_pb = pb_data["historical_pb"]
            
            pe_percentile = _calculate_percentile(current_pe, historical_pe)
            pb_percentile = _calculate_percentile(current_pb, historical_pb)
            
            result = {
                "index_code": index_code,
                "index_name": index_name,
                "pe_ttm": round(current_pe, 2),
                "pb": round(current_pb, 2),
                "dividend_yield": round(dividend_yield or 0, 2),
                "pe_percentile": pe_percentile,
                "pb_percentile": pb_percentile,
                "markarea": _get_markarea_zones(pe_percentile),
                "is_simulated": False,
                "data_source": "akshare",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            # Use simulation fallback
            result = _generate_simulated_valuation(index_code, index_name)
        
        # Cache the result
        _set_cache(index_code, result)
        return result
        
    except Exception as e:
        logger.error(f"Error fetching valuation for {index_code}: {e}")
        # Return simulated data on any error
        result = _generate_simulated_valuation(index_code, index_name)
        _set_cache(index_code, result)
        return result


async def get_all_indices_valuation() -> List[Dict[str, Any]]:
    """
    Fetch valuation data for all 17 core indices.
    Uses asyncio.gather for parallel fetching.
    
    Returns:
        List of dicts with valuation data for each index
    """
    tasks = [get_index_valuation_data(code) for code in CORE_INDICES.keys()]
    results = await asyncio.gather(*tasks)
    return list(results)


async def get_index_pe_history(index_code: str, days: int = 365) -> List[Dict[str, Any]]:
    """
    Get historical PE data for charting.
    
    Args:
        index_code: Index code (e.g., "000300")
        days: Number of days of history (default 365)
    
    Returns:
        List of dicts with date, pe_value, percentile for each day
    """
    index_name = CORE_INDICES.get(index_code, "未知指数")
    
    try:
        pe_data = await _fetch_pe_data(index_name)
        
        if pe_data and pe_data["historical_pe"]:
            historical_pe = pe_data["historical_pe"]
            # Take last N days
            historical_pe = historical_pe[-days:] if len(historical_pe) > days else historical_pe
            
            result = []
            for i, pe_value in enumerate(historical_pe):
                # Calculate rolling percentile up to this point
                percentile = _calculate_percentile(pe_value, historical_pe[:i+1])
                result.append({
                    "date": f"day_{i}",  # Would be actual date from AkShare
                    "pe_value": round(pe_value, 2),
                    "percentile": percentile,
                })
            return result
    except Exception as e:
        logger.error(f"Error fetching PE history for {index_code}: {e}")
    
    # Fallback: generate simulated history
    sim_data = _generate_simulated_valuation(index_code, index_name)
    # Generate synthetic history
    pe_sim = GBMSimulator(
        S0=sim_data["pe_ttm"],
        mu=0.0,
        sigma=0.2,
        T=days / 252,
        N=days,
        n_paths=1
    )
    try:
        seed = int(index_code[:6]) % 10000
    except ValueError:
        seed = hash(index_code) % 10000
    paths = pe_sim.simulate(seed=seed)
    pe_history = list(paths[0, :])
    
    result = []
    for i, pe_value in enumerate(pe_history):
        percentile = _calculate_percentile(pe_value, pe_history[:i+1])
        result.append({
            "date": f"day_{i}",
            "pe_value": round(pe_value, 2),
            "percentile": percentile,
            "is_simulated": True,
        })
    return result
