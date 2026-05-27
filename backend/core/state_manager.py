"""
State Manager for Scheduler Worker Process Isolation.

SQLite-based state management for task claiming, completion tracking,
and worker health monitoring. Enables safe coordination between
FastAPI main process and isolated scheduler worker process.

Key features:
- Atomic task claiming with SQLite transactions
- Worker heartbeat monitoring
- Task state persistence across process restarts
- No asyncio - synchronous code for worker process
"""
import sqlite3
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# State database path (separate from main DB to avoid contention)
STATE_DB_PATH = Path(__file__).parent.parent.parent / "data" / "scheduler_state.db"


@dataclass
class Task:
    """Task representation for scheduler worker."""
    task_id: str
    task_type: str
    payload: str  # JSON string
    status: str  # pending, claimed, running, completed, failed
    worker_id: Optional[str]
    created_at: datetime
    claimed_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    result_path: Optional[str]  # Path to Parquet result file


class StateManager:
    """
    SQLite-based state management for scheduler worker isolation.
    
    Uses a separate database from the main application to avoid
    write contention and OOM issues during large ETL operations.
    
    All methods are synchronous - no asyncio in worker process.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize state manager.
        
        Args:
            db_path: Optional custom database path (for testing)
        """
        self.db_path = db_path or STATE_DB_PATH
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Worker registration and heartbeats
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduler_workers (
                    worker_id TEXT PRIMARY KEY,
                    pid INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    last_heartbeat TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    tasks_completed INTEGER DEFAULT 0,
                    tasks_failed INTEGER DEFAULT 0
                )
            """)
            
            # Task queue with claiming
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduler_tasks (
                    task_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    priority INTEGER DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    worker_id TEXT,
                    created_at TEXT NOT NULL,
                    claimed_at TEXT,
                    completed_at TEXT,
                    error_message TEXT,
                    result_path TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3
                )
            """)
            
            # Indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status_priority
                ON scheduler_tasks(status, priority DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_type_status
                ON scheduler_tasks(task_type, status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_workers_heartbeat
                ON scheduler_workers(last_heartbeat)
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """
        Get database connection with WAL mode and timeout.
        
        Yields connection with proper cleanup.
        """
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=10.0,  # 10s busy timeout
            isolation_level='IMMEDIATE'  # Immediate locking for consistency
        )
        
        # Enable WAL for concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=10000")  # 10s
        
        try:
            yield conn
        finally:
            conn.close()
    
    def register_worker(self, worker_id: str, pid: int) -> bool:
        """
        Register a new worker in the database.
        
        Args:
            worker_id: Unique worker identifier
            pid: Process ID of the worker
        
        Returns:
            True if registered successfully
        """
        now = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Remove any existing registration for this worker_id
            cursor.execute(
                "DELETE FROM scheduler_workers WHERE worker_id = ?",
                (worker_id,)
            )
            
            # Insert new registration
            cursor.execute("""
                INSERT INTO scheduler_workers
                (worker_id, pid, started_at, last_heartbeat, status)
                VALUES (?, ?, ?, ?, 'running')
            """, (worker_id, pid, now, now))
            
            conn.commit()
        
        logger.info(f"Registered worker {worker_id} (PID: {pid})")
        return True
    
    def unregister_worker(self, worker_id: str) -> bool:
        """
        Unregister a worker (on graceful shutdown).
        
        Args:
            worker_id: Worker identifier to unregister
        
        Returns:
            True if unregistered successfully
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scheduler_workers
                SET status = 'stopped'
                WHERE worker_id = ?
            """, (worker_id,))
            conn.commit()
        
        logger.info(f"Unregistered worker {worker_id}")
        return True
    
    def update_heartbeat(self, worker_id: str) -> bool:
        """
        Update worker heartbeat timestamp.
        
        Should be called periodically (every 10-30s) by the worker.
        
        Args:
            worker_id: Worker identifier
        
        Returns:
            True if heartbeat updated successfully
        """
        now = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scheduler_workers
                SET last_heartbeat = ?
                WHERE worker_id = ?
            """, (now, worker_id))
            conn.commit()
        
        return True
    
    def get_heartbeat(self, worker_id: str) -> Optional[datetime]:
        """
        Get the last heartbeat timestamp for a worker.
        
        Args:
            worker_id: Worker identifier
        
        Returns:
            Last heartbeat datetime, or None if worker not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT last_heartbeat FROM scheduler_workers
                WHERE worker_id = ?
            """, (worker_id,))
            row = cursor.fetchone()
            
            if row:
                return datetime.fromisoformat(row[0])
            return None
    
    def get_worker_status(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full worker status.
        
        Args:
            worker_id: Worker identifier
        
        Returns:
            Dict with worker status, or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT worker_id, pid, started_at, last_heartbeat, status,
                       tasks_completed, tasks_failed
                FROM scheduler_workers
                WHERE worker_id = ?
            """, (worker_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'worker_id': row[0],
                    'pid': row[1],
                    'started_at': datetime.fromisoformat(row[2]),
                    'last_heartbeat': datetime.fromisoformat(row[3]),
                    'status': row[4],
                    'tasks_completed': row[5],
                    'tasks_failed': row[6],
                }
            return None
    
    def create_task(
        self,
        task_id: str,
        task_type: str,
        payload: str,
        priority: int = 0,
        max_retries: int = 3
    ) -> bool:
        """
        Create a new task in the queue.
        
        Args:
            task_id: Unique task identifier
            task_type: Type of task (e.g., 'fund_sync', 'bond_sync')
            payload: JSON string with task parameters
            priority: Higher priority = claimed first (default: 0)
            max_retries: Maximum retry attempts (default: 3)
        
        Returns:
            True if task created successfully
        """
        now = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO scheduler_tasks
                    (task_id, task_type, payload, priority, created_at, max_retries)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (task_id, task_type, payload, priority, now, max_retries))
                conn.commit()
                logger.info(f"Created task {task_id} (type={task_type}, priority={priority})")
                return True
            except sqlite3.IntegrityError:
                logger.warning(f"Task {task_id} already exists")
                return False
    
    def claim_task(self, worker_id: str, task_type: Optional[str] = None) -> Optional[Task]:
        """
        Claim a pending task atomically.
        
        Finds the highest-priority pending task and claims it for the worker.
        Uses IMMEDIATE transaction to prevent race conditions.
        
        Args:
            worker_id: Worker claiming the task
            task_type: Optional filter by task type
        
        Returns:
            Task if claimed, None if no pending tasks
        """
        now = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Find highest-priority pending task
            if task_type:
                cursor.execute("""
                    SELECT task_id, task_type, payload, status, worker_id,
                           created_at, claimed_at, completed_at, error_message,
                           result_path, retry_count, max_retries
                    FROM scheduler_tasks
                    WHERE status = 'pending' AND task_type = ?
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                """, (task_type,))
            else:
                cursor.execute("""
                    SELECT task_id, task_type, payload, status, worker_id,
                           created_at, claimed_at, completed_at, error_message,
                           result_path, retry_count, max_retries
                    FROM scheduler_tasks
                    WHERE status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                """)
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            task_id = row[0]
            
            # Claim the task
            cursor.execute("""
                UPDATE scheduler_tasks
                SET status = 'claimed', worker_id = ?, claimed_at = ?
                WHERE task_id = ? AND status = 'pending'
            """, (worker_id, now, task_id))
            
            if cursor.rowcount == 0:
                # Task was claimed by another worker
                return None
            
            conn.commit()
            
            task = Task(
                task_id=row[0],
                task_type=row[1],
                payload=row[2],
                status='claimed',
                worker_id=worker_id,
                created_at=datetime.fromisoformat(row[5]),
                claimed_at=datetime.fromisoformat(now),
                completed_at=None,
                error_message=None,
                result_path=None
            )
            
            logger.info(f"Worker {worker_id} claimed task {task_id} (type={task.task_type})")
            return task
    
    def start_task(self, task_id: str) -> bool:
        """
        Mark a claimed task as running.
        
        Args:
            task_id: Task identifier
        
        Returns:
            True if task started successfully
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scheduler_tasks
                SET status = 'running'
                WHERE task_id = ? AND status = 'claimed'
            """, (task_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def complete_task(self, task_id: str, result_path: Optional[str] = None) -> bool:
        """
        Mark a task as completed.
        
        Args:
            task_id: Task identifier
            result_path: Optional path to result Parquet file
        
        Returns:
            True if task completed successfully
        """
        now = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Update task status
            cursor.execute("""
                UPDATE scheduler_tasks
                SET status = 'completed', completed_at = ?, result_path = ?
                WHERE task_id = ?
            """, (now, result_path, task_id))
            
            # Update worker stats
            cursor.execute("""
                UPDATE scheduler_workers
                SET tasks_completed = tasks_completed + 1
                WHERE worker_id = (
                    SELECT worker_id FROM scheduler_tasks WHERE task_id = ?
                )
            """, (task_id,))
            
            conn.commit()
        
        logger.info(f"Completed task {task_id}")
        return True
    
    def fail_task(self, task_id: str, error_message: str) -> bool:
        """
        Mark a task as failed.
        
        If retry_count < max_retries, the task is reset to pending for retry.
        Otherwise, it's marked as permanently failed.
        
        Args:
            task_id: Task identifier
            error_message: Error description
        
        Returns:
            True if task failed successfully
        """
        now = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get retry info
            cursor.execute("""
                SELECT retry_count, max_retries FROM scheduler_tasks
                WHERE task_id = ?
            """, (task_id,))
            row = cursor.fetchone()
            
            if not row:
                return False
            
            retry_count, max_retries = row
            
            # Update worker stats
            cursor.execute("""
                UPDATE scheduler_workers
                SET tasks_failed = tasks_failed + 1
                WHERE worker_id = (
                    SELECT worker_id FROM scheduler_tasks WHERE task_id = ?
                )
            """, (task_id,))
            
            if retry_count < max_retries:
                # Reset for retry
                cursor.execute("""
                    UPDATE scheduler_tasks
                    SET status = 'pending', worker_id = NULL, claimed_at = NULL,
                        retry_count = retry_count + 1, error_message = ?
                    WHERE task_id = ?
                """, (error_message, task_id))
                logger.warning(f"Task {task_id} failed (retry {retry_count + 1}/{max_retries}): {error_message}")
            else:
                # Permanent failure
                cursor.execute("""
                    UPDATE scheduler_tasks
                    SET status = 'failed', completed_at = ?, error_message = ?
                    WHERE task_id = ?
                """, (now, error_message, task_id))
                logger.error(f"Task {task_id} permanently failed: {error_message}")
            
            conn.commit()
        
        return True
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get task by ID.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Task if found, None otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT task_id, task_type, payload, status, worker_id,
                       created_at, claimed_at, completed_at, error_message,
                       result_path
                FROM scheduler_tasks
                WHERE task_id = ?
            """, (task_id,))
            row = cursor.fetchone()
            
            if row:
                return Task(
                    task_id=row[0],
                    task_type=row[1],
                    payload=row[2],
                    status=row[3],
                    worker_id=row[4],
                    created_at=datetime.fromisoformat(row[5]),
                    claimed_at=datetime.fromisoformat(row[6]) if row[6] else None,
                    completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
                    error_message=row[8],
                    result_path=row[9]
                )
            return None
    
    def get_pending_tasks(self, limit: int = 100) -> List[Task]:
        """
        Get all pending tasks.
        
        Args:
            limit: Maximum number of tasks to return
        
        Returns:
            List of pending tasks
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT task_id, task_type, payload, status, worker_id,
                       created_at, claimed_at, completed_at, error_message,
                       result_path
                FROM scheduler_tasks
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            
            return [
                Task(
                    task_id=row[0],
                    task_type=row[1],
                    payload=row[2],
                    status=row[3],
                    worker_id=row[4],
                    created_at=datetime.fromisoformat(row[5]),
                    claimed_at=datetime.fromisoformat(row[6]) if row[6] else None,
                    completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
                    error_message=row[8],
                    result_path=row[9]
                )
                for row in rows
            ]
    
    def cleanup_stale_tasks(self, timeout_seconds: int = 3600) -> int:
        """
        Reset tasks that have been claimed but not completed.
        
        This handles cases where a worker crashes while processing a task.
        
        Args:
            timeout_seconds: Seconds before considering a task stale
        
        Returns:
            Number of tasks reset
        """
        cutoff = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Reset stale claimed/running tasks to pending
            cursor.execute("""
                UPDATE scheduler_tasks
                SET status = 'pending', worker_id = NULL, claimed_at = NULL
                WHERE status IN ('claimed', 'running')
                  AND claimed_at < datetime(?, '-' || ? || ' seconds')
                  AND retry_count < max_retries
            """, (cutoff, timeout_seconds))
            
            count = cursor.rowcount
            conn.commit()
        
        if count > 0:
            logger.warning(f"Reset {count} stale tasks to pending")
        
        return count
    
    def cleanup_old_tasks(self, days: int = 7) -> int:
        """
        Remove completed/failed tasks older than specified days.
        
        Args:
            days: Days to keep completed tasks
        
        Returns:
            Number of tasks removed
        """
        cutoff = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM scheduler_tasks
                WHERE status IN ('completed', 'failed')
                  AND completed_at < datetime(?, '-' || ? || ' days')
            """, (cutoff, days))
            
            count = cursor.rowcount
            conn.commit()
        
        if count > 0:
            logger.info(f"Cleaned up {count} old tasks")
        
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get scheduler statistics.
        
        Returns:
            Dict with task counts and worker status
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Task counts by status
            cursor.execute("""
                SELECT status, COUNT(*)
                FROM scheduler_tasks
                GROUP BY status
            """)
            task_counts = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Worker status
            cursor.execute("""
                SELECT worker_id, pid, status, tasks_completed, tasks_failed,
                       last_heartbeat
                FROM scheduler_workers
                WHERE status = 'running'
            """)
            workers = []
            for row in cursor.fetchall():
                workers.append({
                    'worker_id': row[0],
                    'pid': row[1],
                    'status': row[2],
                    'tasks_completed': row[3],
                    'tasks_failed': row[4],
                    'last_heartbeat': datetime.fromisoformat(row[5])
                })
            
            return {
                'tasks': task_counts,
                'workers': workers
            }


# Global state manager instance (singleton pattern)
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """
    Get the global state manager instance.
    
    Creates a new instance if not already created.
    Thread-safe for SQLite connections.
    """
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager