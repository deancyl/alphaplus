"""
Sina data source adapter.

Uses Sina Finance APIs for real-time market data.
Provides lightweight alternative with different rate limits.
"""
import asyncio
import logging
import re
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class SinaSource:
    """
    Sina Finance API data source.

    Provides real-time stock and index data through Sina's APIs.
    Fast response time, good for high-frequency polling.

    Supported endpoints:
    - index_quotes: Major index quotes
    - stock_quotes: Real-time stock quotes
    - futures_quotes: Futures quotes
    - hk_stock_quotes: Hong Kong stock quotes
    """

    # Sina API endpoints
    QUOTE_URL = "https://hq.sinajs.cn/list={}"
    FUTURES_URL = "http://hq.sinajs.cn/list=nf_{}"
    HK_STOCK_URL = "https://stock.finance.sina.com.cn/stock/quote/hkstock/jsonp.php/IO.XSRV2.CallbackData/hk_stock_data"

    # Index codes for Sina API
    INDEX_CODES = {
        "000001": "sh000001",   # 上证指数
        "399001": "sz399001",   # 深证成指
        "000300": "sh000300",   # 沪深300
        "000905": "sh000905",   # 中证500
        "000852": "sh000852",   # 中证1000
        "399006": "sz399006",   # 创业板指
        "000688": "sh000688",   # 科创50
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

    def __init__(self, timeout: float = 10.0):
        self.name = "sina"
        self._timeout = timeout
        self._supported_endpoints = [
            "index_quotes",
            "stock_quotes",
            "futures_quotes",
            "hk_stock_quotes",
        ]

    def get_supported_endpoints(self) -> list[str]:
        return self._supported_endpoints

    def supports(self, endpoint: str) -> bool:
        return endpoint in self._supported_endpoints

    async def fetch(self, endpoint: str, params: Optional[dict] = None) -> Any:
        """
        Fetch data from Sina API.

        Args:
            endpoint: One of the supported endpoints
            params: Endpoint-specific parameters

        Returns:
            Dict or list with fetched data
        """
        params = params or {}

        if endpoint == "index_quotes":
            return await self._fetch_index_quotes(params)
        elif endpoint == "stock_quotes":
            return await self._fetch_stock_quotes(params)
        elif endpoint == "futures_quotes":
            return await self._fetch_futures_quotes(params)
        elif endpoint == "hk_stock_quotes":
            return await self._fetch_hk_stock_quotes(params)
        else:
            raise ValueError(f"Unsupported endpoint: {endpoint}")

    async def _http_get(self, url: str) -> str:
        """Make HTTP GET request to Sina API."""
        headers = {
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text

    def _parse_sina_quote(self, text: str) -> dict:
        """
        Parse Sina quote response format.

        Format: var hq_str_sh000001="上证指数,3000.00,2990.00,..."
        """
        quotes = {}

        # Match pattern: var hq_str_<code>="<data>"
        pattern = r'var hq_str_([^=]+)="([^"]*)"'
        matches = re.findall(pattern, text)

        for code, data in matches:
            if not data:
                continue

            parts = data.split(",")
            if len(parts) >= 6:
                # For indices: name, open, prev_close, current, high, low, ...
                name = parts[0]
                current = float(parts[3]) if parts[3] else 0
                prev_close = float(parts[2]) if parts[2] else 0
                change = current - prev_close if current and prev_close else 0
                change_pct = (change / prev_close * 100) if prev_close else 0

                # Normalize code (remove sh/sz prefix)
                clean_code = code.replace("sh", "").replace("sz", "")

                quotes[clean_code] = {
                    "name": self.INDEX_NAMES.get(clean_code, name),
                    "price": current,
                    "change": change,
                    "change_pct": round(change_pct, 2),
                    "volume": int(parts[8]) if len(parts) > 8 and parts[8] else 0,
                    "amount": float(parts[9]) if len(parts) > 9 and parts[9] else 0,
                }

        return quotes

    async def _fetch_index_quotes(self, params: dict) -> dict:
        """
        Fetch major index quotes from Sina.

        Returns dict mapping index code to quote data.
        """
        codes = ",".join(self.INDEX_CODES.values())
        url = self.QUOTE_URL.format(codes)

        try:
            text = await self._http_get(url)
            return self._parse_sina_quote(text)

        except Exception as e:
            logger.error(f"Sina index_quotes fetch failed: {e}")
            raise

    async def _fetch_stock_quotes(self, params: dict) -> list[dict]:
        """
        Fetch stock quotes by codes.

        Params:
            codes: List of stock codes (e.g., ["sh600000", "sz000001"])
        """
        codes = params.get("codes", [])
        if not codes:
            return []

        # Build Sina-formatted codes
        sina_codes = []
        for code in codes:
            if code.startswith("6"):
                sina_codes.append(f"sh{code}")
            else:
                sina_codes.append(f"sz{code}")

        url = self.QUOTE_URL.format(",".join(sina_codes))

        try:
            text = await self._http_get(url)
            quotes = self._parse_sina_quote(text)

            results = []
            for code in codes:
                if code in quotes:
                    results.append(quotes[code])

            return results

        except Exception as e:
            logger.error(f"Sina stock_quotes fetch failed: {e}")
            raise

    async def _fetch_futures_quotes(self, params: dict) -> list[dict]:
        """
        Fetch futures quotes from Sina.

        Params:
            codes: List of futures codes (e.g., ["AU0", "CU0"])
        """
        codes = params.get("codes", ["AU0", "AG0", "CU0", "RB0"])

        results = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for code in codes:
                try:
                    url = self.FUTURES_URL.format(code.lower())
                    text = await self._http_get(url)

                    # Parse: var hq_str_nf_au0="黄金,500.00,..."
                    pattern = r'var hq_str_nf_[^=]+="([^"]*)"'
                    match = re.search(pattern, text)

                    if match:
                        data = match.group(1)
                        parts = data.split(",")
                        if len(parts) >= 6:
                            results.append({
                                "code": code,
                                "name": parts[0],
                                "price": float(parts[1]) if parts[1] else 0,
                                "change_pct": float(parts[5]) if parts[5] else 0,
                            })

                except Exception as e:
                    logger.warning(f"Failed to fetch futures {code}: {e}")

        return results

    async def _fetch_hk_stock_quotes(self, params: dict) -> list[dict]:
        """
        Fetch Hong Kong stock quotes.

        Params:
            codes: List of HK stock codes (e.g., ["00700", "00941"])
        """
        codes = params.get("codes", [])
        if not codes:
            return []

        results = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for code in codes:
                try:
                    # HK stocks use hk prefix
                    url = self.QUOTE_URL.format(f"hk{code}")
                    text = await self._http_get(url)

                    pattern = r'var hq_str_hk[^=]+="([^"]*)"'
                    match = re.search(pattern, text)

                    if match:
                        data = match.group(1)
                        parts = data.split(",")
                        if len(parts) >= 6:
                            results.append({
                                "code": code,
                                "name": parts[1],
                                "price": float(parts[6]) if parts[6] else 0,
                                "change_pct": float(parts[8]) if len(parts) > 8 and parts[8] else 0,
                            })

                except Exception as e:
                    logger.warning(f"Failed to fetch HK stock {code}: {e}")

        return results
