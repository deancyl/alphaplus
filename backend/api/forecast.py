"""
Forecast API router - AI / economic-model trend analysis for indices.

Endpoint contract follows the unified envelope (see backend/core/envelope.py):

    GET /api/v1/analytics/forecast/{index_code}?horizon=20&lookback=500&with_llm=false

    { "ok": true, "action": "forecast", "generatedAt": "...",
      "data": { "index_code", "metrics", "model", "projection", ...,
                "llm": { "enabled", "available", "text", ... } } }

Honesty rules:
* If the price series cannot be fetched, we return ``ok=false`` with
  ``error="unavailable"`` / ``"no_bars"`` - never a simulated curve.
* The LLM section reports ``enabled=false`` when no key is configured, rather
  than emitting a fabricated analysis.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from backend.core.envelope import fail, ok, strip_status
from backend.core.config import settings
from backend.services.akshare_data import akshare_data_service
from backend.services.forecast import (
    DEFAULT_HORIZON,
    DEFAULT_LOOKBACK,
    MAX_HORIZON,
    ForecastError,
    build_forecast,
)
from backend.services.llm_client import analyse_forecast

router = APIRouter()
logger = logging.getLogger(__name__)

# index_code -> AkShare symbol. Kept explicit so an unknown code fails loudly.
INDEX_SYMBOLS: dict[str, str] = {
    "000001": "sh000001",
    "000300": "sh000300",
    "000905": "sh000905",
    "000852": "sh000852",
    "000016": "sh000016",
    "000688": "sh000688",
    "000903": "sh000903",
    "000922": "sh000922",
    "399001": "sz399001",
    "399006": "sz399006",
    "399102": "sz399102",
    "399303": "sz399303",
    "399971": "sz399971",
}


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


@router.get("/forecast/{index_code}")
async def get_forecast(
    index_code: str,
    horizon: int = Query(DEFAULT_HORIZON, ge=1, le=MAX_HORIZON, description="预测交易日数"),
    lookback: int = Query(DEFAULT_LOOKBACK, ge=60, le=2500, description="估计漂移/波动的回看窗口"),
    with_llm: bool = Query(False, description="是否附加 LLM 解读（需配置密钥）"),
):
    """Economic-model trend forecast with optional LLM interpretation."""
    action = "forecast"
    symbol = INDEX_SYMBOLS.get(index_code)
    index_name = settings.CORE_INDICES.get(index_code)

    if symbol is None or index_name is None:
        return _reject(
            fail(
                action, "invalid_index_code", 400,
                message=f"unsupported index code: {index_code}",
            )
        )

    rows = await akshare_data_service.get_index_daily_history(symbol)
    if not rows:
        return _reject(
            fail(action, "unavailable", 502, message="index daily history unavailable")
        )

    closes = [r["close"] for r in rows]
    dates = [r["date"] for r in rows]

    try:
        result = build_forecast(
            index_code=index_code,
            index_name=index_name,
            closes=closes,
            dates=dates,
            lookback=_clamp(lookback, 60, 2500),
            horizon=_clamp(horizon, 1, MAX_HORIZON),
        )
    except ForecastError as exc:
        return _reject(fail(action, exc.code, 400, message=exc.message))

    data = result.to_dict()
    data["available"] = {
        "price_series": True,
        "observations": result.observations,
        "as_of": result.as_of,
    }

    llm_section = None
    if with_llm:
        llm_result = await analyse_forecast(data)
        llm_section = llm_result.to_dict()
    else:
        from backend.services.llm_client import llm_configured

        llm_section = {
            "enabled": llm_configured(),
            "available": False,
            "api_style": settings.llm_api_style,
            "model": settings.llm_model if llm_configured() else None,
            "text": None,
            "error": None if llm_configured() else "llm_not_configured",
            "usage": None,
            "note": "use ?with_llm=true to request an AI interpretation",
        }

    data["llm"] = llm_section
    return strip_status(ok(action, data, index_code=index_code))


def _reject(payload: dict):
    """Return a failure envelope with its HTTP status code."""
    from fastapi.responses import JSONResponse

    status = payload.pop("http_status", 502)
    return JSONResponse(status_code=status, content=payload)
