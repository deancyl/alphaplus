"""
Main FastAPI application with lifespan and APScheduler integration.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.core import settings, init_db_pragma, async_engine, Base
from backend.services.scheduler import scheduler_service
from backend.services.cache import realtime_cache
from backend.services.pandas_cache import GLOBAL_FUND_DF


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown."""
    # ===== STARTUP =====
    
    # 1. Initialize database with WAL mode
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db_pragma(str(db_path))
    
    # 2. Create tables if not exist
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 3. Initialize real-time cache
    await realtime_cache.initialize()
    
    # 4. Initialize Pandas in-memory cache (lazy load)
    GLOBAL_FUND_DF.df
    
    # 5. Start scheduler
    if settings.scheduler_enabled:
        await scheduler_service.start()
    
    yield
    
    # ===== SHUTDOWN =====
    
    # 1. Stop scheduler gracefully
    if settings.scheduler_enabled:
        await scheduler_service.stop()
    
    # 2. Clear cache
    await realtime_cache.clear()
    
    # 3. Close database connections
    await async_engine.dispose()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and register routers FIRST (before static mount)
from backend.api.fund import router as fund_router
from backend.api.market import router as market_router
from backend.api.analytics import router as analytics_router
from backend.api.pool import pool_router
from backend.api.favorites import favorites_router
from backend.api.insurance import router as insurance_router
from backend.api.gold import router as gold_router

app.include_router(fund_router, prefix="/api/v1/fund", tags=["Fund"])
app.include_router(market_router, prefix="/api/v1/market", tags=["Market"])
app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(pool_router, prefix="/api/v1", tags=["pool"])
app.include_router(favorites_router, prefix="/api/v1", tags=["favorites"])
app.include_router(insurance_router, prefix="/api/v1/insurance", tags=["Insurance"])
app.include_router(gold_router, prefix="/api/v1/gold", tags=["Gold"])


# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }


# Mount static files (frontend dist) - MUST be last
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
