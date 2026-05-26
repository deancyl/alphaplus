"""
Rate limiter implementation using token bucket algorithm.
"""
import asyncio
import time
from typing import Optional


class RateLimiter:
    """
    Token bucket rate limiter for API requests.
    Limits requests to a specified rate per second.
    """
    
    def __init__(self, rate: float = 10.0, capacity: Optional[float] = None):
        """
        Initialize rate limiter.
        
        Args:
            rate: Maximum requests per second
            capacity: Maximum tokens in bucket (defaults to rate)
        """
        self.rate = rate
        self.capacity = capacity or rate
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: float = 1.0) -> bool:
        """
        Acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens were acquired, False if would block
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            
            # Refill tokens
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate
            )
            
            # Check if enough tokens available
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            # Calculate wait time
            deficit = tokens - self.tokens
            wait_time = deficit / self.rate
            
            # Wait and retry
            await asyncio.sleep(wait_time)
            self.tokens = 0
            return True
    
    async def try_acquire(self, tokens: float = 1.0) -> bool:
        """
        Try to acquire tokens without blocking.
        
        Returns:
            True if tokens were acquired, False otherwise
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate
            )
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    @property
    def available(self) -> float:
        """Current number of available tokens."""
        return self.tokens


class MultiRateLimiter:
    """
    Rate limiter with multiple buckets for different endpoints.
    """
    
    def __init__(self, default_rate: float = 10.0):
        self.limiters: dict[str, RateLimiter] = {}
        self.default_rate = default_rate
    
    def get(self, endpoint: str, rate: Optional[float] = None) -> RateLimiter:
        """Get or create rate limiter for endpoint."""
        if endpoint not in self.limiters:
            self.limiters[endpoint] = RateLimiter(rate or self.default_rate)
        return self.limiters[endpoint]
    
    async def acquire(self, endpoint: str, tokens: float = 1.0) -> bool:
        """Acquire tokens for specific endpoint."""
        return await self.get(endpoint).acquire(tokens)
