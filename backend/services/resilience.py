"""
Resilience module with retry logic and exponential backoff.
Implements V0.2 开发圣经 requirements: T_w = 2^n + jitter, n∈[1,5]
"""
import asyncio
import functools
import logging
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, Awaitable

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ErrorType(Enum):
    """Classification of error types for retry decisions."""
    NETWORK_ERROR = "network_error"      # Retry with normal backoff
    RATE_LIMITED = "rate_limited"        # Retry with longer delay
    DATA_ERROR = "data_error"            # Skip retry, log and return None
    AUTH_ERROR = "auth_error"            # Stop retry, raise immediately
    UNKNOWN = "unknown"                  # Retry with normal backoff


@dataclass
class RetryConfig:
    """
    Configuration for retry with exponential backoff.
    
    Default values follow V0.2 开发圣经: max_retries=5, exponential_base=2.0
    Formula: delay = base_delay * (exponential_base ** n) + jitter
    """
    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number.
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Returns:
            Delay in seconds with exponential backoff and jitter
        """
        # Exponential backoff: base_delay * (exponential_base ** n)
        delay = self.base_delay * (self.exponential_base ** attempt)
        
        # Cap at max_delay
        delay = min(delay, self.max_delay)
        
        # Add jitter: random.uniform(0, 1)
        if self.jitter:
            delay += random.uniform(0, 1)
        
        return delay


def classify_error(error: Exception) -> ErrorType:
    """
    Classify an exception to determine retry strategy.
    
    Args:
        error: Exception to classify
    
    Returns:
        ErrorType enum indicating how to handle the error
    """
    error_str = str(error).lower()
    error_type_name = type(error).__name__.lower()
    
    # Network errors - retry
    network_indicators = [
        'timeout', 'connection', 'network', 'socket', 'refused',
        'reset', 'broken', 'unreachable', 'errno', 'gaierror'
    ]
    if any(indicator in error_str or indicator in error_type_name for indicator in network_indicators):
        return ErrorType.NETWORK_ERROR
    
    # Rate limiting - retry with longer delay
    rate_limit_indicators = ['rate', 'limit', 'too many', '429', 'throttl']
    if any(indicator in error_str for indicator in rate_limit_indicators):
        return ErrorType.RATE_LIMITED
    
    # Authentication errors - stop immediately
    auth_indicators = ['auth', 'unauthorized', 'forbidden', '401', '403', 'api key', 'token']
    if any(indicator in error_str for indicator in auth_indicators):
        return ErrorType.AUTH_ERROR
    
    # Data errors - skip retry
    data_indicators = ['no data', 'empty', 'invalid', 'not found', '404', 'null', 'missing']
    if any(indicator in error_str for indicator in data_indicators):
        return ErrorType.DATA_ERROR
    
    return ErrorType.UNKNOWN


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: Optional[tuple] = None
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Async decorator for automatic retry with exponential backoff.
    
    Args:
        config: RetryConfig instance (uses defaults if None)
        retryable_exceptions: Tuple of exception types to retry (all if None)
    
    Returns:
        Decorator function
    
    Example:
        @retry_with_backoff(RetryConfig(max_retries=3))
        async def fetch_data():
            return await some_api_call()
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception: Optional[Exception] = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                
                except Exception as e:
                    last_exception = e
                    
                    # Check if exception type is retryable
                    if retryable_exceptions and not isinstance(e, retryable_exceptions):
                        logger.debug(
                            f"[{func.__name__}] Non-retryable exception: {type(e).__name__}",
                            extra={"function": func.__name__, "error_type": type(e).__name__}
                        )
                        raise
                    
                    # Classify error
                    error_type = classify_error(e)
                    
                    # Log retry attempt
                    logger.warning(
                        f"[{func.__name__}] Attempt {attempt + 1}/{config.max_retries + 1} failed: {e}",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_retries": config.max_retries + 1,
                            "error_type": error_type.value,
                            "error_message": str(e)
                        }
                    )
                    
                    # Handle based on error type
                    if error_type == ErrorType.AUTH_ERROR:
                        logger.error(
                            f"[{func.__name__}] Authentication error, stopping retry",
                            extra={"function": func.__name__, "error": str(e)}
                        )
                        raise
                    
                    if error_type == ErrorType.DATA_ERROR:
                        logger.info(
                            f"[{func.__name__}] Data error, skipping retry",
                            extra={"function": func.__name__, "error": str(e)}
                        )
                        raise
                    
                    # Check if max retries reached
                    if attempt >= config.max_retries:
                        logger.error(
                            f"[{func.__name__}] Max retries ({config.max_retries}) exceeded",
                            extra={"function": func.__name__, "attempts": attempt + 1}
                        )
                        raise
                    
                    # Calculate delay
                    delay = config.calculate_delay(attempt)
                    
                    # Double delay for rate-limited errors
                    if error_type == ErrorType.RATE_LIMITED:
                        delay *= 2
                        logger.info(
                            f"[{func.__name__}] Rate limited, using extended delay: {delay:.2f}s",
                            extra={"function": func.__name__, "delay": delay}
                        )
                    
                    logger.info(
                        f"[{func.__name__}] Retrying in {delay:.2f}s (attempt {attempt + 2}/{config.max_retries + 1})",
                        extra={
                            "function": func.__name__,
                            "delay": delay,
                            "next_attempt": attempt + 2
                        }
                    )
                    
                    await asyncio.sleep(delay)
            
            # Should never reach here, but raise last exception if we do
            if last_exception:
                raise last_exception
            raise RuntimeError(f"[{func.__name__}] Unexpected state in retry logic")
        
        return wrapper
    return decorator
