"""
Parquet cache for fund holdings data with Hive partitioning.

Used for:
- Anti-scraping protection through cached Parquet files
- Fast bulk data loading for OLAP queries
- Physical lock to prevent redundant API calls
"""
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from datetime import date
from typing import Optional, List, Dict, Any
import logging
import fcntl
import json

logger = logging.getLogger(__name__)

# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "parquet"
LOCK_DIR = Path(__file__).parent.parent.parent / "data" / "locks"


def ensure_directories():
    """Ensure cache and lock directories exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_DIR.mkdir(parents=True, exist_ok=True)


class PhysicalLock:
    """
    File-based lock to prevent redundant API calls across processes.
    
    Uses fcntl for POSIX-compliant file locking.
    """
    
    def __init__(self, lock_name: str, timeout: int = 300):
        """
        Initialize physical lock.
        
        Args:
            lock_name: Name of the lock (e.g., 'holdings_ingestion')
            timeout: Lock timeout in seconds (default 5 minutes)
        """
        ensure_directories()
        self.lock_path = LOCK_DIR / f".{lock_name}.lock"
        self.timeout = timeout
        self.lock_file: Optional[Any] = None
    
    def acquire(self) -> bool:
        """
        Acquire the lock.
        
        Returns:
            True if lock acquired, False if already locked by another process
        """
        try:
            self.lock_file = open(self.lock_path, 'w')
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Write lock metadata
            self.lock_file.write(json.dumps({
                'pid': __import__('os').getpid(),
                'timestamp': __import__('time').time(),
            }))
            self.lock_file.flush()
            return True
        except (IOError, OSError):
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            return False
    
    def release(self):
        """Release the lock."""
        if self.lock_file:
            try:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
                self.lock_path.unlink(missing_ok=True)
            except (IOError, OSError):
                pass
            finally:
                self.lock_file = None
    
    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(f"Could not acquire lock: {self.lock_path}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def export_holdings_to_parquet(
    holdings: List[Dict],
    partition_by_quarter: bool = True
) -> Path:
    """
    Export fund holdings to Parquet with Hive partitioning.
    
    Args:
        holdings: List of holding dicts
        partition_by_quarter: If True, partition by quarter_date
    
    Returns:
        Path to the Parquet file/directory
    """
    ensure_directories()
    
    if not holdings:
        raise ValueError("No holdings to export")
    
    # Convert to PyArrow Table
    table = pa.Table.from_pylist(holdings)
    
    if partition_by_quarter:
        # Hive partitioning by quarter_date
        # Structure: data/parquet/fund_holdings/quarter_date=2024-03-31/
        base_path = CACHE_DIR / "fund_holdings"
        
        # Write with partitioning
        pq.write_to_dataset(
            table,
            root_path=str(base_path),
            partition_cols=['quarter_date'],
            compression='snappy',
        )
        
        logger.info(f"Exported {len(holdings)} holdings to {base_path} with Hive partitioning")
        return base_path
    else:
        # Single Parquet file
        output_path = CACHE_DIR / "fund_holdings.parquet"
        pq.write_table(table, output_path, compression='snappy')
        logger.info(f"Exported {len(holdings)} holdings to {output_path}")
        return output_path


def load_holdings_from_parquet(
    quarter_date: Optional[date] = None
) -> List[Dict]:
    """
    Load fund holdings from Parquet cache.
    
    Args:
        quarter_date: If provided, load only holdings for this quarter
    
    Returns:
        List of holding dicts
    """
    base_path = CACHE_DIR / "fund_holdings"
    
    if not base_path.exists():
        # Try single file
        single_file = CACHE_DIR / "fund_holdings.parquet"
        if single_file.exists():
            table = pq.read_table(single_file)
            return table.to_pylist()
        return []
    
    # Read with optional partition filter
    filters = None
    if quarter_date:
        filters = [('quarter_date', '=', str(quarter_date))]
    
    table = pq.read_table(base_path, filters=filters)
    holdings = table.to_pylist()
    
    logger.info(f"Loaded {len(holdings)} holdings from Parquet cache")
    return holdings


def get_parquet_cache_stats() -> Dict:
    """
    Get statistics about the Parquet cache.
    
    Returns:
        Dict with cache stats (file_count, total_size_bytes, partitions)
    """
    ensure_directories()
    
    stats = {
        'file_count': 0,
        'total_size_bytes': 0,
        'partitions': [],
    }
    
    base_path = CACHE_DIR / "fund_holdings"
    
    if base_path.exists():
        for partition_dir in base_path.iterdir():
            if partition_dir.is_dir() and partition_dir.name.startswith('quarter_date='):
                stats['partitions'].append(partition_dir.name.replace('quarter_date=', ''))
                for parquet_file in partition_dir.glob('*.parquet'):
                    stats['file_count'] += 1
                    stats['total_size_bytes'] += parquet_file.stat().st_size
    
    # Check single file
    single_file = CACHE_DIR / "fund_holdings.parquet"
    if single_file.exists():
        stats['file_count'] += 1
        stats['total_size_bytes'] += single_file.stat().st_size
    
    return stats
