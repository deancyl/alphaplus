"""
AData Direct Mode client - bypassing AkShare parsing layer.

Direct broker API client for faster real-time market data fetching.
Features:
- Request batching (max 50 symbols per request)
- Request deduplication (same symbol within 100ms returns cached)
- Request coalescing (batch same query type)
- Parallel batch fetching with asyncio.gather
"""
import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cached response entry."""
    data: Any
    timestamp: float
    query_type: str


@dataclass
class PendingRequest:
    """Pending coalesced request."""
    symbols: List[str] = field(default_factory=list)
    futures: List[asyncio.Future] = field(default_factory=list)
    query_type: str = ""
    scheduled_time: float = 0.0


class ADataClient:
    """
    Direct broker API client bypassing AkShare parsing.
    
    Optimizations:
    1. Request batching: Max 50 symbols per HTTP request
    2. Request deduplication: Same symbol within 100ms returns cached
    3. Request coalescing: Batch same query type together
    4. Parallel batches: asyncio.gather for concurrent fetching
    
    Supported endpoints:
    - realtime_quotes: Real-time stock quotes
    - index_quotes: Major index quotes
    - fund_nav: Fund NAV data
    """

    # Broker API endpoints (Eastmoney Push2 direct API)
    QUOTE_API = "https://push2.eastmoney.com/api/qt/ulist.np"
    INDEX_API = "https://push2.eastmoney.com/api/qt/ulist.np"
    FUND_API = "https://fundgz.1234567.com.cn/js/{code}.js"
    
    # Maximum symbols per batch request
    MAX_BATCH_SIZE = 50
    
    # Deduplication cache TTL (milliseconds)
    CACHE_TTL_MS = 100
    
    # Coalescing window (milliseconds)
    COALESCE_WINDOW_MS = 50
    
    # Index codes mapping (market.code format for Eastmoney API)
    INDEX_CODES = {
        "000001": "1.000001",   # 上证指数 (SH market = 1)
        "399001": "0.399001",   # 深证成指 (SZ market = 0)
        "000300": "1.000300",   # 沪深300
        "000905": "1.000905",   # 中证500
        "000852": "1.000852",   # 中证1000
        "399006": "0.399006",   # 创业板指
        "000688": "1.000688",   # 科创50
    }

    INDEX_NAMES = {
        "000001": "上证指数",
        "399001": "深证成指",
        "000300": "沪深300",
        "000905": "中证500",
        "000852": "中证1000",
        "399006": "创业板指",
        "000688": "科创50",
    }

    def __init__(
        self,
        timeout: float = 10.0,
        max_batch_size: int = 50,
        cache_ttl_ms: int = 100,
        coalesce_window_ms: int = 50,
    ):
        self.name = "adata"
        self._timeout = timeout
        self._max_batch_size = max_batch_size
        self._cache_ttl_ms = cache_ttl_ms
        self._coalesce_window_ms = coalesce_window_ms
        
        # Deduplication cache
        self._cache: Dict[str, CacheEntry] = {}
        
        # Request coalescing state
        self._pending_requests: Dict[str, PendingRequest] = {}
        self._coalesce_task: Optional[asyncio.Task] = None
        
        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None
        
        self._supported_endpoints = [
            "realtime_quotes",
            "index_quotes",
            "fund_nav",
            "stock_quotes",
        ]

    def get_supported_endpoints(self) -> List[str]:
        return self._supported_endpoints

    def supports(self, endpoint: str) -> bool:
        return endpoint in self._supported_endpoints

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # ==================== Public API Methods ====================

    async def get_realtime_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Fetch real-time quotes for multiple stock symbols.
        
        Args:
            symbols: List of stock codes (e.g., ["600000", "000001"])
            
        Returns:
            Dict mapping symbol to quote data:
            {
                "600000": {
                    "name": "浦发银行",
                    "price": 10.50,
                    "change": 0.20,
                    "change_pct": 1.91,
                    "volume": 12345678,
                    "amount": 129876543.21,
                },
                ...
            }
        """
        if not symbols:
            return {}
        
        # Deduplication check
        cache_key = f"quotes:{','.join(sorted(symbols))}"
        cached = self._get_cached(cache_key, "realtime_quotes")
        if cached:
            return cached
        
        # Batch symbols into groups of max_batch_size
        batches = self._batch_symbols(symbols)
        
        # Fetch all batches in parallel
        results = await asyncio.gather(
            *[self._fetch_quote_batch(batch) for batch in batches]
        )
        
        # Merge results
        merged = {}
        for result in results:
            merged.update(result)
        
        # Cache the result
        self._set_cache(cache_key, merged, "realtime_quotes")
        
        return merged

    async def get_index_quotes(self) -> Dict[str, Dict]:
        """
        Fetch major index quotes.
        
        Returns:
            Dict mapping index code to quote data:
            {
                "000001": {
                    "name": "上证指数",
                    "price": 3000.50,
                    "change": 15.20,
                    "change_pct": 0.51,
                    "volume": 1234567890,
                    "amount": 123456789012.34,
                },
                ...
            }
        """
        cache_key = "index_quotes"
        cached = self._get_cached(cache_key, "index_quotes")
        if cached:
            return cached
        
        # Build secids for all indices
        secids = ",".join(self.INDEX_CODES.values())
        
        params = {
            "secids": secids,
            "fields": "f12,f14,f2,f3,f4,f5,f6",
        }
        
        try:
            data = await self._fetch_json(self.INDEX_API, params)
            
            result = {}
            diff = data.get("data", {}).get("diff", [])
            
            for item in diff:
                secid = item.get("f12", "")
                code = secid.split(".")[-1] if "." in secid else secid
                
                # Eastmoney API returns values scaled by 100
                price = float(item.get("f2", 0)) / 100 if item.get("f2") else 0
                change_pct = float(item.get("f3", 0)) / 100 if item.get("f3") else 0
                change = float(item.get("f4", 0)) / 100 if item.get("f4") else 0
                
                result[code] = {
                    "name": self.INDEX_NAMES.get(code, item.get("f14", "")),
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": int(item.get("f5", 0)) if item.get("f5") else 0,
                    "amount": float(item.get("f6", 0)) if item.get("f6") else 0,
                }
            
            self._set_cache(cache_key, result, "index_quotes")
            return result
            
        except Exception as e:
            logger.error(f"AData index_quotes fetch failed: {e}")
            raise

    async def get_fund_nav(self, fund_code: str) -> Dict:
        """
        Fetch fund NAV estimate.
        
        Args:
            fund_code: Fund code (e.g., "000001")
            
        Returns:
            Dict with fund data:
            {
                "fund_code": "000001",
                "name": "华夏成长混合",
                "nav": 1.234,
                "change_pct": 1.56,
                "estimate_time": "2024-01-15 15:00",
            }
        """
        cache_key = f"fund_nav:{fund_code}"
        cached = self._get_cached(cache_key, "fund_nav")
        if cached:
            return cached
        
        url = self.FUND_API.format(code=fund_code)
        
        try:
            client = await self._get_client()
            response = await client.get(url)
            text = response.text
            
            # Parse JSONP response: jsonpgz({"fundcode":"000001",...})
            if "jsonpgz" in text:
                import json
                json_str = text.split("(")[1].rstrip(")")
                data = json.loads(json_str)
                
                result = {
                    "fund_code": data.get("fundcode", fund_code),
                    "name": data.get("name", ""),
                    "nav": float(data.get("gsz", 0)),
                    "change_pct": float(data.get("gszzl", 0)),
                    "estimate_time": data.get("gztime", ""),
                }
                
                self._set_cache(cache_key, result, "fund_nav")
                return result
            
            raise ValueError(f"Invalid JSONP response for fund {fund_code}")
            
        except Exception as e:
            logger.error(f"AData fund_nav fetch failed for {fund_code}: {e}")
            raise

    # ==================== Gateway Adapter Interface ====================

    async def fetch(self, endpoint: str, params: Optional[dict] = None) -> Any:
        """
        Gateway adapter interface.
        
        Args:
            endpoint: One of the supported endpoints
            params: Endpoint-specific parameters
            
        Returns:
            Dict or DataFrame with fetched data
        """
        params = params or {}
        
        if endpoint == "realtime_quotes" or endpoint == "stock_quotes":
            symbols = params.get("symbols", params.get("codes", []))
            return await self.get_realtime_quotes(symbols)
        elif endpoint == "index_quotes":
            return await self.get_index_quotes()
        elif endpoint == "fund_nav":
            fund_code = params.get("fund_code")
            if not fund_code:
                raise ValueError("fund_code is required for fund_nav endpoint")
            return await self.get_fund_nav(fund_code)
        else:
            raise ValueError(f"Unsupported endpoint: {endpoint}")

    # ==================== Internal Methods ====================

    async def _fetch_json(self, url: str, params: dict) -> Dict:
        """
        Fetch JSON data from broker API.
        
        Args:
            url: API endpoint URL
            params: Query parameters
            
        Returns:
            Dict with JSON response
        """
        client = await self._get_client()
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def _parse_response(self, data: Dict) -> pd.DataFrame:
        """
        Parse API response to DataFrame.
        
        Args:
            data: Raw API response dict
            
        Returns:
            DataFrame with parsed data
        """
        diff = data.get("data", {}).get("diff", [])
        
        if not diff:
            return pd.DataFrame()
        
        rows = []
        for item in diff:
            rows.append({
                "code": item.get("f12", "").split(".")[-1],
                "name": item.get("f14", ""),
                "price": float(item.get("f2", 0)) / 100 if item.get("f2") else 0,
                "change_pct": float(item.get("f3", 0)) / 100 if item.get("f3") else 0,
                "volume": int(item.get("f5", 0)) if item.get("f5") else 0,
            })
        
        return pd.DataFrame(rows)

    def _batch_symbols(self, symbols: List[str]) -> List[List[str]]:
        """
        Batch symbols into groups of max_batch_size.
        
        Args:
            symbols: List of symbols
            
        Returns:
            List of batches
        """
        batches = []
        for i in range(0, len(symbols), self._max_batch_size):
            batch = symbols[i:i + self._max_batch_size]
            batches.append(batch)
        return batches

    async def _fetch_quote_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Fetch quotes for a batch of symbols.
        
        Args:
            symbols: List of stock codes (max 50)
            
        Returns:
            Dict mapping symbol to quote data
        """
        # Build secids (SH=1, SZ=0)
        secids = []
        for code in symbols:
            market = "1" if code.startswith(("6", "5", "9")) else "0"
            secids.append(f"{market}.{code}")
        
        params = {
            "secids": ",".join(secids),
            "fields": "f12,f14,f2,f3,f4,f5,f6",
        }
        
        try:
            data = await self._fetch_json(self.QUOTE_API, params)
            
            result = {}
            diff = data.get("data", {}).get("diff", [])
            
            for item in diff:
                secid = item.get("f12", "")
                code = secid.split(".")[-1] if "." in secid else secid
                
                # Values are scaled by 100 in Eastmoney API
                price = float(item.get("f2", 0)) / 100 if item.get("f2") else 0
                change_pct = float(item.get("f3", 0)) / 100 if item.get("f3") else 0
                change = float(item.get("f4", 0)) / 100 if item.get("f4") else 0
                
                result[code] = {
                    "name": item.get("f14", ""),
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": int(item.get("f5", 0)) if item.get("f5") else 0,
                    "amount": float(item.get("f6", 0)) if item.get("f6") else 0,
                }
            
            return result
            
        except Exception as e:
            logger.warning(f"AData batch fetch failed for {symbols[:5]}...: {e}")
            # Return empty dict for failed batch (allows partial success)
            return {}

    # ==================== Deduplication & Caching ====================

    def _get_cached(self, key: str, query_type: str) -> Optional[Any]:
        """
        Get cached data if within TTL window.
        
        Args:
            key: Cache key
            query_type: Query type for validation
            
        Returns:
            Cached data or None if expired/not found
        """
        entry = self._cache.get(key)
        
        if entry is None:
            return None
        
        # Check TTL
        elapsed_ms = (time.time() - entry.timestamp) * 1000
        
        if elapsed_ms < self._cache_ttl_ms and entry.query_type == query_type:
            logger.debug(f"Returning cached data for {key} (age: {elapsed_ms:.1f}ms)")
            return entry.data
        
        # Cache expired, remove it
        del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Any, query_type: str) -> None:
        """
        Set cache entry.
        
        Args:
            key: Cache key
            data: Data to cache
            query_type: Query type
        """
        self._cache[key] = CacheEntry(
            data=data,
            timestamp=time.time(),
            query_type=query_type,
        )
        
        logger.debug(f"Cached data for {key}")

    def _clear_expired_cache(self) -> None:
        """Clear all expired cache entries."""
        current_time = time.time()
        
        expired_keys = [
            key for key, entry in self._cache.items()
            if (current_time - entry.timestamp) * 1000 > self._cache_ttl_ms
        ]
        
        for key in expired_keys:
            del self._cache[key]

    # ==================== Request Coalescing ====================

    async def _coalesce_request(
        self,
        query_type: str,
        symbol: str,
    ) -> Dict:
        """
        Coalesce request with same query type.
        
        Multiple concurrent requests for the same query type within
        the coalescing window are batched together.
        
        Args:
            query_type: Query type (realtime_quotes, fund_nav, etc.)
            symbol: Symbol to query
            
        Returns:
            Query result
        """
        key = f"{query_type}:{symbol}"
        
        # Check cache first
        cached = self._get_cached(key, query_type)
        if cached:
            return cached
        
        # Check if there's a pending request for this query type
        if query_type in self._pending_requests:
            pending = self._pending_requests[query_type]
            
            # Add symbol to pending batch
            if symbol not in pending.symbols:
                pending.symbols.append(symbol)
            
            # Create future for this request
            future: asyncio.Future = asyncio.get_event_loop().create_future()
            pending.futures.append(future)
            
            # Wait for the batched result
            return await future
        
        # No pending request, create new one
        pending = PendingRequest(
            symbols=[symbol],
            futures=[],
            query_type=query_type,
            scheduled_time=time.time(),
        )
        
        # Create future for this request
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        pending.futures.append(future)
        
        self._pending_requests[query_type] = pending
        
        # Schedule batch execution after coalescing window
        self._schedule_coalesce(query_type)
        
        # Wait for result
        return await future

    def _schedule_coalesce(self, query_type: str) -> None:
        """Schedule coalesced batch execution."""
        if self._coalesce_task is not None and not self._coalesce_task.done():
            return
        
        async def execute_after_window():
            await asyncio.sleep(self._coalesce_window_ms / 1000)
            await self._execute_coalesced_batch(query_type)
        
        self._coalesce_task = asyncio.create_task(execute_after_window())

    async def _execute_coalesced_batch(self, query_type: str) -> None:
        """Execute coalesced batch request."""
        pending = self._pending_requests.get(query_type)
        
        if pending is None:
            return
        
        try:
            # Execute batched query
            if query_type == "realtime_quotes":
                result = await self.get_realtime_quotes(pending.symbols)
            elif query_type == "fund_nav":
                # Fund NAV queries are individual
                results = await asyncio.gather(
                    *[self.get_fund_nav(s) for s in pending.symbols]
                )
                result = {s: r for s, r in zip(pending.symbols, results)}
            else:
                result = {}
            
            # Resolve all futures
            for future in pending.futures:
                if not future.done():
                    # Get result for this symbol
                    symbol_result = result.get(pending.symbols[0], result)
                    future.set_result(symbol_result)
            
        except Exception as e:
            # Reject all futures with error
            for future in pending.futures:
                if not future.done():
                    future.set_exception(e)
        
        finally:
            # Clear pending request
            del self._pending_requests[query_type]