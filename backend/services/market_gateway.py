"""
Market Data Gateway with multi-source failover.

Provides unified interface for fetching market data from multiple sources
with automatic failover, circuit breaker protection, and parallel fetching.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar

from backend.services.circuit_breaker import (
    AsyncCircuitBreaker,
    CircuitState,
    Result,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class SourceConfig:
    """Configuration for a data source."""
    name: str
    adapter: Any  # Source adapter instance
    priority: int  # Lower number = higher priority
    circuit_breaker: AsyncCircuitBreaker
    enabled: bool = True


@dataclass
class FetchResult(Generic[T]):
    """Result from gateway fetch operation."""
    success: bool
    value: Optional[T] = None
    error: Optional[Exception] = None
    source: Optional[str] = None
    fallback_chain: list[str] = field(default_factory=list)  # Sources tried

    @classmethod
    def ok(cls, value: T, source: str, fallback_chain: list[str] = None) -> "FetchResult[T]":
        return cls(success=True, value=value, source=source, fallback_chain=fallback_chain or [])

    @classmethod
    def err(cls, error: Exception, fallback_chain: list[str] = None) -> "FetchResult[T]":
        return cls(success=False, error=error, fallback_chain=fallback_chain or [])


class MarketDataGateway:
    """
    Multi-source market data gateway with automatic failover.

    Features:
    - Register multiple data sources with priority ordering
    - Circuit breaker protection for each source
    - Automatic failover to next source on failure
    - Parallel fetching for multiple endpoints
    - Source health monitoring

    Example:
        gateway = MarketDataGateway()
        gateway.register_source("akshare", AkshareSource(), priority=1)
        gateway.register_source("eastmoney", EastmoneySource(), priority=2)

        # Fetch with automatic failover
        result = await gateway.fetch("index_quotes", {})
        if result.success:
            data = result.value
            print(f"Data from {result.source}")

        # Parallel fetch multiple endpoints
        results = await gateway.fetch_parallel(["index_quotes", "futures_quotes"])
    """

    def __init__(
        self,
        default_failure_threshold: int = 3,
        default_recovery_timeout: float = 60.0,
    ):
        """
        Initialize the gateway.

        Args:
            default_failure_threshold: Default circuit breaker failure threshold
            default_recovery_timeout: Default circuit breaker recovery timeout (seconds)
        """
        self._sources: dict[str, SourceConfig] = {}
        self._default_failure_threshold = default_failure_threshold
        self._default_recovery_timeout = default_recovery_timeout
        self._lock = asyncio.Lock()

    def register_source(
        self,
        name: str,
        adapter: Any,
        priority: int = 1,
        failure_threshold: Optional[int] = None,
        recovery_timeout: Optional[float] = None,
    ) -> None:
        """
        Register a data source with the gateway.

        Args:
            name: Unique source name
            adapter: Source adapter instance (must have fetch() method)
            priority: Source priority (lower = higher priority, tried first)
            failure_threshold: Circuit breaker failure threshold (optional)
            recovery_timeout: Circuit breaker recovery timeout (optional)
        """
        circuit_breaker = AsyncCircuitBreaker(
            name=f"{name}_breaker",
            failure_threshold=failure_threshold or self._default_failure_threshold,
            recovery_timeout=recovery_timeout or self._default_recovery_timeout,
        )

        self._sources[name] = SourceConfig(
            name=name,
            adapter=adapter,
            priority=priority,
            circuit_breaker=circuit_breaker,
            enabled=True,
        )

        logger.info(
            f"Registered source '{name}' with priority {priority}",
            extra={"source": name, "priority": priority}
        )

    def unregister_source(self, name: str) -> bool:
        """Remove a source from the gateway."""
        if name in self._sources:
            del self._sources[name]
            logger.info(f"Unregistered source '{name}'")
            return True
        return False

    def enable_source(self, name: str) -> bool:
        """Enable a disabled source."""
        if name in self._sources:
            self._sources[name].enabled = True
            return True
        return False

    def disable_source(self, name: str) -> bool:
        """Disable a source (won't be used in failover)."""
        if name in self._sources:
            self._sources[name].enabled = False
            logger.warning(f"Disabled source '{name}'")
            return True
        return False

    def get_source_status(self, name: str) -> Optional[dict]:
        """Get status for a specific source."""
        if name not in self._sources:
            return None

        source = self._sources[name]
        return {
            "name": name,
            "priority": source.priority,
            "enabled": source.enabled,
            "circuit_state": source.circuit_breaker.state.value,
            "circuit_status": source.circuit_breaker.get_status(),
        }

    def get_all_sources_status(self) -> list[dict]:
        """Get status for all registered sources."""
        return [self.get_source_status(name) for name in self._sources.keys()]

    def _get_ordered_sources(self) -> list[SourceConfig]:
        """Get sources sorted by priority (ascending), excluding disabled and open circuits."""
        sources = []

        for source in self._sources.values():
            # Skip disabled sources
            if not source.enabled:
                continue

            # Skip sources with open circuit (unless we're checking for available ones)
            # Note: Half-open sources are included to allow recovery testing
            if source.circuit_breaker.is_open():
                logger.debug(
                    f"Skipping source '{source.name}' due to open circuit",
                    extra={"source": source.name}
                )
                continue

            sources.append(source)

        # Sort by priority (lower number = higher priority)
        sources.sort(key=lambda s: s.priority)

        return sources
    
    def _make_cache_key(self, endpoint: str, params: Optional[dict] = None) -> str:
        """
        Create a cache key from endpoint and params.
        
        Args:
            endpoint: Data endpoint
            params: Request parameters
        
        Returns:
            Cache key string
        """
        if params:
            import json
            params_str = json.dumps(params, sort_keys=True)
            return f"gateway:{endpoint}:{hash(params_str)}"
        return f"gateway:{endpoint}"

    async def fetch(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        preferred_source: Optional[str] = None,
        use_cache: bool = True,
        cache_ttl: Optional[int] = None,
    ) -> FetchResult:
        """
        Fetch data with automatic failover across sources.

        Attempts sources in priority order (or specified preferred source first),
        skipping sources with open circuits. Each source is protected by its
        circuit breaker.

        Args:
            endpoint: Data endpoint to fetch
            params: Parameters for the fetch
            preferred_source: Try this source first (optional)
            use_cache: Whether to use tiered cache (default: True)
            cache_ttl: Cache TTL in seconds (optional, uses default if None)

        Returns:
            FetchResult with success status, data/error, and source name
        """
        params = params or {}
        
        # Try cache first if enabled
        if use_cache:
            cache_key = self._make_cache_key(endpoint, params)
            cached_value = tiered_cache.get(cache_key)
            if cached_value is not None:
                logger.debug(
                    f"Cache hit for '{endpoint}'",
                    extra={"endpoint": endpoint, "cache_key": cache_key}
                )
                return FetchResult.ok(
                    cached_value,
                    source="cache",
                    fallback_chain=["cache"]
                )
        
        fallback_chain = []

        # Build source order
        sources = self._get_ordered_sources()

        # Insert preferred source at the beginning if specified and available
        if preferred_source and preferred_source in self._sources:
            preferred = self._sources[preferred_source]
            if preferred.enabled and not preferred.circuit_breaker.is_open():
                # Remove from list and insert at beginning
                sources = [s for s in sources if s.name != preferred_source]
                sources.insert(0, preferred)

        if not sources:
            logger.error("No available sources for fetching")
            return FetchResult.err(
                Exception("No available data sources (all disabled or circuits open)"),
                fallback_chain=fallback_chain
            )

        logger.info(
            f"Fetching '{endpoint}' with {len(sources)} available sources",
            extra={
                "endpoint": endpoint,
                "sources": [s.name for s in sources],
                "preferred": preferred_source
            }
        )

        # Try each source in order
        for source in sources:
            fallback_chain.append(source.name)

            # Check if source supports this endpoint
            if hasattr(source.adapter, "supports") and not source.adapter.supports(endpoint):
                logger.debug(
                    f"Source '{source.name}' doesn't support endpoint '{endpoint}'",
                    extra={"source": source.name, "endpoint": endpoint}
                )
                continue

            # Execute through circuit breaker
            try:
                async def _fetch():
                    return await source.adapter.fetch(endpoint, params)

                result: Result = await source.circuit_breaker.call(_fetch)

                if result.success:
                    logger.info(
                        f"Successfully fetched '{endpoint}' from '{source.name}'",
                        extra={"endpoint": endpoint, "source": source.name}
                    )
                    
                    # Cache the result if caching is enabled
                    if use_cache:
                        cache_key = self._make_cache_key(endpoint, params)
                        tiered_cache.set(cache_key, result.value, ttl=cache_ttl)
                    
                    return FetchResult.ok(
                        result.value,
                        source=source.name,
                        fallback_chain=fallback_chain
                    )

                # Circuit breaker rejected or function failed
                logger.warning(
                    f"Source '{source.name}' failed for '{endpoint}': {result.error}",
                    extra={
                        "endpoint": endpoint,
                        "source": source.name,
                        "error": str(result.error)
                    }
                )
                # Continue to next source

            except Exception as e:
                logger.warning(
                    f"Unexpected error from source '{source.name}': {e}",
                    extra={"endpoint": endpoint, "source": source.name, "error": str(e)}
                )
                # Continue to next source

        # All sources failed
        logger.error(
            f"All sources failed for endpoint '{endpoint}'",
            extra={"endpoint": endpoint, "fallback_chain": fallback_chain}
        )
        return FetchResult.err(
            Exception(f"All data sources failed for endpoint '{endpoint}'"),
            fallback_chain=fallback_chain
        )

    async def fetch_parallel(
        self,
        endpoints: list[str],
        params: Optional[dict] = None,
    ) -> list[FetchResult]:
        """
        Fetch multiple endpoints in parallel using asyncio.gather.

        Each endpoint is fetched independently with its own failover chain.

        Args:
            endpoints: List of endpoints to fetch
            params: Shared parameters for all endpoints (optional)

        Returns:
            List of FetchResult for each endpoint (in same order as input)
        """
        tasks = [
            self.fetch(endpoint, params)
            for endpoint in endpoints
        ]

        results = await asyncio.gather(*tasks)
        return list(results)

    async def fetch_from_source(
        self,
        source_name: str,
        endpoint: str,
        params: Optional[dict] = None,
    ) -> FetchResult:
        """
        Fetch data from a specific source only (no failover).

        Useful for comparing data from different sources or testing.

        Args:
            source_name: Specific source to use
            endpoint: Data endpoint to fetch
            params: Parameters for the fetch

        Returns:
            FetchResult with success status and data/error
        """
        if source_name not in self._sources:
            return FetchResult.err(Exception(f"Source '{source_name}' not registered"))

        source = self._sources[source_name]

        if not source.enabled:
            return FetchResult.err(Exception(f"Source '{source_name}' is disabled"))

        try:
            async def _fetch():
                return await source.adapter.fetch(endpoint, params)

            result: Result = await source.circuit_breaker.call(_fetch)

            if result.success:
                return FetchResult.ok(result.value, source=source_name)
            else:
                return FetchResult.err(result.error, fallback_chain=[source_name])

        except Exception as e:
            return FetchResult.err(e, fallback_chain=[source_name])

    def reset_circuit(self, source_name: str) -> bool:
        """Manually reset circuit breaker for a source."""
        if source_name in self._sources:
            self._sources[source_name].circuit_breaker.reset()
            return True
        return False

    def reset_all_circuits(self) -> None:
        """Reset all circuit breakers."""
        for source in self._sources.values():
            source.circuit_breaker.reset()
        logger.info("Reset all circuit breakers")


# Singleton gateway instance for application-wide use
market_gateway = MarketDataGateway()


def init_gateway() -> None:
    """
    Initialize the default gateway with standard sources.

    Called during application startup.
    """
    from backend.services.sources.akshare_source import AkshareSource
    from backend.services.sources.eastmoney_source import EastmoneySource
    from backend.services.sources.sina_source import SinaSource

    # Register sources with priority ordering
    market_gateway.register_source(
        "akshare",
        AkshareSource(),
        priority=1,  # Primary source
        failure_threshold=3,
        recovery_timeout=60.0,
    )

    market_gateway.register_source(
        "eastmoney",
        EastmoneySource(),
        priority=2,  # Secondary source (API-based, faster)
        failure_threshold=5,
        recovery_timeout=30.0,
    )

    market_gateway.register_source(
        "sina",
        SinaSource(),
        priority=3,  # Tertiary source (lightweight)
        failure_threshold=5,
        recovery_timeout=30.0,
    )

    logger.info("Market data gateway initialized with 3 sources")