"""
Deposit product API endpoints.

Honesty contract (research-terminal principle):
- Real AkShare data is fetched and tagged ``source="akshare"``.
- The historical hardcoded "大额存单" bank rows are SIMULATED reference data.
  They are only returned when ``allow_simulated_fallback`` is explicitly
  enabled, and they carry ``is_simulated=true`` on every row plus a
  top-level ``simulated_parts`` list — they are never passed off as real.
- With the default policy (``allow_simulated_fallback=false``) a failed
  upstream yields an honest degradation: real parts are returned, failed
  parts are declared in ``unavailable`` instead of being fabricated.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from backend.core.config import settings
from backend.services.cache import realtime_cache

import asyncio
import akshare as ak

router = APIRouter()

# Historical simulated reference table (NOT real quotes — no free upstream
# publishes per-bank deposit products). Kept for reference display only,
# always tagged is_simulated=true.
_SIMULATED_BANK_RATES = [
    {"bank": "工商银行", "product": "大额存单(20万起) 3年", "rate": 2.35},
    {"bank": "建设银行", "product": "大额存单(20万起) 3年", "rate": 2.35},
    {"bank": "农业银行", "product": "大额存单(20万起) 3年", "rate": 2.35},
    {"bank": "中国银行", "product": "大额存单(20万起) 3年", "rate": 2.35},
    {"bank": "招商银行", "product": "大额存单(20万起) 3年", "rate": 2.50},
    {"bank": "浦发银行", "product": "大额存单(20万起) 3年", "rate": 2.55},
    {"bank": "兴业银行", "product": "大额存单(20万起) 3年", "rate": 2.60},
    {"bank": "民生银行", "product": "大额存单(20万起) 3年", "rate": 2.55},
    {"bank": "平安银行", "product": "大额存单(20万起) 3年", "rate": 2.50},
    {"bank": "中信银行", "product": "大额存单(20万起) 3年", "rate": 2.55},
]


def _simulated(rows: list[dict]) -> list[dict]:
    return [
        {**r, "rate_display": f"{r['rate']:.2f}%", "is_simulated": True, "source": "simulated"}
        for r in rows
    ]


@router.get("/rates")
async def get_deposit_rates():
    """
    Get bank deposit rates and treasury yield comparison.

    Response contract:
      deposit_rates[]   real interbank rate row (source="akshare"), and — only
                        if allow_simulated_fallback — tagged simulated rows
      treasury_yields[] real yields, or declared in ``unavailable``
      spreads[]         computed from the parts actually present
      simulated_parts[] which sections contain simulated data (empty = all real)
      unavailable[]     sections that could not be fetched (empty = all real)
    """
    # Rates change at most daily; 15 min cache keeps the endpoint cheap
    # (upstream takes seconds per call).
    cached = await realtime_cache.get("deposit:rates")
    if cached is not None and not (isinstance(cached, dict) and "_stale" in cached):
        return cached

    deposit_rates: list[dict] = []
    treasury_yields: list[dict] = []
    unavailable: list[str] = []
    simulated_parts: list[str] = []

    # --- Real data: interbank reference rate (tagged as what it is) ---
    try:
        df = await asyncio.to_thread(ak.rate_interbank)
        if df is not None and not df.empty:
            latest_rate = float(df.iloc[-1]["利率"])
            deposit_rates.append({
                "bank": "银行间同业",
                "product": "同业拆借利率",
                "rate": round(latest_rate, 2),
                "rate_display": f"{latest_rate:.2f}%",
                "source": "akshare",
                "is_simulated": False,
            })
    except Exception as exc:  # noqa: BLE001
        unavailable.append(f"interbank_rate: {type(exc).__name__}")

    # --- Per-bank deposit products: no real upstream exists ---
    if settings.allow_simulated_fallback:
        deposit_rates.extend(_simulated(_SIMULATED_BANK_RATES))
        simulated_parts.append("deposit_rates")
    else:
        # Honest policy: declare the gap instead of inventing bank quotes.
        unavailable.append(
            "bank_deposit_products: no real upstream source configured "
            "(set allow_simulated_fallback=true to display tagged reference data)"
        )

    # --- Real data: treasury yields ---
    try:
        # Upstream defaults end_date to 20210124 (!) — passing only start_date
        # yields an inverted window and 0 rows. Always pin both bounds.
        from datetime import date as _date
        today = _date.today()
        year_start = today.replace(month=1, day=1).strftime("%Y%m%d")
        bond_df = await asyncio.to_thread(
            ak.bond_china_yield, start_date=year_start, end_date=today.strftime("%Y%m%d")
        )
        if bond_df is not None and not bond_df.empty:
            latest = bond_df.iloc[-1]
            # Upstream columns are '1年','3年',... — '1年期' does NOT exist, and
            # dict.get() would silently fall back to the hardcoded defaults
            # while claiming source="akshare". Use the real columns only.
            treasury_yields = [
                {"tenor": "1年", "yield": float(latest["1年"]), "source": "akshare"},
                {"tenor": "3年", "yield": float(latest["3年"]), "source": "akshare"},
                {"tenor": "5年", "yield": float(latest["5年"]), "source": "akshare"},
                {"tenor": "10年", "yield": float(latest["10年"]), "source": "akshare"},
            ]
            for t in treasury_yields:
                t["yield_display"] = f"{t['yield']:.2f}%"
        else:
            unavailable.append("treasury_yields: empty upstream response")
    except Exception as exc:  # noqa: BLE001
        unavailable.append(f"treasury_yields: {type(exc).__name__}")

    # --- Spreads: computed only from what is actually real (or tagged) ---
    treasury_3y = next((t["yield"] for t in treasury_yields if t["tenor"] == "3年"), None)
    spreads = []
    if treasury_3y is not None:
        for deposit in deposit_rates:
            spread = deposit["rate"] - treasury_3y
            spreads.append({
                "bank": deposit["bank"],
                "product": deposit["product"],
                "deposit_rate": deposit["rate"],
                "treasury_yield": treasury_3y,
                "spread": round(spread, 2),
                "spread_display": f"{spread:+.2f}%",
                "is_simulated": deposit.get("is_simulated", False),
            })

    result = {
        "deposit_rates": deposit_rates,
        "treasury_yields": treasury_yields,
        "spreads": spreads,
        "simulated_parts": simulated_parts,
        "unavailable": unavailable,
        "timestamp": datetime.now().isoformat(),
    }
    # Cache real-only responses; simulated ones too (policy is per-process).
    await realtime_cache.set("deposit:rates", result, ttl_seconds=900)
    return result
