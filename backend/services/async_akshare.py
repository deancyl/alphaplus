"""
AsyncAkShareWrapper - Non-blocking wrapper for AkShare calls.

Provides dedicated ThreadPoolExecutor with timeout protection for all AkShare functions,
ensuring the FastAPI event loop is never blocked by synchronous I/O operations.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)


class AsyncAkShareError(Exception):
    """Raised when AkShare async operation fails."""
    pass


class AsyncAkShareTimeoutError(AsyncAkShareError):
    """Raised when AkShare operation times out."""
    pass


class AsyncAkShareWrapper:
    """
    Async wrapper for AkShare with dedicated ThreadPoolExecutor.
    
    All AkShare synchronous calls are executed in a thread pool to prevent
    blocking the FastAPI event loop. Each call has timeout protection.
    
    Attributes:
        _executor: Dedicated ThreadPoolExecutor for AkShare calls
        _timeout: Default timeout in seconds for all operations
    """
    
    def __init__(self, max_workers: int = 4, timeout: float = 30.0):
        """
        Initialize the AsyncAkShareWrapper.
        
        Args:
            max_workers: Number of worker threads (default: 4)
            timeout: Default timeout in seconds (default: 30.0)
        """
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="akshare_")
        self._timeout = timeout
    
    async def _run_sync(self, func, *args, **kwargs) -> pd.DataFrame:
        """
        Execute a synchronous AkShare function in thread pool with timeout.
        
        Args:
            func: Synchronous AkShare function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            pd.DataFrame: Result from AkShare function
            
        Raises:
            AsyncAkShareTimeoutError: If operation times out
            AsyncAkShareError: If operation fails for other reasons
        """
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(func, *args, **kwargs),
                timeout=self._timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"AkShare call {func.__name__} timed out after {self._timeout}s")
            raise AsyncAkShareTimeoutError(
                f"Operation {func.__name__} timed out after {self._timeout}s"
            )
        except Exception as e:
            logger.error(f"AkShare call {func.__name__} failed: {e}")
            raise AsyncAkShareError(f"Failed to call {func.__name__}: {e}") from e
    
    async def get_bond_china_yield(self) -> pd.DataFrame:
        """
        Fetch Chinese bond yield data.
        
        Returns:
            pd.DataFrame: Bond yield data with columns for different maturities
            
        Raises:
            AsyncAkShareError: If fetch fails
        """
        logger.info("Fetching bond_china_yield data")
        return await self._run_sync(ak.bond_china_yield)
    
    async def get_rate_interbank(self) -> pd.DataFrame:
        """
        Fetch interbank market interest rates.
        
        Returns:
            pd.DataFrame: Interbank rate data (SHIBOR, LPR, etc.)
            
        Raises:
            AsyncAkShareError: If fetch fails
        """
        logger.info("Fetching rate_interbank data")
        return await self._run_sync(ak.rate_interbank)
    
    async def get_spot_hist_sge(self, symbol: str) -> pd.DataFrame:
        """
        Fetch Shanghai Gold Exchange historical spot prices.
        
        Args:
            symbol: Gold contract symbol (e.g., "Au99.99", "Au100g")
            
        Returns:
            pd.DataFrame: Historical gold price data with date, open, high, low, close, volume
            
        Raises:
            AsyncAkShareError: If fetch fails
        """
        logger.info(f"Fetching spot_hist_sge data for symbol: {symbol}")
        return await self._run_sync(ak.spot_hist_sge, symbol=symbol)
    
    async def get_stock_spot(self) -> pd.DataFrame:
        """
        Fetch A-share real-time market data.
        
        Returns:
            pd.DataFrame: Real-time stock quotes for all A-share stocks
            
        Raises:
            AsyncAkShareError: If fetch fails
        """
        logger.info("Fetching stock_zh_a_spot_em data")
        return await self._run_sync(ak.stock_zh_a_spot_em)
    
    async def get_fund_list(self) -> pd.DataFrame:
        """
        Fetch all public fund names and codes.
        
        Returns:
            pd.DataFrame: Fund list with columns: 基金代码, 基金简称, 基金类型, etc.
            
        Raises:
            AsyncAkShareError: If fetch fails
        """
        logger.info("Fetching fund_name_em data")
        return await self._run_sync(ak.fund_name_em)
    
    async def close(self) -> None:
        """
        Shutdown the thread pool executor.
        
        Should be called during application shutdown to clean up resources.
        """
        logger.info("Shutting down AsyncAkShareWrapper executor")
        self._executor.shutdown(wait=True)
    
    def __del__(self):
        """Ensure executor is cleaned up on object destruction."""
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass


# Singleton instance for application-wide use
async_akshare = AsyncAkShareWrapper()