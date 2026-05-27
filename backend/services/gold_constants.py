"""
Gold conversion constants and functions for precise London-Shanghai gold price conversion.

Implements:
- Precise troy ounce to gram conversion (31.1034768g)
- Purity adjustment (LBMA 0.995 vs SGE 0.9999)
- VAT friction factor (0.35%)
- Real-time USDCNY exchange rate with fallback
- Round-trip conversion verification (< 0.01% error)
"""
import logging
from typing import Optional
import asyncio

logger = logging.getLogger(__name__)

# ============================================================================
# PRECISE CONSTANTS
# ============================================================================

# Troy ounce to grams conversion (exact, 7 decimal places)
# Source: NIST Handbook 44
TROY_OUNCE_TO_GRAMS = 31.1034768

# Gold purity standards
# LBMA Good Delivery standard: minimum 99.5% pure
LONDON_GOLD_PURITY = 0.995

# Shanghai Gold Exchange Au99.99 standard: 99.99% pure
SHANGHAI_GOLD_PURITY = 0.9999

# VAT friction factor for gold imports into China
# Includes: import VAT (typically 13%), handling fees, and market friction
# Net effective friction estimated at 0.35%
VAT_FRICTION_FACTOR = 0.0035

# Fallback USDCNY rate (offshore CNH rate)
# Updated periodically based on market conditions
DEFAULT_USDCNY_FALLBACK = 7.20


# ============================================================================
# EXCHANGE RATE FUNCTIONS
# ============================================================================

async def get_usdcny_rate() -> float:
    """
    Fetch real-time USDCNY exchange rate from AkShare.
    
    Priority:
    1. Try ak.fx_spot_quote() for real-time forex data
    2. Fallback to DEFAULT_USDCNY_FALLBACK (7.20)
    
    Returns:
        float: USDCNY exchange rate
    """
    try:
        import akshare as ak
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        
        # Try to get forex spot quote
        try:
            df = await loop.run_in_executor(
                None, 
                lambda: ak.fx_spot_quote()
            )
            
            # Look for USDCNY or USD/CNY pair
            for _, row in df.iterrows():
                symbol = str(row.get('symbol', '')).upper()
                if 'USD' in symbol and 'CNY' in symbol:
                    price_val = row.get('price', 0)
                    rate = float(price_val if price_val is not None else 0)
                    if rate > 0:
                        logger.info(f"Fetched USDCNY rate: {rate}")
                        return rate
        except Exception as e:
            logger.debug(f"fx_spot_quote failed: {e}")
        
        # Alternative: try currency_boc_safe for Bank of China rates
        try:
            df = await loop.run_in_executor(
                None,
                lambda: ak.currency_boc_safe()
            )
            
            for _, row in df.iterrows():
                currency = str(row.get('货币名称', ''))
                if '美元' in currency or 'USD' in currency.upper():
                    rate_val = row.get('中行折算价', 0)
                    rate = float(rate_val if rate_val is not None else 0)
                    if rate > 0:
                        logger.info(f"Fetched USDCNY rate from BOC: {rate}")
                        return rate
        except Exception as e:
            logger.debug(f"currency_boc_safe failed: {e}")
            
    except Exception as e:
        logger.warning(f"Failed to fetch USDCNY rate: {e}")
    
    # Fallback
    logger.warning(f"Using fallback USDCNY rate: {DEFAULT_USDCNY_FALLBACK}")
    return DEFAULT_USDCNY_FALLBACK


# ============================================================================
# CONVERSION FUNCTIONS
# ============================================================================

def convert_london_to_shanghai(
    london_price_usd_per_oz: float,
    usdcny_rate: float,
    include_vat: bool = True
) -> dict:
    """
    Convert London gold price (USD/oz) to Shanghai gold price (CNY/g).
    
    Formula:
    Shanghai = London($/oz) ÷ 31.1034768 × USDCNY × (0.9999/0.995) × (1 + VAT)
    
    Steps:
    1. Convert USD/oz to USD/g (divide by 31.1034768)
    2. Convert USD/g to CNY/g (multiply by USDCNY)
    3. Adjust for purity difference (multiply by 0.9999/0.995)
    4. Add VAT friction if applicable (multiply by 1.0035)
    
    Args:
        london_price_usd_per_oz: London gold price in USD per troy ounce
        usdcny_rate: USDCNY exchange rate
        include_vat: Whether to include VAT friction factor
    
    Returns:
        dict with all conversion factors and intermediate results:
        - london_usd_per_oz: Input London price
        - usd_per_gram: Price in USD per gram
        - cny_per_gram_unadjusted: Price in CNY per gram (no purity/VAT)
        - purity_factor: Purity adjustment factor (0.9999/0.995)
        - shanghai_theoretical: Shanghai price without VAT
        - shanghai_with_vat: Shanghai price with VAT (if include_vat=True)
        - usdcny_rate: Exchange rate used
        - vat_included: Whether VAT was included
    """
    # Step 1: Convert USD/oz to USD/g
    usd_per_gram = london_price_usd_per_oz / TROY_OUNCE_TO_GRAMS
    
    # Step 2: Convert USD/g to CNY/g
    cny_per_gram_unadjusted = usd_per_gram * usdcny_rate
    
    # Step 3: Purity adjustment
    # Shanghai gold (Au99.99) is purer than London gold (LBMA 99.5%)
    # Higher purity = higher value, so multiply by ratio
    purity_factor = SHANGHAI_GOLD_PURITY / LONDON_GOLD_PURITY
    shanghai_theoretical = cny_per_gram_unadjusted * purity_factor
    
    # Step 4: VAT friction
    shanghai_with_vat = shanghai_theoretical
    if include_vat:
        shanghai_with_vat = shanghai_theoretical * (1 + VAT_FRICTION_FACTOR)
    
    return {
        "london_usd_per_oz": round(london_price_usd_per_oz, 4),
        "usd_per_gram": round(usd_per_gram, 6),
        "cny_per_gram_unadjusted": round(cny_per_gram_unadjusted, 4),
        "purity_factor": round(purity_factor, 6),
        "shanghai_theoretical": round(shanghai_theoretical, 4),
        "shanghai_with_vat": round(shanghai_with_vat, 4),
        "usdcny_rate": round(usdcny_rate, 4),
        "vat_included": include_vat,
        "vat_factor": VAT_FRICTION_FACTOR if include_vat else 0.0,
    }


