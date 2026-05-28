"""
Application configuration using Pydantic Settings.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_cors_origins() -> list[str]:
    """Parse CORS origins from environment variable."""
    env_origins = os.getenv("CORS_ORIGINS", "")
    if env_origins:
        return [origin.strip() for origin in env_origins.split(",") if origin.strip()]
    return ["http://localhost:60201", "http://127.0.0.1:60201", "http://0.0.0.0:60201"]


class Settings(BaseSettings):
    """Application settings."""
    
    # App
    app_name: str = "财富 Alpha+ 投研工作台"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Database
    database_path: str = "data/alphaplus.db"
    
    # Scheduler
    scheduler_enabled: bool = False
    fund_sync_hour: int = 18
    bond_sync_hour: int = 17
    
    # Cache
    cache_ttl_seconds: int = 30
    index_refresh_interval: int = 5
    
    # Rate Limiting (for AkShare)
    akshare_rate_limit: int = 10
    akshare_batch_size: int = 50
    akshare_retry_count: int = 3
    akshare_retry_delay: float = 1.0
    
    # AData Direct Mode
    adata_enabled: bool = True
    adata_fallback_to_akshare: bool = True
    adata_cache_ttl_ms: int = 100
    adata_batch_size: int = 50
    adata_coalesce_window_ms: int = 50
    
    # Server
    host: str = "0.0.0.0"
    port: int = 60200
    
    # Thread Pool
    thread_pool_workers: int = 4
    async_timeout: float = 30.0
    
    # DuckDB Connection Pool
    duckdb_pool_readers: int = 4
    duckdb_pool_writers: int = 1
    
    # CORS (configurable via CORS_ORIGINS env var)
    cors_origins: list[str] = _parse_cors_origins()
    
    # Cache Warmup Configuration
    warmup_top_funds_count: int = 50
    warmup_index_valuation_codes: list[str] = [
        "000300", "000905", "399006", "000852", "H30533", 
        "000016", "399102"
    ]
    
    # Startup/Warmup Configuration
    # Enable or disable cache warmup on application startup
    warmup_enabled: bool = True
    # Maximum time in seconds to wait for warmup operations
    warmup_timeout_seconds: float = 10.0
    # Number of retry attempts for warmup operations (reduced from default 5)
    warmup_retry_count: int = 1
    # Whether warmup should block application startup (False = non-blocking)
    warmup_blocking: bool = False
    # Enable fallback to degraded mode if warmup fails
    warmup_fallback_enabled: bool = True
    
    # Quantitative Analysis Parameters
    fear_greed_history_days: int = 30
    erp_history_days: int = 100
    crowding_history_records: int = 240
    
    # Gold Arbitrage Calibration
    gold_shanghai_purity: float = 0.9999
    gold_london_purity: float = 0.9950
    gold_vat_friction_factor: float = 0.0035
    
    # Core Indices Configuration (17 indices)
    CORE_INDICES: dict[str, str] = {
        "000300": "沪深300",
        "000905": "中证500",
        "000852": "中证1000",
        "399006": "创业板指",
        "000016": "上证50",
        "399102": "创业板综",
        "H30533": "中证A50",
        "000001": "上证指数",
        "399001": "深证成指",
        "000688": "科创50",
        "399303": "国证2000",
        "000903": "中证100",
        "000922": "中证红利",
        "931697": "中证消费",
        "931800": "中证医药",
        "931631": "中证科技",
        "399971": "中证传媒"
    }
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
