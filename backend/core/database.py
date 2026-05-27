"""
Database configuration with WAL mode for concurrent access.
"""
import asyncio
import functools
import logging
import random
import sqlite3
from pathlib import Path
from typing import Callable

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

def retry_on_sqlite_busy(
    max_retries: int = 3,
    base_delay_ms: float = 50,
    max_delay_ms: float = 500,
    jitter: bool = True
) -> Callable:
    """
    SQLite写操作指数退避重试装饰器
    
    仅在SQLITE_BUSY错误(database is locked)时重试
    其他错误立即抛出
    
    公式: delay = min(max_delay, base_delay * 2^attempt) + random(0, jitter)
    
    Args:
        max_retries: 最大重试次数 (default: 3)
        base_delay_ms: 基础延迟毫秒 (default: 50ms)
        max_delay_ms: 最大延迟毫秒 (default: 500ms)
        jitter: 是否添加随机抖动 (default: True)
    
    Returns:
        Decorated function
    
    Example:
        @retry_on_sqlite_busy(max_retries=3, base_delay_ms=50)
        async def write_to_db():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                
                except OperationalError as e:
                    is_busy_error = False
                    error_str = str(e).lower()
                    
                    # Check if it's SQLITE_BUSY error (database is locked)
                    # Method 1: Check orig attribute (SQLAlchemy wrapped error)
                    if hasattr(e, 'orig') and e.orig is not None:
                        if isinstance(e.orig, sqlite3.OperationalError):
                            if hasattr(e.orig, 'sqlite_errorcode'):
                                is_busy_error = (e.orig.sqlite_errorcode == sqlite3.SQLITE_BUSY)
                    
                    # Method 2: Check error message string
                    if not is_busy_error:
                        is_busy_error = 'database is locked' in error_str
                    
                    if is_busy_error:
                        last_exception = e
                        
                        if attempt < max_retries:
                            # Calculate exponential backoff delay
                            delay_ms = min(max_delay_ms, base_delay_ms * (2 ** attempt))
                            
                            # Add jitter to prevent thundering herd
                            if jitter:
                                jitter_ms = random.uniform(0, base_delay_ms)
                                delay_ms += jitter_ms
                            
                            delay_s = delay_ms / 1000.0
                            
                            logger.warning(
                                f"SQLite database locked (attempt {attempt + 1}/{max_retries + 1}), "
                                f"retrying in {delay_s:.3f}s: {e}"
                            )
                            
                            await asyncio.sleep(delay_s)
                            continue
                    
                    # Non-SQLITE_BUSY OperationalError: re-raise immediately
                    raise
                
                except sqlite3.OperationalError as e:
                    # Direct sqlite3 error (not wrapped by SQLAlchemy)
                    is_busy_error = False
                    
                    if hasattr(e, 'sqlite_errorcode'):
                        is_busy_error = (e.sqlite_errorcode == sqlite3.SQLITE_BUSY)
                    elif 'database is locked' in str(e).lower():
                        is_busy_error = True
                    
                    if is_busy_error:
                        last_exception = e
                        
                        if attempt < max_retries:
                            # Calculate exponential backoff delay
                            delay_ms = min(max_delay_ms, base_delay_ms * (2 ** attempt))
                            
                            # Add jitter to prevent thundering herd
                            if jitter:
                                jitter_ms = random.uniform(0, base_delay_ms)
                                delay_ms += jitter_ms
                            
                            delay_s = delay_ms / 1000.0
                            
                            logger.warning(
                                f"SQLite database locked (attempt {attempt + 1}/{max_retries + 1}), "
                                f"retrying in {delay_s:.3f}s: {e}"
                            )
                            
                            await asyncio.sleep(delay_s)
                            continue
                    
                    # Non-SQLITE_BUSY sqlite3 error: re-raise immediately
                    raise
                
                except Exception as e:
                    # Non-OperationalError: re-raise immediately
                    raise
            
            # All retries exhausted
            if last_exception:
                logger.error(
                    f"SQLite database still locked after {max_retries + 1} attempts, "
                    f"giving up: {last_exception}"
                )
                raise last_exception
        
        return wrapper
    return decorator


# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "alphaplus.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# SQLite URL
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
SYNC_DATABASE_URL = f"sqlite:///{DB_PATH}"


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# Async engine for FastAPI
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db():
    """Dependency to get async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def init_db_pragma(db_path: str = None):
    """
    Initialize SQLite with WAL mode and performance optimizations.
    Should be called once at application startup.
    """
    from sqlite3 import connect
    
    db_path = db_path or str(DB_PATH)
    conn = connect(db_path)
    
    # Enable WAL mode for concurrent reads
    conn.execute("PRAGMA journal_mode=WAL")
    
    # Performance pragmas
    conn.execute("PRAGMA synchronous=NORMAL")      # Safe for WAL mode
    conn.execute("PRAGMA cache_size=-64000")       # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")       # Temp tables in RAM
    conn.execute("PRAGMA mmap_size=268435456")     # 256MB mmap
    conn.execute("PRAGMA busy_timeout=5000")       # 5s write lock timeout
    conn.execute("PRAGMA foreign_keys=ON")         # Enable FK constraints
    
    conn.close()


@event.listens_for(async_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Set pragmas on each connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
