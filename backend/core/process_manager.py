"""
Process Manager for Scheduler Worker.

Manages the lifecycle of the isolated scheduler worker process,
including startup, shutdown, health monitoring, and auto-restart.

This runs in the FastAPI main process and communicates with the
worker process through:
1. StateManager (SQLite) - Task claiming/completion
2. DataBridge (Parquet) - Large data transfers
3. Process signals - SIGTERM/SIGINT handling
"""
import logging
import multiprocessing as mp
import os
import signal
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from backend.core.state_manager import StateManager, get_state_manager
from backend.core.data_bridge import DataBridge, get_data_bridge

logger = logging.getLogger(__name__)


class ProcessManager:
    """
    Manages the isolated scheduler worker process lifecycle.
    
    Responsibilities:
    - Start/stop worker process
    - Health monitoring via heartbeats
    - Auto-restart on failure
    - Task scheduling interface
    
    Runs in the FastAPI main process.
    """
    
    def __init__(
        self,
        worker_id: Optional[str] = None,
        heartbeat_timeout: int = 120,
        restart_delay: int = 5,
        max_restart_attempts: int = 3
    ):
        """
        Initialize process manager.
        
        Args:
            worker_id: Optional worker identifier (auto-generated if None)
            heartbeat_timeout: Seconds before considering worker dead (default: 120)
            restart_delay: Seconds to wait before restart (default: 5)
            max_restart_attempts: Maximum restart attempts within window (default: 3)
        """
        self.worker_id = worker_id or f"worker_{uuid.uuid4().hex[:8]}"
        self.heartbeat_timeout = heartbeat_timeout
        self.restart_delay = restart_delay
        self.max_restart_attempts = max_restart_attempts
        
        self._process: Optional[mp.Process] = None
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._restart_count = 0
        self._restart_window_start: Optional[datetime] = None
        self._state_manager: Optional[StateManager] = None
        
        logger.info(f"ProcessManager initialized with worker_id={self.worker_id}")
    
    def start_worker(self, target: Optional[Callable] = None) -> bool:
        """
        Start the worker process.
        
        Args:
            target: Optional target function (default: scheduler_worker.main)
        
        Returns:
            True if started successfully
        """
        if self._process and self._process.is_alive():
            logger.warning(f"Worker {self.worker_id} already running")
            return False
        
        # Import here to avoid circular import
        if target is None:
            from backend.services.scheduler_worker import main as worker_main
            target = worker_main
        
        self._stop_event.clear()
        
        # Create and start process
        self._process = mp.Process(
            target=target,
            args=(self.worker_id,),
            name=f"scheduler-worker-{self.worker_id}",
            daemon=False  # Allow graceful shutdown
        )
        
        self._process.start()
        
        pid = self._process.pid
        if pid is None:
            logger.error(f"Failed to get PID for worker {self.worker_id}")
            return False
        
        self._state_manager = get_state_manager()
        self._state_manager.register_worker(self.worker_id, pid)
        
        # Start health monitor thread
        self._monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            name=f"health-monitor-{self.worker_id}",
            daemon=True
        )
        self._monitor_thread.start()
        
        logger.info(f"Started worker {self.worker_id} (PID: {self._process.pid})")
        return True
    
    def stop_worker(self, timeout: int = 30) -> bool:
        """
        Stop the worker process gracefully.
        
        Args:
            timeout: Seconds to wait for graceful shutdown
        
        Returns:
            True if stopped successfully
        """
        if not self._process or not self._process.is_alive():
            logger.warning(f"Worker {self.worker_id} not running")
            return True
        
        logger.info(f"Stopping worker {self.worker_id}")
        
        self._stop_event.set()
        
        if self._process and self._process.pid:
            try:
                os.kill(self._process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        
        self._process.join(timeout=timeout)
        
        if self._process.is_alive():
            logger.warning(f"Worker {self.worker_id} not responding, sending SIGKILL")
            if self._process.pid:
                try:
                    os.kill(self._process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self._process.join(timeout=5)
        
        # Unregister worker
        if self._state_manager:
            self._state_manager.unregister_worker(self.worker_id)
        
        logger.info(f"Stopped worker {self.worker_id}")
        return True
    
    def restart_worker(self) -> bool:
        """
        Restart the worker process.
        
        Returns:
            True if restarted successfully
        """
        logger.info(f"Restarting worker {self.worker_id}")
        
        self.stop_worker()
        
        # Check restart rate limit
        now = datetime.utcnow()
        if self._restart_window_start:
            window_elapsed = (now - self._restart_window_start).total_seconds()
            if window_elapsed < 300:  # 5 minute window
                self._restart_count += 1
                if self._restart_count > self.max_restart_attempts:
                    logger.error(
                        f"Worker {self.worker_id} exceeded max restart attempts "
                        f"({self._restart_count}/{self.max_restart_attempts})"
                    )
                    return False
            else:
                # Reset window
                self._restart_count = 1
                self._restart_window_start = now
        else:
            self._restart_count = 1
            self._restart_window_start = now
        
        # Wait before restart
        time.sleep(self.restart_delay)
        
        return self.start_worker()
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check worker health status.
        
        Returns:
            Dict with health status information
        """
        status = {
            'worker_id': self.worker_id,
            'process_alive': False,
            'process_pid': None,
            'heartbeat_ok': False,
            'last_heartbeat': None,
            'heartbeat_age_seconds': None,
            'restart_count': self._restart_count,
        }
        
        # Check process status
        if self._process:
            status['process_alive'] = self._process.is_alive()
            status['process_pid'] = self._process.pid
        
        # Check heartbeat
        if self._state_manager:
            last_heartbeat = self._state_manager.get_heartbeat(self.worker_id)
            status['last_heartbeat'] = last_heartbeat.isoformat() if last_heartbeat else None
            
            if last_heartbeat:
                age = (datetime.utcnow() - last_heartbeat).total_seconds()
                status['heartbeat_age_seconds'] = age
                status['heartbeat_ok'] = age < self.heartbeat_timeout
        
        status['healthy'] = (
            status['process_alive'] and
            status['heartbeat_ok']
        )
        
        return status
    
    def is_running(self) -> bool:
        """
        Check if worker process is running.
        
        Returns:
            True if worker is running
        """
        return self._process is not None and self._process.is_alive()
    
    def _health_monitor_loop(self):
        """
        Background thread for health monitoring and auto-restart.
        
        Runs in the FastAPI main process.
        """
        logger.info(f"Health monitor started for worker {self.worker_id}")
        
        while not self._stop_event.is_set():
            try:
                # Check health every 30 seconds
                if self._stop_event.wait(timeout=30):
                    break
                
                health = self.health_check()
                
                # Auto-restart if unhealthy
                if not health['healthy'] and not self._stop_event.is_set():
                    if health['process_alive'] and not health['heartbeat_ok']:
                        # Process running but no heartbeat - might be stuck
                        logger.warning(
                            f"Worker {self.worker_id} heartbeat timeout "
                            f"(age={health['heartbeat_age_seconds']:.0f}s)"
                        )
                        self.restart_worker()
                    elif not health['process_alive']:
                        # Process died
                        logger.warning(f"Worker {self.worker_id} process died")
                        self.restart_worker()
                
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
        
        logger.info(f"Health monitor stopped for worker {self.worker_id}")
    
    def schedule_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
        priority: int = 0
    ) -> str:
        """
        Schedule a task for the worker.
        
        Args:
            task_type: Type of task (e.g., 'fund_sync', 'bond_sync')
            payload: Task parameters
            task_id: Optional task ID (auto-generated if None)
            priority: Task priority (higher = claimed first)
        
        Returns:
            Task ID
        """
        import json
        
        if not self._state_manager:
            self._state_manager = get_state_manager()
        
        task_id = task_id or f"{task_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        payload_str = json.dumps(payload, ensure_ascii=False)
        
        self._state_manager.create_task(
            task_id=task_id,
            task_type=task_type,
            payload=payload_str,
            priority=priority
        )
        
        logger.info(f"Scheduled task {task_id} (type={task_type}, priority={priority})")
        return task_id
    
    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get result of a completed task.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Task result dict with status and data path, or None if not found
        """
        if not self._state_manager:
            self._state_manager = get_state_manager()
        
        task = self._state_manager.get_task(task_id)
        
        if not task:
            return None
        
        result = {
            'task_id': task.task_id,
            'task_type': task.task_type,
            'status': task.status,
            'created_at': task.created_at.isoformat(),
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'error_message': task.error_message,
            'result_path': task.result_path,
        }
        
        # If completed with result, get manifest
        if task.status == 'completed' and task.result_path:
            data_bridge = get_data_bridge()
            result['manifest'] = data_bridge.get_manifest(task.task_id)
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics.
        
        Returns:
            Dict with process and task statistics
        """
        health = self.health_check()
        
        if self._state_manager:
            state_stats = self._state_manager.get_stats()
        else:
            state_stats = {}
        
        data_bridge = get_data_bridge()
        ipc_stats = data_bridge.get_ipc_stats()
        
        return {
            'worker': health,
            'tasks': state_stats.get('tasks', {}),
            'ipc': ipc_stats,
        }


# Global process manager instance
_process_manager: Optional[ProcessManager] = None


def get_process_manager() -> ProcessManager:
    """
    Get the global process manager instance.
    
    Creates a new instance if not already created.
    """
    global _process_manager
    if _process_manager is None:
        _process_manager = ProcessManager()
    return _process_manager


def start_scheduler_worker() -> bool:
    """
    Convenience function to start the scheduler worker.
    
    Returns:
        True if started successfully
    """
    manager = get_process_manager()
    return manager.start_worker()


def stop_scheduler_worker() -> bool:
    """
    Convenience function to stop the scheduler worker.
    
    Returns:
        True if stopped successfully
    """
    manager = get_process_manager()
    return manager.stop_worker()