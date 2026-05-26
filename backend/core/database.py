"""
Database configuration with WAL mode for concurrent access.
"""
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker

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
