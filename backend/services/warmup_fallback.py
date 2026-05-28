"""
Fallback data for cache warmup when external APIs fail.
Provides default/synthetic data to ensure service availability.
"""

from datetime import datetime
from typing import Dict, List, Any

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

def get_fallback_index_quotes() -> Dict[str, Dict]:
    """Return fallback index quotes."""
    return {
        code: {
            "name": name,
            "price": 0.0,
            "change": 0.0,
            "change_pct": 0.0,
            "is_fallback": True,
        }
        for code, name in list(CORE_INDICES.items())[:5]  # Top 5 indices
    }
