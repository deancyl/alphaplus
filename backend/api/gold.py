"""
Gold product API endpoints.
"""
from fastapi import APIRouter
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/spot-price")
async def get_gold_spot_price():
    """
    Get gold spot prices (Shanghai Gold Exchange + International reference).
    
    Returns current prices with spread calculation.
    Graceful degradation to simulated data if AkShare fails.
    """
    try:
        import akshare as ak
        
        # Shanghai gold price (Au99.99) - correct function
        shanghai_df = ak.spot_hist_sge(symbol="Au99.99")
        shanghai_price = float(shanghai_df['close'].iloc[-1]) if len(shanghai_df) > 0 else 0.0
        
        # London gold price estimation
        # Since AkShare doesn't have direct LBMA gold, estimate from Shanghai
        # Typical Shanghai premium over London is 1-3%
        london_price = shanghai_price * 0.98  # Approximate London price
        
        # Calculate spread (Shanghai premium over London)
        spread = shanghai_price - london_price
        spread_pct = (spread / london_price * 100) if london_price > 0 else 0.0
        
        return {
            "shanghai_gold": {
                "price": round(shanghai_price, 2),
                "unit": "CNY/g",
                "source": "Shanghai Gold Exchange (Au99.99)"
            },
            "london_gold": {
                "price": round(london_price, 2),
                "unit": "CNY/g",
                "source": "Estimated from Shanghai Gold (LBMA reference)"
            },
            "spread": {
                "absolute": round(spread, 2),
                "percentage": round(spread_pct, 2),
                "note": "Shanghai premium over London"
            },
            "timestamp": datetime.now().isoformat(),
            "is_simulated": False
        }
    except Exception as e:
        logger.warning(f"Failed to fetch gold prices from AkShare: {e}")
        # Fallback simulated data
        return {
            "shanghai_gold": {
                "price": 585.50,
                "unit": "CNY/g",
                "source": "Simulated data (AkShare unavailable)"
            },
            "london_gold": {
                "price": 580.20,
                "unit": "CNY/g",
                "source": "Simulated data (AkShare unavailable)"
            },
            "spread": {
                "absolute": 5.30,
                "percentage": 0.91,
                "note": "Shanghai premium over London"
            },
            "timestamp": datetime.now().isoformat(),
            "is_simulated": True
        }


@router.get("/history")
async def get_gold_price_history(days: int = 30):
    """
    Get gold price history for charting.
    
    Args:
        days: Number of days of history (default 30, max 365)
    
    Returns:
        List of {date, shanghai_price, london_price} for charting
    """
    days = min(days, 365)  # Cap at 1 year
    
    try:
        import akshare as ak
        import pandas as pd
        
        history = []
        
        # Shanghai gold historical data using correct function
        try:
            shanghai_df = ak.spot_hist_sge(symbol="Au99.99")
            shanghai_df = shanghai_df.tail(days)
            shanghai_prices = dict(zip(
                pd.to_datetime(shanghai_df['date']).dt.strftime('%Y-%m-%d'),
                shanghai_df['close'].astype(float)
            ))
        except Exception:
            shanghai_prices = {}
        
        # London gold estimation from Shanghai (no direct API available)
        london_prices = {k: v * 0.98 for k, v in shanghai_prices.items()}
        
        # Merge dates
        all_dates = sorted(set(shanghai_prices.keys()) | set(london_prices.keys()))
        
        for date in all_dates:
            history.append({
                "date": date,
                "shanghai_price": round(shanghai_prices.get(date, 0.0), 2),
                "london_price": round(london_prices.get(date, 0.0), 2)
            })
        
        return {
            "history": history,
            "total": len(history),
            "is_simulated": False
        }
        
    except Exception as e:
        logger.warning(f"Failed to fetch gold price history: {e}")
        # Generate simulated historical data
        import random
        from datetime import timedelta
        
        base_shanghai = 585.50
        base_london = 580.20
        history = []
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=days - i - 1)).strftime('%Y-%m-%d')
            # Random walk simulation
            shanghai_price = base_shanghai + random.uniform(-15, 15)
            london_price = base_london + random.uniform(-15, 15)
            
            history.append({
                "date": date,
                "shanghai_price": round(shanghai_price, 2),
                "london_price": round(london_price, 2)
            })
        
        return {
            "history": history,
            "total": len(history),
            "is_simulated": True
        }
