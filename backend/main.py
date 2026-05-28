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
    - Hot keys from metadata
    """
    logger.info("Starting TieredCache warmup...")
    
    warmup_tasks = []
    
    async def warmup_indices():
        """Load all 17 core index valuations into cache."""
        try:
            valuations = await get_all_indices_valuation()
            for idx_data in valuations:
                key = f"index_valuation:{idx_data['index_code']}"
                tiered_cache.set(key, idx_data, ttl=3600)
            logger.info(f"Warmed up {len(valuations)} index valuations")
            return len(valuations)
        except Exception as e:
            logger.warning(f"Failed to warmup index valuations: {e}")
            return 0
    
    async def warmup_fear_greed():
        """Load fear-greed index data into cache."""
        try:
            key = "fear_greed:latest"
            tiered_cache.set(key, {"status": "warmup_placeholder"}, ttl=300)
            logger.info("Warmed up fear-greed index placeholder")
            return 1
        except Exception as e:
            logger.warning(f"Failed to warmup fear-greed: {e}")
            return 0
    
    async def warmup_index_quotes():
        """Load real-time index quotes into cache."""
        try:
            quotes = await akshare_data_service.get_index_quotes()
            key = "index_quotes:all"
            tiered_cache.set(key, quotes, ttl=300)
            logger.info(f"Warmed up {len(quotes)} index quotes")
            return len(quotes)
        except Exception as e:
            logger.warning(f"Failed to warmup index quotes: {e}")
            return 0
    
    async def warmup_hot_keys():
        """Warm L1 cache with hot keys from metadata."""
        try:
            warmed = await tiered_cache.warm_cache(top_n=100)
            logger.info(f"Warmed {warmed} hot keys from metadata")
            return warmed
        except Exception as e:
            logger.warning(f"Failed to warmup hot keys: {e}")
            return 0
    
    warmup_tasks = [
        warmup_indices(),
        warmup_fear_greed(),
        warmup_index_quotes(),
        warmup_hot_keys(),
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
from backend.api.wmp import router as wmp_router

app.include_router(fund_router, prefix="/api/v1/fund", tags=["Fund"])
app.include_router(market_router, prefix="/api/v1/market", tags=["Market"])
app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(pool_router, prefix="/api/v1", tags=["pool"])
app.include_router(favorites_router, prefix="/api/v1", tags=["favorites"])
app.include_router(insurance_router, prefix="/api/v1/insurance", tags=["Insurance"])
app.include_router(gold_router, prefix="/api/v1/gold", tags=["Gold"])
app.include_router(portfolio_router, prefix="/api/v1/portfolio", tags=["Portfolio"])
app.include_router(wmp_router, prefix="/api/v1/wmp", tags=["WMP"])


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


@app.get("/api/cache/metrics")
async def cache_metrics():
    """
    Get detailed cache performance metrics for all layers.
    
    Returns:
        - Latency percentiles (p50, p95, p99) for each layer
        - Hit rates for L1, L2, L3 and combined
        - Capacity information
        - L3 DataFrame and Parquet statistics
        - Target validation (90% combined hit rate)
    """
    stats = tiered_cache.stats()
    latency = stats.get("latency", {})
    l1 = stats.get("l1", {})
    l2 = stats.get("l2", {})
    l3 = stats.get("l3", {})
    combined = stats.get("combined", {})
    l3_parquet = l3.get("parquet", {})
    l3_dataframe = l3.get("dataframe", {})
    
    return {
        "status": "ok",
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "performance": {
            "latency_ms": {
                "overall": latency,
                "l3_parquet": l3_parquet.get("latency", {}),
                "l3_dataframe": l3_dataframe.get("latency", {}),
            },
            "hit_rates": {
                "l1_pct": l1.get("hit_rate_pct", 0.0),
                "l2_pct": l2.get("hit_rate_pct", 0.0),
                "l3_pct": l3.get("hit_rate_pct", 0.0),
                "combined_pct": combined.get("hit_rate_pct", 0.0),
                "target_pct": 90.0,
                "target_achieved": combined.get("target_achieved", False),
            },
        },
        "capacity": {
            "l1": {
                "size": l1.get("size", 0),
                "maxsize": l1.get("maxsize", 1000),
                "usage_pct": round(l1.get("size", 0) / l1.get("maxsize", 1) * 100, 2),
                "ttl_seconds": l1.get("ttl_seconds", 300),
            },
            "l2": {
                "entries": l2.get("total_entries", 0),
                "size_mb": round(l2.get("total_size_bytes", 0) / 1024 / 1024, 2),
                "evictions": l2.get("evictions", 0),
            },
            "l3": {
                "parquet": {
                    "file_count": l3_parquet.get("file_count", 0),
                    "size_mb": l3_parquet.get("total_size_mb", 0),
                    "partitions": l3_parquet.get("partitions", []),
                },
                "dataframe": {
                    "status": l3_dataframe.get("status", "unknown"),
                    "row_count": l3_dataframe.get("row_count", 0),
                    "memory_mb": l3_dataframe.get("memory_mb", 0),
                },
            },
        },
        "targets": {
            "l2_latency_p95_ms": {"target": 8.0, "current": l3_dataframe.get("latency", {}).get("p95_ms", 0.0)},
            "l3_latency_p95_ms": {"target": 20.0, "current": l3_parquet.get("latency", {}).get("p95_ms", 0.0)},
            "combined_hit_rate_pct": {"target": 90.0, "current": combined.get("hit_rate_pct", 0.0)},
        },
        "hot_keys": stats.get("metadata", {}).get("hot_keys", []),
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