def convert_shanghai_to_london(
    shanghai_price_cny_per_g: float,
    usdcny_rate: float,
    include_vat: bool = True
) -> dict:
    """
    Convert Shanghai gold price (CNY/g) to London gold price (USD/oz).
    
    Reverse of convert_london_to_shanghai.
    
    Formula:
    London = Shanghai(CNY/g) ÷ (1 + VAT) × (0.995/0.9999) ÷ USDCNY × 31.1034768
    
    Args:
        shanghai_price_cny_per_g: Shanghai gold price in CNY per gram
        usdcny_rate: USDCNY exchange rate
        include_vat: Whether VAT was included in Shanghai price
    
    Returns:
        dict with all conversion factors and intermediate results:
        - shanghai_cny_per_g: Input Shanghai price
        - shanghai_no_vat: Shanghai price without VAT (if applicable)
        - cny_per_gram_adjusted: Price after purity adjustment
        - usd_per_gram: Price in USD per gram
        - london_usd_per_oz: London price in USD per troy ounce
        - purity_factor: Purity adjustment factor (0.995/0.9999)
        - usdcny_rate: Exchange rate used
        - vat_included: Whether VAT was considered
    """
    # Step 1: Remove VAT if it was included
    shanghai_no_vat = shanghai_price_cny_per_g
    if include_vat:
        shanghai_no_vat = shanghai_price_cny_per_g / (1 + VAT_FRICTION_FACTOR)
    
    # Step 2: Reverse purity adjustment
    # London gold is less pure, so divide by ratio
    purity_factor = LONDON_GOLD_PURITY / SHANGHAI_GOLD_PURITY
    cny_per_gram_adjusted = shanghai_no_vat * purity_factor
    
    # Step 3: Convert CNY/g to USD/g
    usd_per_gram = cny_per_gram_adjusted / usdcny_rate
    
    # Step 4: Convert USD/g to USD/oz
    london_usd_per_oz = usd_per_gram * TROY_OUNCE_TO_GRAMS
    
    return {
        "shanghai_cny_per_g": round(shanghai_price_cny_per_g, 4),
        "shanghai_no_vat": round(shanghai_no_vat, 4),
        "cny_per_gram_adjusted": round(cny_per_gram_adjusted, 4),
        "usd_per_gram": round(usd_per_gram, 6),
        "london_usd_per_oz": round(london_usd_per_oz, 4),
        "purity_factor": round(purity_factor, 6),
        "usdcny_rate": round(usdcny_rate, 4),
        "vat_included": include_vat,
        "vat_factor": VAT_FRICTION_FACTOR if include_vat else 0.0,
    }


def verify_round_trip(
    london_price_usd_per_oz: float,
    usdcny_rate: float,
    include_vat: bool = True
) -> dict:
    """
    Verify round-trip conversion accuracy.
    
    London → Shanghai → London should return to original value.
    Error should be < 0.01% for precision verification.
    
    Args:
        london_price_usd_per_oz: Starting London price
        usdcny_rate: Exchange rate
        include_vat: Whether to include VAT
    
    Returns:
        dict with:
        - original_london: Starting price
        - round_trip_london: Price after round-trip
        - absolute_error: Absolute difference
        - percent_error: Percentage error
        - passes_threshold: True if error < 0.01%
    """
    # Forward conversion
    forward = convert_london_to_shanghai(
        london_price_usd_per_oz,
        usdcny_rate,
        include_vat
    )
    
    # Reverse conversion
    reverse = convert_shanghai_to_london(
        forward["shanghai_with_vat"],
        usdcny_rate,
        include_vat
    )
    
    # Calculate error
    round_trip_london = reverse["london_usd_per_oz"]
    absolute_error = abs(round_trip_london - london_price_usd_per_oz)
    percent_error = (absolute_error / london_price_usd_per_oz * 100) if london_price_usd_per_oz > 0 else 0
    
    return {
        "original_london": round(london_price_usd_per_oz, 4),
        "round_trip_london": round(round_trip_london, 4),
        "absolute_error": round(absolute_error, 6),
        "percent_error": round(percent_error, 6),
        "passes_threshold": percent_error < 0.01,
        "threshold_pct": 0.01,
    }


def calculate_premium(
    shanghai_actual: float,
    shanghai_theoretical: float
) -> dict:
    """
    Calculate Shanghai gold premium over theoretical London-converted price.
    
    Args:
        shanghai_actual: Actual Shanghai gold price (CNY/g)
        shanghai_theoretical: Theoretical Shanghai price from London conversion
    
    Returns:
        dict with premium metrics
    """
    absolute_premium = shanghai_actual - shanghai_theoretical
    percent_premium = (absolute_premium / shanghai_theoretical * 100) if shanghai_theoretical > 0 else 0
    
    return {
        "shanghai_actual": round(shanghai_actual, 4),
        "shanghai_theoretical": round(shanghai_theoretical, 4),
        "absolute_premium": round(absolute_premium, 4),
        "percent_premium": round(percent_premium, 4),
    }
