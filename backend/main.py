"""
Main FastAPI application with lifespan and APScheduler integration.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
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


# Warmup status tracking
_warmup_status = {
    "started": False,
    "completed": False,
    "tasks_total": 5,
    "tasks_completed": 0,
    "errors": [],
    "start_time": None,
}


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
    Non-blocking warmup with timeout and fallback data.
    
    Runs warmup tasks in background so service starts immediately.
    Uses reduced retry count and timeout protection.
    Injects fallback data if warmup fails.
    """
    if not settings.warmup_enabled:
        logger.info("Warmup disabled by config")
        return
    
    # Immediately inject fallback data so service is operational
    _inject_fallback_data()
    
    _warmup_status["started"] = True
    _warmup_status["start_time"] = datetime.now().isoformat()
    
    async def execute_warmup():
        """Execute warmup tasks with timeout protection."""
        try:
            await asyncio.wait_for(
                _run_warmup_tasks(),
                timeout=settings.warmup_timeout_seconds
            )
            _warmup_status["completed"] = True
            logger.info(f"Warmup completed successfully")
        except asyncio.TimeoutError:
            logger.warning(f"Warmup timed out after {settings.warmup_timeout_seconds}s")
            _warmup_status["errors"].append("timeout")
            _inject_fallback_data()
        except Exception as e:
            logger.error(f"Warmup failed: {e}")
            _warmup_status["errors"].append(str(e))
            _inject_fallback_data()
    
    if settings.warmup_blocking:
        await execute_warmup()
    else:
        asyncio.create_task(execute_warmup())
        logger.info("Warmup started in background, service accepting requests")


async def _run_warmup_tasks():
    """Execute warmup tasks that don't require external APIs."""
    tasks = [
        _warmup_hot_keys(),
        _warmup_hot_funds(),
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, result in enumerate(results):
        if isinstance(result, int):
            _warmup_status["tasks_completed"] += 1
        elif isinstance(result, Exception):
            logger.warning(f"Warmup task {i} failed: {result}")


async def _warmup_indices_with_fallback():
    """Warmup index valuations with fallback injection."""
    try:
        valuations = await get_all_indices_valuation()
        for idx_data in valuations:
            key = f"index_valuation:{idx_data['index_code']}"
            tiered_cache.set(key, idx_data, ttl=3600)
        logger.info(f"Warmed up {len(valuations)} index valuations")
        return len(valuations)
    except Exception as e:
        logger.warning(f"Index valuation warmup failed: {e}")
        from backend.services.warmup_fallback import get_fallback_index_valuations
        fallback_data = get_fallback_index_valuations()
        for idx_data in fallback_data:
            key = f"index_valuation:{idx_data['index_code']}"
            tiered_cache.set(key, idx_data, ttl=3600)
        logger.info(f"Injected {len(fallback_data)} fallback index valuations")
        return 0


async def _warmup_fear_greed_with_fallback():
    """Warmup fear-greed index with fallback injection."""
    try:
        # Direct database query instead of calling FastAPI endpoint
        from backend.models.fund import MarketFearGreedSentimentHistory
        from backend.core import async_engine
        from sqlalchemy import select
        
        async with async_engine.connect() as conn:
            result = await conn.execute(
                select(MarketFearGreedSentimentHistory)
                .order_by(MarketFearGreedSentimentHistory.trade_date.desc())
                .limit(30)
            )
            rows = result.fetchall()
            
            if rows:
                data = [
                    {
                        "trade_date": row.trade_date,
                        "composite_score": row.composite_score,
                        "sentiment_status": row.sentiment_status,
                        "is_fallback": False,
                    }
                    for row in rows
                ]
                tiered_cache.set("fear_greed:latest", data, ttl=300)
                logger.info(f"Warmed up fear-greed index with {len(data)} records")
                return len(data)
        return 0
    except Exception as e:
        logger.warning(f"Fear-greed warmup failed: {e}")
        from backend.services.warmup_fallback import get_fallback_fear_greed
        fallback_data = get_fallback_fear_greed()
        tiered_cache.set("fear_greed:latest", fallback_data, ttl=300)
        logger.info("Injected fallback fear-greed data")
        return 0


async def _warmup_index_quotes_with_fallback():
    """Warmup index quotes with fallback injection."""
    try:
        quotes = await akshare_data_service.get_index_quotes()
        tiered_cache.set("index_quotes:all", quotes, ttl=300)
        logger.info(f"Warmed up {len(quotes)} index quotes")
        return len(quotes)
    except Exception as e:
        logger.warning(f"Index quotes warmup failed: {e}")
        from backend.services.warmup_fallback import get_fallback_index_quotes
        fallback_data = get_fallback_index_quotes()
        tiered_cache.set("index_quotes:all", fallback_data, ttl=300)
        logger.info("Injected fallback index quotes")
        return 0


async def _warmup_hot_keys():
    """Warm L1 cache with hot keys from metadata."""
    try:
        warmed = await tiered_cache.warm_cache(top_n=100)
        logger.info(f"Warmed {warmed} hot keys from metadata")
        return warmed
    except Exception as e:
        logger.warning(f"Hot keys warmup failed: {e}")
        return 0


async def _warmup_hot_funds():
    """Pre-warm top N funds from GLOBAL_FUND_DF."""
    try:
        df = GLOBAL_FUND_DF.df
        if df is not None and not df.empty:
            top_funds = df.nlargest(settings.warmup_top_funds_count, 'scale') if 'scale' in df.columns else df.head(settings.warmup_top_funds_count)
            warmed = 0
            for _, fund in top_funds.iterrows():
                key = f"fund:{fund.get('fund_code', fund.get('code', ''))}"
                tiered_cache.set(key, fund.to_dict(), ttl=3600)
                warmed += 1
            logger.info(f"Warmed up {warmed} hot funds")
            return warmed
        return 0
    except Exception as e:
        logger.warning(f"Hot funds warmup failed: {e}")
        return 0


def _inject_fallback_data():
    """Inject all fallback data when warmup fails completely."""
    from backend.services.warmup_fallback import (
        get_fallback_index_valuations,
        get_fallback_fear_greed,
        get_fallback_index_quotes,
    )
    
    for idx_data in get_fallback_index_valuations():
        key = f"index_valuation:{idx_data['index_code']}"
        tiered_cache.set(key, idx_data, ttl=3600)
    
    tiered_cache.set("fear_greed:latest", get_fallback_fear_greed(), ttl=300)
    
    tiered_cache.set("index_quotes:all", get_fallback_index_quotes(), ttl=300)
    
    logger.info("Injected all fallback data into cache")


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
    """Health check endpoint with warmup status."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "warmup": _warmup_status,
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
