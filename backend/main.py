"""
Main FastAPI application with lifespan and APScheduler integration.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.core import settings, init_db_pragma, async_engine, Base
from backend.services.scheduler import scheduler_service
from backend.services.cache import realtime_cache
from backend.services.pandas_cache import GLOBAL_FUND_DF
from backend.services.tiered_cache import tiered_cache
from backend.services.akshare_data import akshare_data_service
from backend.services.index_valuation import get_all_indices_valuation, CORE_INDICES
from backend.core.process_manager import start_scheduler_worker, stop_scheduler_worker, get_process_manager

logger = logging.getLogger(__name__)


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
    
    # 5. Warmup TieredCache (v0.1.14)
    await _warmup_cache()
    
    # 6. Start isolated scheduler worker process (if enabled)
    if settings.scheduler_enabled:
        # Start the isolated worker process for memory isolation
        worker_started = start_scheduler_worker()
        if worker_started:
            logger.info("Scheduler worker process started")
        
        # Also start APScheduler for cron triggers (delegates to worker)
        await scheduler_service.start()
    
    yield
    
    # ===== SHUTDOWN =====
    
    # 1. Stop isolated worker process gracefully
    if settings.scheduler_enabled:
        # Stop APScheduler first
        await scheduler_service.stop()
        
        # Stop the worker process
        stop_scheduler_worker()
        logger.info("Scheduler worker process stopped")
    
    # 2. Clear caches
    await realtime_cache.clear()
    tiered_cache.clear()
    
    # 3. Close database connections
    await async_engine.dispose()


async def _warmup_cache():
    """
    Warmup TieredCache with frequently accessed data.
    
    Loads:
    - Top 50 index valuations (17 core indices)
    - Hot funds data (placeholder for now)
    - Fear-greed index
    """
    logger.info("Starting TieredCache warmup...")
    
    warmup_tasks = []
    
    # 1. Warmup index valuations
    async def warmup_indices():
        """Load all 17 core index valuations into cache."""
        try:
            valuations = await get_all_indices_valuation()
            for idx_data in valuations:
                key = f"index_valuation:{idx_data['index_code']}"
                tiered_cache.set(key, idx_data, ttl=3600)  # 1 hour TTL
            logger.info(f"Warmed up {len(valuations)} index valuations")
            return len(valuations)
        except Exception as e:
            logger.warning(f"Failed to warmup index valuations: {e}")
            return 0
    
    # 2. Warmup fear-greed index
    async def warmup_fear_greed():
        """Load fear-greed index data into cache."""
        try:
            # Placeholder: would fetch from DB or API
            # For now, just set a placeholder key
            key = "fear_greed:latest"
            # This would be replaced with actual data fetch
            tiered_cache.set(key, {"status": "warmup_placeholder"}, ttl=300)
            logger.info("Warmed up fear-greed index placeholder")
            return 1
        except Exception as e:
            logger.warning(f"Failed to warmup fear-greed: {e}")
            return 0
    
    # 3. Warmup index quotes
    async def warmup_index_quotes():
        """Load real-time index quotes into cache."""
        try:
            quotes = await akshare_data_service.get_index_quotes()
            key = "index_quotes:all"
            tiered_cache.set(key, quotes, ttl=300)  # 5 min TTL for real-time
            logger.info(f"Warmed up {len(quotes)} index quotes")
            return len(quotes)
        except Exception as e:
            logger.warning(f"Failed to warmup index quotes: {e}")
            return 0
    
    # Run warmup tasks in parallel
    warmup_tasks = [
        warmup_indices(),
        warmup_fear_greed(),
        warmup_index_quotes(),
    ]
    
    results = await asyncio.gather(*warmup_tasks, return_exceptions=True)
    
    total_entries = sum(r for r in results if isinstance(r, int))
    logger.info(f"TieredCache warmup complete: {total_entries} entries loaded")


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
from backend.api.portfolio import router as portfolio_router

app.include_router(fund_router, prefix="/api/v1/fund", tags=["Fund"])
app.include_router(market_router, prefix="/api/v1/market", tags=["Market"])
app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(pool_router, prefix="/api/v1", tags=["pool"])
app.include_router(favorites_router, prefix="/api/v1", tags=["favorites"])
app.include_router(insurance_router, prefix="/api/v1/insurance", tags=["Insurance"])
app.include_router(gold_router, prefix="/api/v1/gold", tags=["Gold"])
app.include_router(portfolio_router, prefix="/api/v1/portfolio", tags=["Portfolio"])


# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }


# Cache statistics endpoint (v0.1.14)
@app.get("/api/cache/stats")
async def cache_stats():
    """
    Get TieredCache statistics.
    
    Returns:
        L1 (memory) and L2 (Parquet) cache stats
    """
    stats = tiered_cache.stats()
    return {
        "status": "ok",
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        **stats,
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
