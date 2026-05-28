"""
Parquet cache for fund holdings data with Hive partitioning.

L3 Enhancement:
- Date partitioning for faster range queries
- Incremental Parquet updates (not full rewrite)
- Partition pruning for date-range queries
- Optimized compression options (zstd)
- Latency metrics for performance monitoring
"""
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import logging
import fcntl
import json
import time
import threading
from collections import deque

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "parquet"
LOCK_DIR = Path(__file__).parent.parent.parent / "data" / "locks"

PARQUET_COMPRESSION = "zstd"
PARQUET_COMPRESSION_LEVEL = 3


class ParquetLatencyMetrics:
    """Thread-safe latency metrics for Parquet operations."""
    
    def __init__(self, max_samples: int = 5000):
        self._samples = deque(maxlen=max_samples)
        self._lock = threading.Lock()
    
    def record(self, latency_ms: float) -> None:
        with self._lock:
            self._samples.append(latency_ms)
    
    def get_stats(self) -> Dict[str, float]:
        with self._lock:
            if not self._samples:
                return {"avg_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}
            
            samples = sorted(self._samples)
            count = len(samples)
            
            def percentile(p: float) -> float:
                idx = min(int(count * p / 100), count - 1)
                return samples[idx]
            
            return {
                "avg_ms": round(sum(samples) / count, 4),
                "p50_ms": round(percentile(50), 4),
                "p95_ms": round(percentile(95), 4),
                "p99_ms": round(percentile(99), 4),
            }


parquet_latency_metrics = ParquetLatencyMetrics()


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
    partition_by_quarter: bool = True,
    incremental: bool = False
) -> Path:
    """
    Export fund holdings to Parquet with Hive partitioning.
    
    Args:
        holdings: List of holding dicts
        partition_by_quarter: If True, partition by quarter_date
        incremental: If True, merge with existing data instead of full rewrite
    
    Returns:
        Path to the Parquet file/directory
    """
    ensure_directories()
    
    if not holdings:
        raise ValueError("No holdings to export")
    
    start_time = time.perf_counter()
    
    table = pa.Table.from_pylist(holdings)
    
    if partition_by_quarter:
        base_path = CACHE_DIR / "fund_holdings"
        
        if incremental and base_path.exists():
            _incremental_write(base_path, table, 'quarter_date')
        else:
            pq.write_to_dataset(
                table,
                root_path=str(base_path),
                partition_cols=['quarter_date'],
                compression=PARQUET_COMPRESSION,
                compression_level=PARQUET_COMPRESSION_LEVEL,
            )
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        parquet_latency_metrics.record(elapsed_ms)
        
        logger.info(f"Exported {len(holdings)} holdings to {base_path} ({elapsed_ms:.2f}ms)")
        return base_path
    else:
        output_path = CACHE_DIR / "fund_holdings.parquet"
        
        if incremental and output_path.exists():
            existing_table = pq.read_table(output_path)
            combined = pa.concat_tables([existing_table, table])
            pq.write_table(
                combined,
                output_path,
                compression=PARQUET_COMPRESSION,
                compression_level=PARQUET_COMPRESSION_LEVEL,
            )
        else:
            pq.write_table(
                table,
                output_path,
                compression=PARQUET_COMPRESSION,
                compression_level=PARQUET_COMPRESSION_LEVEL,
            )
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        parquet_latency_metrics.record(elapsed_ms)
        
        logger.info(f"Exported {len(holdings)} holdings to {output_path} ({elapsed_ms:.2f}ms)")
        return output_path


def _incremental_write(base_path: Path, new_table: pa.Table, partition_col: str) -> None:
    """
    Incrementally merge new data with existing partitioned Parquet.
    
    Only writes to partitions that have new data, avoiding full rewrites.
    """
    unique_partitions = new_table.column(partition_col).unique().to_pylist()
    
    for partition_value in unique_partitions:
        partition_dir = base_path / f"{partition_col}={partition_value}"
        
        new_partition_data = new_table.filter(
            pa.compute.equal(new_table.column(partition_col), partition_value)
        )
        
        if partition_dir.exists():
            existing_files = list(partition_dir.glob("*.parquet"))
            if existing_files:
                existing_table = pq.read_table(partition_dir)
                combined = pa.concat_tables([existing_table, new_partition_data])
                pq.write_to_dataset(
                    combined,
                    root_path=str(base_path),
                    partition_cols=[partition_col],
                    compression=PARQUET_COMPRESSION,
                    compression_level=PARQUET_COMPRESSION_LEVEL,
                )
            else:
                pq.write_to_dataset(
                    new_partition_data,
                    root_path=str(base_path),
                    partition_cols=[partition_col],
                    compression=PARQUET_COMPRESSION,
                    compression_level=PARQUET_COMPRESSION_LEVEL,
                )
        else:
            pq.write_to_dataset(
                new_partition_data,
                root_path=str(base_path),
                partition_cols=[partition_col],
                compression=PARQUET_COMPRESSION,
                compression_level=PARQUET_COMPRESSION_LEVEL,
            )


def load_holdings_from_parquet(
    quarter_date: Optional[date] = None,
    date_range: Optional[Tuple[date, date]] = None,
    partition_pruning: bool = True
) -> List[Dict]:
    """
    Load fund holdings from Parquet cache with partition pruning.
    
    Args:
        quarter_date: If provided, load only holdings for this quarter
        date_range: Optional (start_date, end_date) tuple for range queries
        partition_pruning: If True, use partition filters for faster reads
    
    Returns:
        List of holding dicts
    """
    start_time = time.perf_counter()
    
    base_path = CACHE_DIR / "fund_holdings"
    
    if not base_path.exists():
        single_file = CACHE_DIR / "fund_holdings.parquet"
        if single_file.exists():
            table = pq.read_table(single_file)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            parquet_latency_metrics.record(elapsed_ms)
            return table.to_pylist()
        return []
    
    filters = None
    
    if partition_pruning:
        if quarter_date:
            filters = [('quarter_date', '=', str(quarter_date))]
        elif date_range:
            start_str = str(date_range[0])
            end_str = str(date_range[1])
            filters = [
                ('quarter_date', '>=', start_str),
                ('quarter_date', '<=', end_str)
            ]
    
    table = pq.read_table(base_path, filters=filters)
    holdings = table.to_pylist()
    
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    parquet_latency_metrics.record(elapsed_ms)
    
    logger.info(f"Loaded {len(holdings)} holdings from Parquet ({elapsed_ms:.2f}ms)")
    return holdings


def load_holdings_by_fund(
    fund_code: str,
    date_range: Optional[Tuple[date, date]] = None
) -> List[Dict]:
    """
    Load holdings for a specific fund with optional date filtering.
    
    Uses partition pruning for efficient date-range queries.
    
    Args:
        fund_code: Fund code to filter by
        date_range: Optional (start_date, end_date) tuple
    
    Returns:
        List of holding dicts for the specified fund
    """
    start_time = time.perf_counter()
    
    base_path = CACHE_DIR / "fund_holdings"
    
    if not base_path.exists():
        return []
    
    filters = [('fund_code', '=', fund_code)]
    
    if date_range:
        start_str = str(date_range[0])
        end_str = str(date_range[1])
        filters.extend([
            ('quarter_date', '>=', start_str),
            ('quarter_date', '<=', end_str)
        ])
    
    table = pq.read_table(base_path, filters=filters)
    holdings = table.to_pylist()
    
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    parquet_latency_metrics.record(elapsed_ms)
    
    return holdings


def get_parquet_cache_stats() -> Dict:
    """
    Get statistics about the Parquet cache.
    
    Returns:
        Dict with cache stats (file_count, total_size_bytes, partitions, latency)
    """
    ensure_directories()
    
    stats = {
        'file_count': 0,
        'total_size_bytes': 0,
        'partitions': [],
        'latency': parquet_latency_metrics.get_stats(),
    }
    
    base_path = CACHE_DIR / "fund_holdings"
    
    if base_path.exists():
        for partition_dir in base_path.iterdir():
            if partition_dir.is_dir() and partition_dir.name.startswith('quarter_date='):
                stats['partitions'].append(partition_dir.name.replace('quarter_date=', ''))
                for parquet_file in partition_dir.glob('*.parquet'):
                    stats['file_count'] += 1
                    stats['total_size_bytes'] += parquet_file.stat().st_size
    
    single_file = CACHE_DIR / "fund_holdings.parquet"
    if single_file.exists():
        stats['file_count'] += 1
        stats['total_size_bytes'] += single_file.stat().st_size
    
    stats['total_size_mb'] = round(stats['total_size_bytes'] / 1024 / 1024, 2)
    
    return stats


def get_available_partitions() -> List[str]:
    """Get list of available quarter_date partitions."""
    base_path = CACHE_DIR / "fund_holdings"
    
    if not base_path.exists():
        return []
    
    partitions = []
    for partition_dir in base_path.iterdir():
        if partition_dir.is_dir() and partition_dir.name.startswith('quarter_date='):
            partitions.append(partition_dir.name.replace('quarter_date=', ''))
    
    return sorted(partitions)


def delete_partition(quarter_date: str) -> bool:
    """
    Delete a specific partition to free space.
    
    Args:
        quarter_date: Quarter date string to delete
    
    Returns:
        True if deleted, False if not found
    """
    base_path = CACHE_DIR / "fund_holdings"
    partition_dir = base_path / f"quarter_date={quarter_date}"
    
    if not partition_dir.exists():
        return False
    
    try:
        for parquet_file in partition_dir.glob('*.parquet'):
            parquet_file.unlink()
        partition_dir.rmdir()
        logger.info(f"Deleted partition quarter_date={quarter_date}")
        return True
    except Exception as e:
        logger.warning(f"Failed to delete partition {quarter_date}: {e}")
        return False
