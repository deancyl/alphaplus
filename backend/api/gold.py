"""
Gold product API endpoints with precise London-Shanghai conversion.
"""
from fastapi import APIRouter
from datetime import datetime
import logging

from backend.services.gold_constants import (
    TROY_OUNCE_TO_GRAMS,
    LONDON_GOLD_PURITY,
    SHANGHAI_GOLD_PURITY,
    VAT_FRICTION_FACTOR,
    get_usdcny_rate,
    convert_london_to_shanghai,
    convert_shanghai_to_london,
    verify_round_trip,
    calculate_premium,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/spot-price")
async def get_gold_spot_price():
    """
    Get gold spot prices (Shanghai Gold Exchange + International reference).
    
    Returns current prices with:
    - Precise London-Shanghai conversion using 31.1034768g/oz
    - Purity adjustment (LBMA 0.995 vs SGE 0.9999)
    - VAT friction factor (0.35%)
    - Real-time USDCNY exchange rate
    - Round-trip verification (< 0.01% error)
    - Conversion factors exposed in response
    
    Graceful degradation to simulated data if AkShare fails.
    """
    try:
        import akshare as ak
        
        # Fetch Shanghai gold price (Au99.99)
        shanghai_df = ak.spot_hist_sge(symbol="Au99.99")
        shanghai_price_cny_per_g = float(shanghai_df['close'].iloc[-1]) if len(shanghai_df) > 0 else 0.0
        
        # Fetch real-time USDCNY exchange rate
        usdcny_rate = await get_usdcny_rate()
        
        # Convert Shanghai to London (reverse calculation)
        london_conversion = convert_shanghai_to_london(
            shanghai_price_cny_per_g,
            usdcny_rate,
            include_vat=True
        )
        london_price_usd_per_oz = london_conversion["london_usd_per_oz"]
        
        # Convert London back to Shanghai for theoretical price
        shanghai_conversion = convert_london_to_shanghai(
            london_price_usd_per_oz,
            usdcny_rate,
            include_vat=True
        )
        
        # Calculate premium (actual vs theoretical)
        premium = calculate_premium(
            shanghai_price_cny_per_g,
            shanghai_conversion["shanghai_with_vat"]
        )
        
        # Verify round-trip accuracy
        round_trip = verify_round_trip(
            london_price_usd_per_oz,
            usdcny_rate,
            include_vat=True
        )
        
        return {
            "shanghai_gold": {
                "price": round(shanghai_price_cny_per_g, 2),
                "unit": "CNY/g",
                "source": "Shanghai Gold Exchange (Au99.99)",
                "purity": SHANGHAI_GOLD_PURITY
            },
            "london_gold": {
                "price": round(london_price_usd_per_oz, 2),
                "unit": "USD/oz",
                "source": "Calculated from Shanghai Gold (LBMA reference)",
                "purity": LONDON_GOLD_PURITY
            },
            "spread": {
                "absolute": round(premium["absolute_premium"], 2),
                "percentage": round(premium["percent_premium"], 2),
                "note": "Shanghai premium over theoretical London-converted price"
            },
            "conversion_factors": {
                "troy_ounce_to_grams": TROY_OUNCE_TO_GRAMS,
                "london_purity": LONDON_GOLD_PURITY,
                "shanghai_purity": SHANGHAI_GOLD_PURITY,
                "purity_ratio": round(SHANGHAI_GOLD_PURITY / LONDON_GOLD_PURITY, 6),
                "vat_friction_factor": VAT_FRICTION_FACTOR,
                "usdcny_rate": round(usdcny_rate, 4),
                "usdcny_source": "AkShare" if usdcny_rate != 7.20 else "Fallback"
            },
            "round_trip_verification": {
                "original_london_usd_per_oz": round_trip["original_london"],
                "round_trip_london_usd_per_oz": round_trip["round_trip_london"],
                "absolute_error": round_trip["absolute_error"],
                "percent_error": round_trip["percent_error"],
                "passes_threshold": round_trip["passes_threshold"],
                "threshold_pct": round_trip["threshold_pct"]
            },
            "timestamp": datetime.now().isoformat(),
            "is_simulated": False
        }
    except Exception as e:
        logger.warning(f"Failed to fetch gold prices from AkShare: {e}")
        # Fallback simulated data with proper conversion
        usdcny_rate = 7.20
        shanghai_price_cny_per_g = 585.50
        
        # Use conversion functions even for simulated data
        london_conversion = convert_shanghai_to_london(
            shanghai_price_cny_per_g,
            usdcny_rate,
            include_vat=True
        )
        london_price_usd_per_oz = london_conversion["london_usd_per_oz"]
        
        shanghai_conversion = convert_london_to_shanghai(
            london_price_usd_per_oz,
            usdcny_rate,
            include_vat=True
        )
        
        premium = calculate_premium(
            shanghai_price_cny_per_g,
            shanghai_conversion["shanghai_with_vat"]
        )
        
        round_trip = verify_round_trip(
            london_price_usd_per_oz,
            usdcny_rate,
            include_vat=True
        )
        
        return {
            "shanghai_gold": {
                "price": round(shanghai_price_cny_per_g, 2),
                "unit": "CNY/g",
                "source": "Simulated data (AkShare unavailable)",
                "purity": SHANGHAI_GOLD_PURITY
            },
            "london_gold": {
                "price": round(london_price_usd_per_oz, 2),
                "unit": "USD/oz",
                "source": "Simulated data (AkShare unavailable)",
                "purity": LONDON_GOLD_PURITY
            },
            "spread": {
                "absolute": round(premium["absolute_premium"], 2),
                "percentage": round(premium["percent_premium"], 2),
                "note": "Shanghai premium over theoretical London-converted price"
            },
            "conversion_factors": {
                "troy_ounce_to_grams": TROY_OUNCE_TO_GRAMS,
                "london_purity": LONDON_GOLD_PURITY,
                "shanghai_purity": SHANGHAI_GOLD_PURITY,
                "purity_ratio": round(SHANGHAI_GOLD_PURITY / LONDON_GOLD_PURITY, 6),
                "vat_friction_factor": VAT_FRICTION_FACTOR,
                "usdcny_rate": round(usdcny_rate, 4),
                "usdcny_source": "Fallback"
            },
            "round_trip_verification": {
                "original_london_usd_per_oz": round_trip["original_london"],
                "round_trip_london_usd_per_oz": round_trip["round_trip_london"],
                "absolute_error": round_trip["absolute_error"],
                "percent_error": round_trip["percent_error"],
                "passes_threshold": round_trip["passes_threshold"],
                "threshold_pct": round_trip["threshold_pct"]
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
    days = min(days, 365)
    
    try:
        import akshare as ak
        import pandas as pd
        
        history = []
        
        shanghai_df = ak.spot_hist_sge(symbol="Au99.99")
        shanghai_df = shanghai_df.tail(days)
        shanghai_prices = dict(zip(
            pd.to_datetime(shanghai_df['date']).dt.strftime('%Y-%m-%d'),
            shanghai_df['close'].astype(float)
        ))
        
        usdcny_rate = await get_usdcny_rate()
        
        london_prices = {}
        for date, shanghai_price in shanghai_prices.items():
            conversion = convert_shanghai_to_london(
                shanghai_price,
                usdcny_rate,
                include_vat=True
            )
            london_prices[date] = conversion["london_usd_per_oz"]
        
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
        import random
        from datetime import timedelta
        
        base_shanghai = 585.50
        usdcny_rate = 7.20
        history = []
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=days - i - 1)).strftime('%Y-%m-%d')
            shanghai_price = base_shanghai + random.uniform(-15, 15)
            
            conversion = convert_shanghai_to_london(
                shanghai_price,
                usdcny_rate,
                include_vat=True
            )
            london_price = conversion["london_usd_per_oz"]
            
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
