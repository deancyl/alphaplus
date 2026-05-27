"""
Eastmoney data source adapter.

Uses Eastmoney Push2 JSON API for real-time market data.
Provides alternative data source with different rate limits and data format.
"""
import asyncio
import json
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class EastmoneySource:
    """
    Eastmoney Push2 API data source.

    Provides real-time market data through Eastmoney's JSON APIs.
    Good alternative when AkShare is rate-limited or failing.

    Supported endpoints:
    - index_quotes: Major index quotes via Push2 API
    - stock_quotes: Real-time stock quotes
    - fund_quotes: Fund real-time estimates
    - north_bound: North-bound capital flow
    """

    # Eastmoney Push2 API endpoints
    PUSH2_URL = "https://push2.eastmoney.com/api/qt"
    QUOTE_URL = "https://push2.eastmoney.com/api/qt/ulist.np"
    FUND_ESTIMATE_URL = "https://fundmobapi.eastmoney.com/fund/EstimateFund"

    # Index codes mapping
    INDEX_CODES = {
        "000001": "1.000001",   # 上证指数
        "399001": "0.399001",   # 深证成指
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

    def __init__(self, timeout: float = 10.0):
        self.name = "eastmoney"
        self._timeout = timeout
        self._supported_endpoints = [
            "index_quotes",
            "stock_quotes",
            "fund_quotes",
            "north_bound",
            "sector_quotes",
        ]

    def get_supported_endpoints(self) -> list[str]:
        return self._supported_endpoints

    def supports(self, endpoint: str) -> bool:
        return endpoint in self._supported_endpoints

    async def fetch(self, endpoint: str, params: Optional[dict] = None) -> Any:
        """
        Fetch data from Eastmoney API.

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
        elif endpoint == "fund_quotes":
            return await self._fetch_fund_quotes(params)
        elif endpoint == "north_bound":
            return await self._fetch_north_bound(params)
        elif endpoint == "sector_quotes":
            return await self._fetch_sector_quotes(params)
        else:
            raise ValueError(f"Unsupported endpoint: {endpoint}")

    async def _http_get(self, url: str, params: dict) -> dict:
        """Make HTTP GET request to Eastmoney API."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def _fetch_index_quotes(self, params: dict) -> dict:
        """
        Fetch major index quotes via Push2 API.

        Returns dict mapping index code to quote data.
        """
        # Build secids for all indices
        secids = ",".join(self.INDEX_CODES.values())

        request_params = {
            "secids": secids,
            "fields": "f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f55",
            "ut": "fa5fd1943c7b386f172d6893dbfba10f",
        }

        try:
            data = await self._http_get(self.QUOTE_URL, request_params)

            if data.get("data", {}).get("diff") is None:
                raise ValueError("No data returned from Eastmoney API")

            result = {}
            for item in data["data"]["diff"]:
                # Parse the secid format (market.code)
                secid = item.get("f12", "")
                code = secid.split(".")[-1] if "." in secid else secid

                name = self.INDEX_NAMES.get(code, item.get("f14", ""))
                price = float(item.get("f2", 0)) / 100 if item.get("f2") else 0
                change = float(item.get("f4", 0)) / 100 if item.get("f4") else 0
                change_pct = float(item.get("f3", 0)) / 100 if item.get("f3") else 0

                result[code] = {
                    "name": name,
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": int(item.get("f5", 0)) if item.get("f5") else 0,
                    "amount": float(item.get("f6", 0)) if item.get("f6") else 0,
                }

            return result

        except Exception as e:
            logger.error(f"Eastmoney index_quotes fetch failed: {e}")
            raise

    async def _fetch_stock_quotes(self, params: dict) -> list[dict]:
        """
        Fetch stock quotes by codes.

        Params:
            codes: List of stock codes (e.g., ["600000", "000001"])
        """
        codes = params.get("codes", [])
        if not codes:
            return []

        # Build secids (assume SH=1, SZ=0)
        secids = []
        for code in codes:
            market = "1" if code.startswith(("6", "5")) else "0"
            secids.append(f"{market}.{code}")

        request_params = {
            "secids": ",".join(secids),
            "fields": "f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f55",
        }

        try:
            data = await self._http_get(self.QUOTE_URL, request_params)

            results = []
            for item in data.get("data", {}).get("diff", []):
                results.append({
                    "code": item.get("f12", ""),
                    "name": item.get("f14", ""),
                    "price": float(item.get("f2", 0)) / 100 if item.get("f2") else 0,
                    "change_pct": float(item.get("f3", 0)) / 100 if item.get("f3") else 0,
                    "volume": int(item.get("f5", 0)) if item.get("f5") else 0,
                })

            return results

        except Exception as e:
            logger.error(f"Eastmoney stock_quotes fetch failed: {e}")
            raise

    async def _fetch_fund_quotes(self, params: dict) -> list[dict]:
        """
        Fetch fund real-time estimates.

        Params:
            fund_codes: List of fund codes
        """
        fund_codes = params.get("fund_codes", [])
        if not fund_codes:
            return []

        results = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for code in fund_codes:
                try:
                    response = await client.get(
                        f"https://fundgz.1234567.com.cn/js/{code}.js"
                    )
                    text = response.text
                    # Parse JSONP response: jsonpgz({"fundcode":"000001",...})
                    if "jsonpgz" in text:
                        json_str = text.split("(")[1].rstrip(")")
                        data = json.loads(json_str)
                        results.append({
                            "code": data.get("fundcode", code),
                            "name": data.get("name", ""),
                            "nav": float(data.get("gsz", 0)),
                            "change_pct": float(data.get("gszzl", 0)),
                            "time": data.get("gztime", ""),
                        })
                except Exception as e:
                    logger.warning(f"Failed to fetch fund {code}: {e}")

        return results

    async def _fetch_north_bound(self, params: dict) -> dict:
        """
        Fetch north-bound capital flow data.
        """
        url = "https://push2.eastmoney.com/api/qt/kamtget"
        request_params = {
            "fields1": "f1,f2,f3,f4",
            "fields2": "f51,f52,f53,f54,f55,f56",
            "ut": "fa5fd1943c7b386f172d6893dbfba10f",
        }

        try:
            data = await self._http_get(url, request_params)

            if not data.get("data"):
                raise ValueError("No north-bound data returned")

            result = {
                "net_inflow": 0.0,
                "shanghai_inflow": 0.0,
                "shenzhen_inflow": 0.0,
            }

            for item in data.get("data", {}).get("diff", []):
                market = item.get("f1", "")
                value = float(item.get("f2", 0)) / 100 if item.get("f2") else 0

                if market == "1":  # Shanghai
                    result["shanghai_inflow"] = value
                elif market == "2":  # Shenzhen
                    result["shenzhen_inflow"] = value

            result["net_inflow"] = result["shanghai_inflow"] + result["shenzhen_inflow"]
            return result

        except Exception as e:
            logger.error(f"Eastmoney north_bound fetch failed: {e}")
            raise

    async def _fetch_sector_quotes(self, params: dict) -> list[dict]:
        """
        Fetch sector/board real-time quotes.
        """
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        request_params = {
            "pn": "1",
            "pz": "20",
            "po": "1",
            "fid": "f3",
            "fs": "m:90+t:2",
            "fields": "f12,f14,f2,f3,f4",
        }

        try:
            data = await self._http_get(url, request_params)

            results = []
            for item in data.get("data", {}).get("diff", []):
                results.append({
                    "code": item.get("f12", ""),
                    "name": item.get("f14", ""),
                    "change_pct": float(item.get("f3", 0)) / 100 if item.get("f3") else 0,
                })

            return results

        except Exception as e:
            logger.error(f"Eastmoney sector_quotes fetch failed: {e}")
            raise
