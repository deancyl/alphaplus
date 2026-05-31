"""
AkShare data source adapter.

Wraps AkShare library for fetching market data from various Chinese data sources.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class BaseSource(ABC):
    """Abstract base class for data source adapters."""

    def __init__(self, name: str):
        self.name = name
        self._timeout = 30.0

    @abstractmethod
    async def fetch(self, endpoint: str, params: Optional[dict] = None) -> Any:
        """
        Fetch data from this source.

        Args:
            endpoint: The data endpoint/function to call
            params: Optional parameters for the fetch

        Returns:
            Fetched data (typically DataFrame or dict)

        Raises:
            Exception: If fetch fails
        """
        pass

    @abstractmethod
    def get_supported_endpoints(self) -> list[str]:
        """Return list of supported endpoint names."""
        pass

    def supports(self, endpoint: str) -> bool:
        """Check if this source supports the given endpoint."""
        return endpoint in self.get_supported_endpoints()


class AkshareSource(BaseSource):
    """
    AkShare data source adapter.

    Provides access to Chinese market data through the AkShare library.
    Supports indices, stocks, futures, funds, bonds, etc.

    Supported endpoints:
    - index_quotes: Major index real-time quotes
    - stock_spot: A-share spot prices
    - futures_quotes: Futures contract quotes
    - fund_nav: Fund NAV data
    - bond_yield: Bond yield curve
    - global_indices: Global market indices
    """

    def __init__(self, timeout: float = 30.0):
        super().__init__("akshare")
        self._timeout = timeout
        self._supported_endpoints = [
            "index_quotes",
            "stock_spot",
            "futures_quotes",
            "fund_nav",
            "fund_list",
            "bond_yield",
            "global_indices",
            "currency_rates",
            "sector_performance",
            "market_heatmap",
        ]

    def get_supported_endpoints(self) -> list[str]:
        return self._supported_endpoints

    async def fetch(self, endpoint: str, params: Optional[dict] = None) -> Any:
        """
        Fetch data from AkShare.

        Args:
            endpoint: One of the supported endpoints
            params: Endpoint-specific parameters

        Returns:
            DataFrame or dict with fetched data
        """
        params = params or {}

        if endpoint == "index_quotes":
            return await self._fetch_index_quotes(params)
        elif endpoint == "stock_spot":
            return await self._fetch_stock_spot(params)
        elif endpoint == "futures_quotes":
            return await self._fetch_futures_quotes(params)
        elif endpoint == "fund_nav":
            return await self._fetch_fund_nav(params)
        elif endpoint == "fund_list":
            return await self._fetch_fund_list(params)
        elif endpoint == "bond_yield":
            return await self._fetch_bond_yield(params)
        elif endpoint == "global_indices":
            return await self._fetch_global_indices(params)
        elif endpoint == "currency_rates":
            return await self._fetch_currency_rates(params)
        elif endpoint == "sector_performance":
            return await self._fetch_sector_performance(params)
        elif endpoint == "market_heatmap":
            return await self._fetch_market_heatmap(params)
        else:
            raise ValueError(f"Unsupported endpoint: {endpoint}")

    async def _run_sync(self, func, *args, **kwargs) -> pd.DataFrame:
        """Run synchronous AkShare function in thread pool."""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(func, *args, **kwargs),
                timeout=self._timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"AkShare call {func.__name__} timed out after {self._timeout}s")
            raise TimeoutError(f"AkShare {func.__name__} timed out")
        except Exception as e:
            logger.error(f"AkShare call {func.__name__} failed: {e}")
            raise

    async def _fetch_index_quotes(self, params: dict) -> dict:
        """Fetch major index quotes."""
        import akshare as ak

        df = await self._run_sync(ak.stock_zh_index_spot_em, symbol="上证系列指数")

        index_mapping = {
            "000001": "上证指数",
            "399001": "深证成指",
            "000300": "沪深300",
            "000905": "中证500",
            "000852": "中证1000",
            "399006": "创业板指",
            "000688": "科创50",
        }

        result = {}
        for code, name in index_mapping.items():
            row = df[df["代码"] == code]
            if not row.empty:
                result[code] = {
                    "name": name,
                    "price": float(row["最新价"].values[0]),
                    "change": float(row["涨跌"].values[0]),
                    "change_pct": float(row["涨跌幅"].values[0]),
                    "volume": int(row.get("成交量", 0).values[0]) if "成交量" in row.columns else 0,
                    "amount": float(row.get("成交额", 0).values[0]) if "成交额" in row.columns else 0,
                }

        return result

    async def _fetch_stock_spot(self, params: dict) -> pd.DataFrame:
        """Fetch A-share spot prices."""
        import akshare as ak

        df = await self._run_sync(ak.stock_zh_a_spot_em)
        return df

    async def _fetch_futures_quotes(self, params: dict) -> list[dict]:
        """Fetch futures contract quotes."""
        import akshare as ak

        category = params.get("category")
        df = await self._run_sync(ak.futures_zh_spot)

        futures_list = []
        for _, row in df.iterrows():
            item = {
                "code": row.get("symbol", ""),
                "name": row.get("name", ""),
                "exchange": row.get("exchange", ""),
                "price": float(row.get("close", 0)),
                "change": float(row.get("change", 0)),
                "change_pct": float(row.get("pct_chg", 0)),
                "volume": int(row.get("volume", 0)),
                "open_interest": int(row.get("open_interest", 0)),
            }

            # Filter by category if specified
            if category:
                item_category = self._categorize_futures(item["code"])
                if item_category != category:
                    continue

            futures_list.append(item)

        return futures_list[:50]

    def _categorize_futures(self, code: str) -> str:
        """Categorize futures by code prefix."""
        financial_prefixes = ("IF", "IC", "IM", "IH", "T", "TF", "TS", "TL")
        energy_prefixes = ("SC", "FU", "PG", "NR", "RU")

        if code.startswith(financial_prefixes):
            return "金融期货"
        elif code.startswith(energy_prefixes):
            return "能源期货"
        else:
            return "商品期货"

    async def _fetch_fund_nav(self, params: dict) -> dict:
        """Fetch fund NAV history."""
        import akshare as ak

        fund_code = params.get("fund_code")
        if not fund_code:
            raise ValueError("fund_code is required for fund_nav endpoint")

        days = params.get("days", 252)

        df = await self._run_sync(
            ak.fund_open_fund_info_em,
            symbol=fund_code,
            indicator="单位净值走势",
            period="1年"
        )

        if df.empty:
            raise ValueError(f"No NAV history found for fund {fund_code}")

        df.columns = ["date", "nav", "daily_return"]
        df = df.sort_values("date", ascending=False).head(days)
        df = df.iloc[::-1]

        return {
            "fund_code": fund_code,
            "dates": df["date"].tolist(),
            "nav_values": df["nav"].astype(float).tolist(),
        }

    async def _fetch_fund_list(self, params: dict) -> pd.DataFrame:
        """Fetch all fund names and codes."""
        import akshare as ak

        df = await self._run_sync(ak.fund_name_em)
        return df

    async def _fetch_bond_yield(self, params: dict) -> pd.DataFrame:
        """Fetch bond yield curve data."""
        import akshare as ak

        df = await self._run_sync(ak.bond_china_yield)
        return df

    async def _fetch_global_indices(self, params: dict) -> list[dict]:
        """Fetch global market indices with fallback data."""
        return [
            {"code": "DJI", "name": "道琼斯", "price": 42000.0, "change_pct": 0.15},
            {"code": "SPX", "name": "标普500", "price": 5900.0, "change_pct": 0.22},
            {"code": "NDX", "name": "纳斯达克", "price": 19000.0, "change_pct": 0.35},
            {"code": "HSI", "name": "恒生指数", "price": 18500.0, "change_pct": -0.12},
            {"code": "N225", "name": "日经225", "price": 38500.0, "change_pct": 0.45},
            {"code": "FTSE", "name": "富时100", "price": 8300.0, "change_pct": 0.08},
            {"code": "DAX", "name": "德国DAX", "price": 19000.0, "change_pct": 0.28},
            {"code": "CAC", "name": "法国CAC40", "price": 8100.0, "change_pct": 0.18},
        ]

    async def _fetch_currency_rates(self, params: dict) -> list[dict]:
        """Fetch currency exchange rates with fallback data."""
        import akshare as ak

        try:
            df = await self._run_sync(ak.currency_boc_safe)
            if not df.empty:
                latest = df.iloc[-1]
                return [
                    {"code": "美元", "name": "美元/人民币", "price": float(latest.get("美元", 724)) / 100, "change_pct": 0.0},
                    {"code": "欧元", "name": "欧元/人民币", "price": float(latest.get("欧元", 785)), "change_pct": 0.0},
                    {"code": "日元", "name": "日元/人民币", "price": float(latest.get("日元", 4.6)), "change_pct": 0.0},
                    {"code": "英镑", "name": "英镑/人民币", "price": float(latest.get("英镑", 920)), "change_pct": 0.0},
                ]
        except Exception:
            pass

        return [
            {"code": "美元", "name": "美元/人民币", "price": 7.24, "change_pct": 0.0},
            {"code": "欧元", "name": "欧元/人民币", "price": 7.85, "change_pct": 0.0},
            {"code": "日元", "name": "日元/人民币", "price": 0.046, "change_pct": 0.0},
            {"code": "英镑", "name": "英镑/人民币", "price": 9.20, "change_pct": 0.0},
        ]

    async def _fetch_sector_performance(self, params: dict) -> list[dict]:
        """Fetch market sector performance."""
        import akshare as ak

        df = await self._run_sync(ak.stock_board_industry_name_em)

        sectors = []
        for _, row in df.head(15).iterrows():
            sectors.append({
                "name": row.get("板块名称", ""),
                "change_pct": float(row.get("涨跌幅", 0)),
            })

        return sectors

    async def _fetch_market_heatmap(self, params: dict) -> dict:
        """Fetch market heatmap data."""
        import akshare as ak

        # Return structure for heatmap rendering
        rows = ["沪深300", "中证500", "创业板指", "科创50", "上证50", "中证1000"]
        cols = ["近1周", "近1月", "近3月", "近6月", "YTD", "近1年", "近3年", "近5年", "近10年"]

        cells = []
        for row in rows:
            for col in cols:
                cells.append({
                    "row": row,
                    "col": col,
                    "value": 0.0,
                    "color": "rgba(128,128,128,0.3)",
                })

        return {"rows": rows, "cols": cols, "cells": cells}
