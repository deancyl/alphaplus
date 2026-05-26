"""
Application configuration using Pydantic Settings.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings


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
    cache_ttl_seconds: int = 5
    index_refresh_interval: int = 5
    
    # Rate Limiting (for AkShare)
    akshare_rate_limit: int = 10
    akshare_batch_size: int = 50
    akshare_retry_count: int = 3
    akshare_retry_delay: float = 1.0
    
    # Server
    host: str = "0.0.0.0"
    port: int = 60200
    
    # CORS (configurable via CORS_ORIGINS env var)
    cors_origins: list[str] = _parse_cors_origins()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
