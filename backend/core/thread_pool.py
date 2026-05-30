"""Thread pool management for CPU-intensive operations.

Provides centralized thread pool management for FastAPI application.
Uses dedicated pool instead of default executor for better control.
"""

from concurrent.futures import ThreadPoolExecutor
import asyncio
from typing import Callable, Any, Optional


class ThreadPoolManager:
    """Singleton manager for application-wide thread pool.
    
    Provides centralized thread pool for CPU-intensive operations
    that should not block the async event loop.
    """
    
    _instance: Optional["ThreadPoolManager"] = None
    _executor: Optional[ThreadPoolExecutor] = None
    
    def __new__(cls):
        """Ensure singleton pattern for thread pool manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self, max_workers: int = 4) -> None:
        """Initialize the thread pool with specified worker count.
        
        Args:
            max_workers: Maximum number of worker threads (default: 4)
        """
        if self._executor is not None:
            self._executor.shutdown(wait=False)
        
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="alphaplus_worker"
        )
    
    def get_executor(self) -> ThreadPoolExecutor:
        """Get the thread pool executor instance.
        
        Returns:
            ThreadPoolExecutor: The managed thread pool executor
            
        Raises:
            RuntimeError: If executor not initialized
        """
        if self._executor is None:
            raise RuntimeError("ThreadPoolManager not initialized. Call initialize() first.")
        return self._executor
    
    async def run_in_thread(
        self, 
        func: Callable[..., Any], 
        *args: Any, 
        timeout: float = 10.0  # Reduced from 30s to prevent long blocking
    ) -> Any:
        """Run a synchronous function in the thread pool.
        
        Args:
            func: Synchronous function to execute
            *args: Arguments to pass to the function
            timeout: Maximum execution time in seconds (default: 10.0)
            
        Returns:
            Result of the function execution
            
        Raises:
            asyncio.TimeoutError: If execution exceeds timeout
        """
        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(self._executor, func, *args),
            timeout=timeout
        )
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the thread pool.
        
        Args:
            wait: Whether to wait for pending tasks to complete
        """
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None


# Global singleton instance
thread_pool_manager = ThreadPoolManager()
