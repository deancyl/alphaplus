"""
Scheduler Worker Process - Isolated Task Execution.

This module runs in a separate process from FastAPI to provide
process isolation for large ETL operations. Uses synchronous code
only (no asyncio) to avoid complexity and memory overhead.

Key features:
- Runs in separate process (isolated from FastAPI)
- SQLite state management via StateManager
- Parquet IPC via DataBridge
- Graceful SIGTERM/SIGINT handling
- Heartbeat monitoring
- No asyncio (synchronous multiprocessing)

Usage:
    # Called by ProcessManager
    python -m backend.services.scheduler_worker
    
    # Or programmatically:
    from backend.services.scheduler_worker import main
    main(worker_id="worker_001")
"""
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any, Callable

# Configure logging for worker process
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SchedulerWorker:
    """
    Isolated scheduler worker for task execution.
    
    Runs in a separate process from FastAPI main process.
    Uses synchronous code only (no asyncio) as per requirements.
    
    Communication:
    - StateManager (SQLite) - Task claiming/completion
    - DataBridge (Parquet) - Large data transfers
    - Heartbeat - Health monitoring
    """
    
    def __init__(self, worker_id: str):
        """
        Initialize worker.
        
        Args:
            worker_id: Unique worker identifier
        """
        self.worker_id = worker_id
        self._running = False
        self._stop_requested = False
        self._state_manager = None
        self._data_bridge = None
        
        # Task handlers registry
        self._task_handlers: Dict[str, Callable] = {}
        
        # Register default task handlers
        self._register_default_handlers()
        
        logger.info(f"SchedulerWorker initialized: {worker_id}")
    
    def _register_default_handlers(self):
        """Register default task handlers."""
        self._task_handlers = {
            'fund_sync': self._handle_fund_sync,
            'bond_sync': self._handle_bond_sync,
            'index_refresh': self._handle_index_refresh,
            'holdings_ingestion': self._handle_holdings_ingestion,
            'pandas_cache_refresh': self._handle_pandas_cache_refresh,
            'test_task': self._handle_test_task,
        }
    
    def register_handler(self, task_type: str, handler: Callable):
        """
        Register a custom task handler.
        
        Args:
            task_type: Task type identifier
            handler: Callable that takes (task_id, payload) and returns result path
        """
        self._task_handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type}")
    
    def run(self):
        """
        Main worker loop.
        
        Continuously:
        1. Claims pending tasks from queue
        2. Executes tasks
        3. Updates task status
        4. Sends heartbeats
        
        Gracefully handles SIGTERM/SIGINT.
        """
        # Import here to avoid circular imports
        from backend.core.state_manager import StateManager
        from backend.core.data_bridge import DataBridge
        
        self._state_manager = StateManager()
        self._data_bridge = DataBridge()
        
        assert self._state_manager is not None
        assert self._data_bridge is not None
        
        self._state_manager.register_worker(self.worker_id, os.getpid())
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        self._running = True
        logger.info(f"Worker {self.worker_id} started (PID: {os.getpid()})")
        
        last_heartbeat = time.time()
        heartbeat_interval = 15  # Send heartbeat every 15 seconds
        poll_interval = 1  # Poll for tasks every 1 second
        max_poll_interval = 10  # Backoff to 10 seconds when idle
        
        current_poll_interval = poll_interval
        consecutive_idle = 0
        
        try:
            while self._running and not self._stop_requested:
                try:
                    # Send heartbeat
                    if time.time() - last_heartbeat >= heartbeat_interval:
                        self.heartbeat()
                        last_heartbeat = time.time()
                    
                    # Claim and process task
                    task = self._state_manager.claim_task(self.worker_id)
                    
                    if task:
                        # Process the task
                        self.process_task(task.task_id, task.payload)
                        consecutive_idle = 0
                        current_poll_interval = poll_interval
                    else:
                        # No tasks available, backoff
                        consecutive_idle += 1
                        if consecutive_idle > 10:
                            current_poll_interval = min(current_poll_interval + 1, max_poll_interval)
                        
                        # Sleep with interrupt check
                        self._sleep_with_interrupt(current_poll_interval)
                    
                    # Cleanup stale tasks periodically
                    if consecutive_idle == 0 and time.time() % 300 < 1:  # Every ~5 minutes
                        self._state_manager.cleanup_stale_tasks()
                
                except Exception as e:
                    logger.error(f"Worker loop error: {e}", exc_info=True)
                    self._sleep_with_interrupt(5)  # Wait before retry
        
        finally:
            # Cleanup
            self._running = False
            self._state_manager.unregister_worker(self.worker_id)
            logger.info(f"Worker {self.worker_id} stopped")
    
    def _setup_signal_handlers(self):
        """Setup graceful shutdown signal handlers."""
        def signal_handler(signum, frame):
            logger.info(f"Worker {self.worker_id} received signal {signum}, shutting down...")
            self._stop_requested = True
            self._running = False
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Ignore SIGPIPE (can happen with broken pipes)
        if hasattr(signal, 'SIGPIPE'):
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    
    def _sleep_with_interrupt(self, seconds: float):
        """
        Sleep for specified seconds, but check for stop requests.
        
        Args:
            seconds: Seconds to sleep
        """
        end_time = time.time() + seconds
        while time.time() < end_time and not self._stop_requested:
            time.sleep(min(0.1, end_time - time.time()))
    
    def heartbeat(self):
        """Send heartbeat to state manager."""
        if self._state_manager:
            self._state_manager.update_heartbeat(self.worker_id)
    
    def process_task(self, task_id: str, payload: str) -> bool:
        """
        Process a task.
        
        Args:
            task_id: Task identifier
            payload: JSON string with task parameters
        
        Returns:
            True if task completed successfully
        """
        logger.info(f"Processing task {task_id}")
        
        # Mark as running
        self._state_manager.start_task(task_id)
        
        try:
            # Parse payload
            params = json.loads(payload) if payload else {}
            task_type = params.get('task_type', 'unknown')
            
            # Get handler
            handler = self._task_handlers.get(task_type)
            
            if not handler:
                error_msg = f"No handler for task type: {task_type}"
                logger.error(error_msg)
                self._state_manager.fail_task(task_id, error_msg)
                return False
            
            # Execute handler
            result_path = handler(task_id, params)
            
            # Complete task
            self._state_manager.complete_task(task_id, result_path)
            
            logger.info(f"Task {task_id} completed successfully")
            return True
        
        except Exception as e:
            error_msg = f"Task execution error: {e}"
            logger.error(f"Task {task_id} failed: {error_msg}", exc_info=True)
            self._state_manager.fail_task(task_id, error_msg)
            return False
    
    # ========== Task Handlers ==========
    # These run synchronously in the worker process
    
    def _handle_fund_sync(self, task_id: str, params: Dict[str, Any]) -> Optional[str]:
        """
        Handle fund data synchronization.
        
        Args:
            task_id: Task identifier
            params: Task parameters
        
        Returns:
            Path to result Parquet file, or None
        """
        logger.info(f"Executing fund sync: {params}")
        
        # Import ingestion service
        from backend.services.ingestion import fund_ingestion
        
        # Run sync (synchronous)
        try:
            # Note: fund_ingestion.sync_all_funds() is async, but we're in sync context
            # We need to run it in a new event loop
            import asyncio
            
            # Create new event loop for this task
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(fund_ingestion.sync_all_funds())
            finally:
                loop.close()
            
            # Write result to Parquet for IPC
            result_data = [{
                'task_id': task_id,
                'status': 'completed',
                'timestamp': datetime.utcnow().isoformat()
            }]
            
            result_path = self._data_bridge.write_parquet(
                result_data,
                task_id=task_id,
                chunk_name='result'
            )
            
            return str(result_path)
        
        except Exception as e:
            logger.error(f"Fund sync error: {e}", exc_info=True)
            raise
    
    def _handle_bond_sync(self, task_id: str, params: Dict[str, Any]) -> Optional[str]:
        """
        Handle bond yield synchronization.
        
        Args:
            task_id: Task identifier
            params: Task parameters
        
        Returns:
            Path to result Parquet file, or None
        """
        logger.info(f"Executing bond sync: {params}")
        
        from backend.services.ingestion import bond_ingestion
        
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(bond_ingestion.sync_bond_yields())
            finally:
                loop.close()
            
            result_data = [{
                'task_id': task_id,
                'status': 'completed',
                'timestamp': datetime.utcnow().isoformat()
            }]
            
            result_path = self._data_bridge.write_parquet(
                result_data,
                task_id=task_id,
                chunk_name='result'
            )
            
            return str(result_path)
        
        except Exception as e:
            logger.error(f"Bond sync error: {e}", exc_info=True)
            raise
    
    def _handle_index_refresh(self, task_id: str, params: Dict[str, Any]) -> Optional[str]:
        """
        Handle index quotes refresh.
        
        Args:
            task_id: Task identifier
            params: Task parameters
        
        Returns:
            Path to result Parquet file, or None
        """
        logger.info(f"Executing index refresh: {params}")
        
        from backend.services.quotes import index_quotes
        
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(index_quotes.refresh())
            finally:
                loop.close()
            
            result_data = [{
                'task_id': task_id,
                'status': 'completed',
                'timestamp': datetime.utcnow().isoformat()
            }]
            
            result_path = self._data_bridge.write_parquet(
                result_data,
                task_id=task_id,
                chunk_name='result'
            )
            
            return str(result_path)
        
        except Exception as e:
            logger.error(f"Index refresh error: {e}", exc_info=True)
            raise
    
    def _handle_holdings_ingestion(self, task_id: str, params: Dict[str, Any]) -> Optional[str]:
        """
        Handle quarterly holdings ingestion.
        
        Args:
            task_id: Task identifier
            params: Task parameters
        
        Returns:
            Path to result Parquet file, or None
        """
        logger.info(f"Executing holdings ingestion: {params}")
        
        from backend.services.parquet_cache import PhysicalLock, load_holdings_from_parquet
        from backend.services.duckdb_ingestion import insert_holdings_batch
        from datetime import date
        
        try:
            with PhysicalLock("holdings_ingestion"):
                today = date.today()
                cached = load_holdings_from_parquet(today)
                
                if cached:
                    insert_holdings_batch(cached)
                    
                    result_data = [{
                        'task_id': task_id,
                        'status': 'completed',
                        'records_count': len(cached),
                        'timestamp': datetime.utcnow().isoformat()
                    }]
                else:
                    result_data = [{
                        'task_id': task_id,
                        'status': 'completed',
                        'records_count': 0,
                        'message': 'No cached Parquet data available',
                        'timestamp': datetime.utcnow().isoformat()
                    }]
                
                result_path = self._data_bridge.write_parquet(
                    result_data,
                    task_id=task_id,
                    chunk_name='result'
                )
                
                return str(result_path)
        
        except RuntimeError as e:
            # Another process is running
            logger.warning(f"Holdings ingestion skipped: {e}")
            raise
        except Exception as e:
            logger.error(f"Holdings ingestion error: {e}", exc_info=True)
            raise
    
    def _handle_pandas_cache_refresh(self, task_id: str, params: Dict[str, Any]) -> Optional[str]:
        """
        Handle Pandas cache refresh.
        
        Args:
            task_id: Task identifier
            params: Task parameters
        
        Returns:
            Path to result Parquet file, or None
        """
        logger.info(f"Executing Pandas cache refresh: {params}")
        
        from backend.services.pandas_cache import GLOBAL_FUND_DF
        
        try:
            stats = GLOBAL_FUND_DF.refresh_cache()
            
            result_data = [{
                'task_id': task_id,
                'status': 'completed',
                'stats': json.dumps(stats) if stats else '{}',
                'timestamp': datetime.utcnow().isoformat()
            }]
            
            result_path = self._data_bridge.write_parquet(
                result_data,
                task_id=task_id,
                chunk_name='result'
            )
            
            return str(result_path)
        
        except Exception as e:
            logger.error(f"Pandas cache refresh error: {e}", exc_info=True)
            raise
    
    def _handle_test_task(self, task_id: str, params: Dict[str, Any]) -> Optional[str]:
        """
        Handle test task (for testing).
        
        Args:
            task_id: Task identifier
            params: Task parameters
        
        Returns:
            Path to result Parquet file
        """
        logger.info(f"Executing test task: {params}")
        
        # Simulate work
        time.sleep(params.get('delay', 1))
        
        result_data = [{
            'task_id': task_id,
            'status': 'completed',
            'message': params.get('message', 'Test task completed'),
            'timestamp': datetime.utcnow().isoformat()
        }]
        
        result_path = self._data_bridge.write_parquet(
            result_data,
            task_id=task_id,
            chunk_name='result'
        )
        
        return str(result_path)


def main(worker_id: Optional[str] = None):
    """
    Main entry point for worker process.
    
    Args:
        worker_id: Optional worker identifier (auto-generated if None)
    """
    import uuid
    
    actual_worker_id = worker_id or f"worker_{uuid.uuid4().hex[:8]}"
    
    logger.info(f"Starting scheduler worker process: {actual_worker_id}")
    
    worker = SchedulerWorker(actual_worker_id)
    worker.run()


if __name__ == "__main__":
    worker_id = sys.argv[1] if len(sys.argv) > 1 else None
    main(worker_id)