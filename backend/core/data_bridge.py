"""
Data Bridge for Inter-Process Communication (IPC).

Handles Parquet-based data exchange between FastAPI main process
and isolated scheduler worker process. Provides zero-copy data
transfer for large ETL operations.

Key features:
- Parquet serialization for efficient large data transfers
- Manifest tracking for task results
- Atomic write operations with temporary files
- Compression support (snappy)
"""
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

# IPC data directory
IPC_DIR = Path(__file__).parent.parent.parent / "data" / "ipc"
MANIFEST_DIR = IPC_DIR / "manifests"


def ensure_directories():
    """Ensure IPC directories exist."""
    IPC_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)


class DataBridge:
    """
    Parquet-based IPC bridge for worker-to-main process communication.
    
    Uses Parquet files for efficient serialization of large datasets,
    avoiding memory pressure in the main process during ETL operations.
    
    All methods are synchronous - no asyncio in worker process.
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize data bridge.
        
        Args:
            base_dir: Optional custom base directory (for testing)
        """
        self.base_dir = base_dir or IPC_DIR
        self.manifest_dir = self.base_dir / "manifests"
        ensure_directories()
    
    def write_parquet(
        self,
        data: Union[List[Dict[str, Any]], pa.Table],
        task_id: str,
        chunk_name: Optional[str] = None,
        compression: str = "snappy",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Write data to Parquet file for IPC.
        
        Uses atomic write pattern: write to temp file, then rename.
        
        Args:
            data: Data to write (list of dicts, PyArrow Table, or pandas DataFrame)
            task_id: Task identifier for directory organization
            chunk_name: Optional chunk name for multi-chunk results
            compression: Compression algorithm (default: snappy)
            metadata: Optional metadata to embed in Parquet schema
        
        Returns:
            Path to written Parquet file
        
        Raises:
            ValueError: If data is empty or invalid type
        """
        # Create task directory
        task_dir = self.base_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate file name
        chunk_name = chunk_name or f"chunk_{uuid.uuid4().hex[:8]}"
        filename = f"{chunk_name}.parquet"
        output_path = task_dir / filename
        temp_path = task_dir / f".{filename}.tmp"
        
        # Convert data to PyArrow Table
        if isinstance(data, pa.Table):
            table = data
        elif hasattr(data, 'to_arrow'):  # pandas DataFrame with pyarrow
            table = pa.Table.from_pandas(data)
        elif isinstance(data, list):
            if not data:
                raise ValueError("Cannot write empty data list")
            table = pa.Table.from_pylist(data)
        else:
            # Try pandas conversion
            try:
                import pandas as pd
                if isinstance(data, pd.DataFrame):
                    table = pa.Table.from_pandas(data)
                else:
                    raise ValueError(f"Unsupported data type: {type(data)}")
            except ImportError:
                raise ValueError(f"Unsupported data type: {type(data)}")
        
        assert isinstance(table, pa.Table), f"Expected pa.Table, got {type(table)}"
        
        pyarrow_table: pa.Table = table
        
        custom_metadata = {
            'task_id': task_id,
            'chunk_name': chunk_name,
            'created_at': datetime.utcnow().isoformat(),
            'row_count': str(len(pyarrow_table)),
            'compression': compression,
        }
        
        if metadata:
            custom_metadata.update({k: str(v) for k, v in metadata.items()})
        
        existing_metadata = pyarrow_table.schema.metadata or {}
        merged_metadata = {**existing_metadata, **{k.encode(): v.encode() for k, v in custom_metadata.items()}}
        pyarrow_table = pyarrow_table.replace_schema_metadata(merged_metadata)
        
        pq.write_table(pyarrow_table, temp_path, compression=compression)
        
        # Atomic rename
        temp_path.rename(output_path)
        
        logger.info(f"Wrote {len(table)} rows to {output_path}")
        
        return output_path
    
    def read_parquet(self, path: Union[str, Path]) -> "pa.Table":
        """
        Read data from Parquet file.
        
        Args:
            path: Path to Parquet file (can be task_id or full path)
        
        Returns:
            PyArrow Table with the data
        
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        path = Path(path)
        
        # If not an absolute path, treat as task_id
        if not path.is_absolute():
            # Try to find the file in task directory
            task_dir = self.base_dir / path
            if task_dir.exists() and task_dir.is_dir():
                # Find first parquet file in directory
                parquet_files = list(task_dir.glob("*.parquet"))
                if parquet_files:
                    path = parquet_files[0]
                else:
                    raise FileNotFoundError(f"No parquet files in {task_dir}")
            else:
                # Treat as direct path
                path = self.base_dir / path
        
        if not path.exists():
            raise FileNotFoundError(f"Parquet file not found: {path}")
        
        table = pq.read_table(path)
        
        logger.info(f"Read {len(table)} rows from {path}")
        
        return table
    
    def read_parquet_as_dicts(self, path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Read data from Parquet file as list of dicts.
        
        Args:
            path: Path to Parquet file (can be task_id or full path)
        
        Returns:
            List of dictionaries with the data
        """
        table = self.read_parquet(path)
        return table.to_pylist()
    
    def get_manifest(self, task_id: str) -> Dict[str, Any]:
        """
        Get manifest for a task's IPC data.
        
        Manifest includes:
        - List of all Parquet files
        - Total row count
        - Schema information
        - Metadata
        
        Args:
            task_id: Task identifier
        
        Returns:
            Manifest dictionary
        """
        task_dir = self.base_dir / task_id
        
        if not task_dir.exists():
            return {
                'task_id': task_id,
                'exists': False,
                'files': [],
                'total_rows': 0,
            }
        
        files = []
        total_rows = 0
        schema = None
        
        for parquet_file in sorted(task_dir.glob("*.parquet")):
            # Read file metadata
            try:
                metadata = pq.read_metadata(parquet_file)
                file_info = {
                    'name': parquet_file.name,
                    'size_bytes': parquet_file.stat().st_size,
                    'row_count': metadata.num_rows,
                    'num_columns': metadata.num_columns,
                    'created_at': datetime.fromtimestamp(
                        parquet_file.stat().st_mtime
                    ).isoformat(),
                }
                files.append(file_info)
                total_rows += metadata.num_rows
                
                # Get schema from first file
                if schema is None:
                    table = pq.read_table(parquet_file)
                    schema = table.schema
            except Exception as e:
                logger.warning(f"Error reading {parquet_file}: {e}")
        
        manifest = {
            'task_id': task_id,
            'exists': True,
            'files': files,
            'total_rows': total_rows,
            'file_count': len(files),
            'schema': str(schema) if schema else None,
            'task_dir': str(task_dir),
        }
        
        return manifest
    
    def write_manifest(self, task_id: str, manifest: Dict[str, Any]) -> Path:
        """
        Write manifest file for a task.
        
        Args:
            task_id: Task identifier
            manifest: Manifest dictionary
        
        Returns:
            Path to manifest file
        """
        manifest_path = self.manifest_dir / f"{task_id}.json"
        temp_path = self.manifest_dir / f".{task_id}.json.tmp"
        
        # Add timestamp
        manifest['manifest_created_at'] = datetime.utcnow().isoformat()
        
        # Atomic write
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        temp_path.rename(manifest_path)
        
        return manifest_path
    
    def delete_task_data(self, task_id: str) -> int:
        """
        Delete all IPC data for a task.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Number of files deleted
        """
        task_dir = self.base_dir / task_id
        deleted_count = 0
        
        if task_dir.exists():
            for file in task_dir.glob("*"):
                try:
                    file.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Error deleting {file}: {e}")
            
            try:
                task_dir.rmdir()
            except Exception:
                pass
        
        # Also delete manifest
        manifest_path = self.manifest_dir / f"{task_id}.json"
        if manifest_path.exists():
            try:
                manifest_path.unlink()
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Error deleting manifest: {e}")
        
        logger.info(f"Deleted {deleted_count} files for task {task_id}")
        return deleted_count
    
    def list_task_data(self) -> List[str]:
        """
        List all task IDs with IPC data.
        
        Returns:
            List of task IDs
        """
        task_ids = []
        
        if self.base_dir.exists():
            for item in self.base_dir.iterdir():
                if item.is_dir() and item.name != "manifests":
                    # Check if it has parquet files
                    if list(item.glob("*.parquet")):
                        task_ids.append(item.name)
        
        return sorted(task_ids)
    
    def get_ipc_stats(self) -> Dict[str, Any]:
        """
        Get statistics about IPC data storage.
        
        Returns:
            Dict with storage stats
        """
        stats = {
            'task_count': 0,
            'total_files': 0,
            'total_size_bytes': 0,
            'tasks': [],
        }
        
        if not self.base_dir.exists():
            return stats
        
        for task_dir in self.base_dir.iterdir():
            if not task_dir.is_dir() or task_dir.name == "manifests":
                continue
            
            task_files = list(task_dir.glob("*.parquet"))
            if not task_files:
                continue
            
            task_size = sum(f.stat().st_size for f in task_files)
            
            stats['task_count'] += 1
            stats['total_files'] += len(task_files)
            stats['total_size_bytes'] += task_size
            
            stats['tasks'].append({
                'task_id': task_dir.name,
                'file_count': len(task_files),
                'size_bytes': task_size,
            })
        
        return stats
    
    def cleanup_old_data(self, days: int = 7) -> int:
        """
        Delete IPC data older than specified days.
        
        Args:
            days: Days to keep data
        
        Returns:
            Number of tasks cleaned up
        """
        from datetime import timedelta
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        cleaned = 0
        
        for task_id in self.list_task_data():
            manifest = self.get_manifest(task_id)
            
            if not manifest.get('files'):
                continue
            
            # Check age of oldest file
            created_times = []
            for f in manifest['files']:
                if 'created_at' in f:
                    try:
                        created_times.append(
                            datetime.fromisoformat(f['created_at'])
                        )
                    except Exception:
                        pass
            
            if created_times:
                oldest = min(created_times)
                if oldest < cutoff:
                    self.delete_task_data(task_id)
                    cleaned += 1
        
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old IPC tasks")
        
        return cleaned


# Global data bridge instance
_data_bridge: Optional[DataBridge] = None


def get_data_bridge() -> DataBridge:
    """
    Get the global data bridge instance.
    
    Creates a new instance if not already created.
    """
    global _data_bridge
    if _data_bridge is None:
        _data_bridge = DataBridge()
    return _data_bridge