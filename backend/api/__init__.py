"""
API module exports.
"""
from backend.api.fund import router as fund_router
from backend.api.market import router as market_router
from backend.api.analytics import router as analytics_router

__all__ = [
    "fund_router",
    "market_router",
    "analytics_router",
]

# Router exports for main.py
from backend.api.fund import router as fund
from backend.api.market import router as market
from backend.api.analytics import router as analytics