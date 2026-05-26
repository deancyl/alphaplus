"""
Test configuration.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from backend.core import settings
from backend.services.cache import realtime_cache


@pytest.fixture(autouse=True)
def mock_akshare():
    """Mock AkShare calls to avoid network requests in tests."""
    import backend.services.index_valuation as iv_module
    import backend.services.aip_calculator as aip_module
    
    original_fetch_pe = iv_module._fetch_pe_data
    original_fetch_pb = iv_module._fetch_pb_data
    original_fetch_dividend = iv_module._fetch_dividend_data
    
    async def mock_fetch_pe(index_name):
        return None
    
    async def mock_fetch_pb(index_name):
        return None
    
    async def mock_fetch_dividend(index_name):
        return None
    
    iv_module._fetch_pe_data = mock_fetch_pe
    iv_module._fetch_pb_data = mock_fetch_pb
    iv_module._fetch_dividend_data = mock_fetch_dividend
    
    yield
    
    iv_module._fetch_pe_data = original_fetch_pe
    iv_module._fetch_pb_data = original_fetch_pb
    iv_module._fetch_dividend_data = original_fetch_dividend


@pytest.fixture
async def app():
    """Create test FastAPI app without static mount."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )
    
    # Register routers (NO static mount)
    from backend.api.fund import router as fund_router
    from backend.api.market import router as market_router
    from backend.api.analytics import router as analytics_router
    from backend.api.pool import pool_router
    from backend.api.favorites import favorites_router
    
    app.include_router(fund_router, prefix="/api/v1/fund", tags=["Fund"])
    app.include_router(market_router, prefix="/api/v1/market", tags=["Market"])
    app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])
    app.include_router(pool_router, prefix="/api/v1", tags=["pool"])
    app.include_router(favorites_router, prefix="/api/v1", tags=["favorites"])
    
    # Initialize cache
    await realtime_cache.initialize()
    
    yield app
    
    # Cleanup
    await realtime_cache.clear()


@pytest.fixture
async def client(app: FastAPI):
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
