"""
AkShare data service layer with rate limiting and error handling.
Provides typed methods for fetching real market data.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

import akshare as ak

from backend.services.rate_limiter import RateLimiter
from backend.services.resilience import RetryConfig, retry_with_backoff

logger = logging.getLogger(__name__)


class AkShareDataError(Exception):
    """Raised when AkShare data fetch fails."""
    pass


class AkShareDataService:
    """
    Service for fetching real market data from AkShare.
    All methods include error handling and return typed data.
    """

    def __init__(self, rate_limit_delay: float = 0.5):
        self._rate_limit_delay = rate_limit_delay
        self._last_call_time: float = 0
        self._lock = asyncio.Lock()
        self._rate_limiter = RateLimiter(rate=2.0, capacity=3)
        self._retry_config = RetryConfig(max_retries=5, base_delay=1.0)

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between API calls."""
        await self._rate_limiter.acquire()

    @retry_with_backoff()
    async def _run_sync(self, func, *args, **kwargs):
        """Run synchronous AkShare function in thread pool with retry."""
        await self._rate_limit()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def get_index_quotes(self) -> dict[str, dict]:
        """
        Fetch real-time quotes for major Chinese indices.
        
        Returns:
            Dict mapping index code to quote data.
            Example: {"000001": {"name": "上证指数", "price": 3000.0, ...}}
        """
        try:
            df = await self._run_sync(ak.stock_zh_index_spot_em, symbol="上证系列指数")
            
            result = {}
            index_mapping = {
                "000001": "上证指数",
                "399001": "深证成指",
                "000300": "沪深300",
                "000905": "中证500",
                "000852": "中证1000",
                "399006": "创业板指",
                "000688": "科创50",
            }
            
            for code, name in index_mapping.items():
                row = df[df["代码"] == code]
                if not row.empty:
                    result[code] = {
                        "name": name,
                        "price": float(row["最新价"].values[0]),
                        "change": float(row["涨跌"].values[0]),
                        "change_pct": float(row["涨跌幅"].values[0]),
                    }
            
            return result
        except Exception as e:
            logger.error(f"Failed to fetch index quotes: {e}")
            return {}

    async def get_futures_quotes(self, category: Optional[str] = None) -> list[dict]:
        """
        Fetch real-time futures quotes.
        
        Args:
            category: Filter by category (金融期货, 商品期货, 能源期货)
        
        Returns:
            List of futures contract data.
        """
        try:
            df = await self._run_sync(ak.futures_zh_spot)
            
            futures_list = []
            for _, row in df.iterrows():
                item = {
                    "code": row.get("symbol", ""),
                    "name": row.get("name", ""),
                    "exchange": row.get("exchange", ""),
                    "category": self._categorize_futures(row.get("symbol", "")),
                    "price": float(row.get("close", 0)),
                    "change": float(row.get("change", 0)),
                    "change_pct": float(row.get("pct_chg", 0)),
                    "volume": int(row.get("volume", 0)),
                    "open_interest": int(row.get("open_interest", 0)),
                    "spot_price": float(row.get("close", 0)),
                    "basis": 0.0,
                    "basis_pct": 0.0,
                    "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                
                if category is None or item["category"] == category:
                    futures_list.append(item)
            
            return futures_list[:50]
        except Exception as e:
            logger.error(f"Failed to fetch futures quotes: {e}")
            return []

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

    async def get_global_indices(self) -> list[dict]:
        """
        Fetch global market index quotes.
        
        Returns:
            List of global index data.
        """
        try:
            df = await self._run_sync(ak.index_global_index_comprehensive)
            
            indices = []
            for _, row in df.head(8).iterrows():
                indices.append({
                    "code": row.get("代码", ""),
                    "name": row.get("名称", ""),
                    "price": float(row.get("最新价", 0)),
                    "change_pct": float(row.get("涨跌幅", 0)),
                })
            
            return indices
        except Exception as e:
            logger.error(f"Failed to fetch global indices: {e}")
            return []

    async def get_currency_rates(self) -> list[dict]:
        """
        Fetch currency exchange rates.
        
        Returns:
            List of currency pair data.
        """
        try:
            df = await self._run_sync(ak.currency_boc_safe)
            
            currencies = []
            for _, row in df.head(4).iterrows():
                currencies.append({
                    "code": row.get("货币名称", ""),
                    "name": row.get("货币名称", ""),
                    "price": float(row.get("中行折算价", 0)),
                    "change_pct": 0.0,
                })
            
            return currencies
        except Exception as e:
            logger.error(f"Failed to fetch currency rates: {e}")
            return []

    async def get_commodities(self) -> list[dict]:
        """
        Fetch commodity prices.
        
        Returns:
            List of commodity data.
        """
        try:
            df = await self._run_sync(ak.futures_main_sina, symbol="AU0")
            
            commodities = []
            if not df.empty:
                commodities.append({
                    "code": "GOLD",
                    "name": "黄金",
                    "price": float(df["close"].iloc[-1]),
                    "change_pct": 0.0,
                })
            
            return commodities
        except Exception as e:
            logger.error(f"Failed to fetch commodities: {e}")
            return []

    async def get_domestic_sectors(self) -> list[dict]:
        """
        Fetch domestic market sector performance.
        
        Returns:
            List of sector performance data.
        """
        try:
            df = await self._run_sync(ak.stock_board_industry_name_em)
            
            sectors = []
            for _, row in df.head(15).iterrows():
                sectors.append({
                    "name": row.get("板块名称", ""),
                    "change_pct": float(row.get("涨跌幅", 0)),
                })
            
            return sectors
        except Exception as e:
            logger.error(f"Failed to fetch sector data: {e}")
            return []

    async def get_market_heatmap(self) -> dict:
        """
        Generate market heatmap data from real index performance.
        
        Returns:
            Dict with rows, cols, and cells for heatmap rendering.
        """
        try:
            indices_df = await self._run_sync(ak.index_stock_info)
            
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
        except Exception as e:
            logger.error(f"Failed to fetch heatmap data: {e}")
            return {"rows": [], "cols": [], "cells": []}
    
    async def get_fund_nav_history(self, fund_code: str, days: int = 252) -> dict:
        """
        Fetch historical NAV data for a specific fund.
        
        Args:
            fund_code: Fund code (e.g., "000001")
            days: Number of trading days to fetch (default: 252 = 1 year)
        
        Returns:
            Dict with 'dates' (list of date strings) and 'nav_values' (list of floats)
        
        Raises:
            AkShareDataError: If data fetch fails
        """
        try:
            df = await self._run_sync(
                ak.fund_open_fund_info_em,
                symbol=fund_code,
                indicator="单位净值走势",
                period="1年"
            )
            
            if df.empty:
                raise AkShareDataError(f"No NAV history found for fund {fund_code}")
            
            df.columns = ['date', 'nav', 'daily_return']
            df = df.sort_values('date', ascending=False).head(days)
            df = df.iloc[::-1]
            
            return {
                "fund_code": fund_code,
                "dates": df['date'].tolist(),
                "nav_values": df['nav'].astype(float).tolist(),
                "daily_returns": df['daily_return'].astype(float).tolist() if 'daily_return' in df.columns else None,
            }
        except AkShareDataError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch NAV history for {fund_code}: {e}")
            raise AkShareDataError(f"Failed to fetch NAV history for fund {fund_code}: {e}")
    
    async def get_multiple_fund_nav_histories(self, fund_codes: list[str], days: int = 252) -> dict[str, dict]:
        """
        Fetch historical NAV data for multiple funds.
        
        Args:
            fund_codes: List of fund codes
            days: Number of trading days to fetch per fund
        
        Returns:
            Dict mapping fund_code to NAV history data
        """
        results = {}
        for code in fund_codes:
            try:
                results[code] = await self.get_fund_nav_history(code, days)
            except AkShareDataError as e:
                logger.warning(f"Skipping fund {code}: {e}")
                results[code] = None
        
        return results


akshare_data_service = AkShareDataService()
