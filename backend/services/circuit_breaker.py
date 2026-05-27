"""
Circuit Breaker pattern implementation for fault tolerance.

Prevents cascading failures by temporarily blocking calls to a failing service.
States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing recovery).
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failing, requests are blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitStats:
    """Statistics for circuit breaker monitoring."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None
    last_failure_message: Optional[str] = None


@dataclass
class Result(Generic[T]):
    """Result wrapper for circuit breaker calls."""
    success: bool
    value: Optional[T] = None
    error: Optional[Exception] = None
    source: Optional[str] = None

    @classmethod
    def ok(cls, value: T, source: Optional[str] = None) -> "Result[T]":
        """Create a successful result."""
        return cls(success=True, value=value, source=source)

    @classmethod
    def err(cls, error: Exception, source: Optional[str] = None) -> "Result[T]":
        """Create a failed result."""
        return cls(success=False, error=error, source=source)


class AsyncCircuitBreaker:
    """
    Async circuit breaker with automatic state transitions.

    State machine:
    - CLOSED: Normal operation. Tracks consecutive failures.
      Opens when failures >= failure_threshold.
    - OPEN: Blocks all calls. After recovery_timeout, transitions to HALF_OPEN.
    - HALF_OPEN: Allows one test call. If success -> CLOSED, if failure -> OPEN.

    Example:
        cb = AsyncCircuitBreaker(failure_threshold=3, recovery_timeout=60)
        result = await cb.call(fetch_data)
        if result.success:
            data = result.value
        else:
            print(f"Circuit open or error: {result.error}")
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit breaker name for logging
            failure_threshold: Number of consecutive failures before opening
            recovery_timeout: Seconds to wait before attempting recovery
            half_open_max_calls: Max calls allowed in half-open state
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._lock = asyncio.Lock()
        self._half_open_calls = 0
        self._opened_at: Optional[float] = None

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state

    @property
    def stats(self) -> CircuitStats:
        """Circuit breaker statistics."""
        return self._stats

    def is_open(self) -> bool:
        """Check if circuit is open (blocking calls)."""
        return self._state == CircuitState.OPEN

    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    def is_half_open(self) -> bool:
        """Check if circuit is in half-open state (testing recovery)."""
        return self._state == CircuitState.HALF_OPEN

    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> Result[T]:
        """
        Execute a function through the circuit breaker.

        Args:
            func: Async function to call
            *args, **kwargs: Arguments to pass to the function

        Returns:
            Result with success status and value or error
        """
        async with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    self._transition_to_half_open()
                else:
                    # Still in cooldown
                    logger.debug(
                        f"[{self.name}] Circuit is OPEN, rejecting call",
                        extra={
                            "circuit_name": self.name,
                            "time_remaining": self._time_until_recovery(),
                        }
                    )
                    return Result.err(
                        CircuitBreakerOpenError(
                            f"Circuit '{self.name}' is open. "
                            f"Retry in {self._time_until_recovery():.1f}s"
                        ),
                        source=self.name
                    )

            # Check half-open capacity
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    return Result.err(
                        CircuitBreakerOpenError(
                            f"Circuit '{self.name}' is half-open with pending test"
                        ),
                        source=self.name
                    )
                self._half_open_calls += 1

        # Execute the function outside the lock
        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return Result.ok(result, source=self.name)

        except Exception as e:
            await self._record_failure(e)
            return Result.err(e, source=self.name)

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._opened_at is None:
            return False
        return (time.monotonic() - self._opened_at) >= self.recovery_timeout

    def _time_until_recovery(self) -> float:
        """Time remaining until recovery attempt."""
        if self._opened_at is None:
            return 0.0
        elapsed = time.monotonic() - self._opened_at
        return max(0.0, self.recovery_timeout - elapsed)

    async def _record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            self._stats.total_calls += 1
            self._stats.successful_calls += 1
            self._stats.consecutive_failures = 0

            if self._state == CircuitState.HALF_OPEN:
                logger.info(
                    f"[{self.name}] Test call succeeded, closing circuit",
                    extra={"circuit_name": self.name}
                )
                self._transition_to_closed()

    async def _record_failure(self, error: Exception) -> None:
        """Record a failed call."""
        async with self._lock:
            self._stats.total_calls += 1
            self._stats.failed_calls += 1
            self._stats.consecutive_failures += 1
            self._stats.last_failure_time = time.monotonic()
            self._stats.last_failure_message = str(error)

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    f"[{self.name}] Test call failed in half-open, reopening circuit",
                    extra={"circuit_name": self.name, "error": str(error)}
                )
                self._transition_to_open()

            elif self._stats.consecutive_failures >= self.failure_threshold:
                logger.error(
                    f"[{self.name}] Failure threshold ({self.failure_threshold}) reached, "
                    f"opening circuit",
                    extra={
                        "circuit_name": self.name,
                        "consecutive_failures": self._stats.consecutive_failures,
                        "error": str(error),
                    }
                )
                self._transition_to_open()

    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        self._half_open_calls = 0

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._half_open_calls = 0

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        logger.info(
            f"[{self.name}] Entering half-open state for recovery test",
            extra={"circuit_name": self.name}
        )

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._half_open_calls = 0
        self._stats = CircuitStats()
        logger.info(f"[{self.name}] Circuit manually reset to CLOSED")

    def force_open(self) -> None:
        """Manually force circuit to open state."""
        self._transition_to_open()
        logger.warning(f"[{self.name}] Circuit manually forced OPEN")

    def get_status(self) -> dict:
        """Get detailed circuit breaker status."""
        return {
            "name": self.name,
            "state": self._state.value,
            "is_open": self.is_open(),
            "stats": {
                "total_calls": self._stats.total_calls,
                "successful_calls": self._stats.successful_calls,
                "failed_calls": self._stats.failed_calls,
                "consecutive_failures": self._stats.consecutive_failures,
                "last_failure_time": self._stats.last_failure_time,
                "last_failure_message": self._stats.last_failure_message,
            },
            "config": {
                "failure_threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
            },
            "time_until_recovery": self._time_until_recovery() if self.is_open() else None,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejecting calls."""
    pass
