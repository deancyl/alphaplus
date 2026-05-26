"""
Real-time index quotes service.
"""
import asyncio
from datetime import datetime
import random

import akshare as ak

from backend.services.cache import realtime_cache
from backend.services.rate_limiter import RateLimiter


class IndexQuotesService:
    """
    指数行情服务 - 5秒伪实时刷新.
    Maintains global cache shared across all frontend requests.
    """
    
    def __init__(self):
        self.rate_limiter = RateLimiter(rate=5)  # 5 req/s for real-time
    
    async def refresh(self):
        """
        刷新指数行情数据到缓存.
        Called by scheduler every 5 seconds during trading hours.
        """
        try:
            # Get real-time quotes from AkShare
            await self.rate_limiter.acquire()
            
            # 东方财富实时行情
            df = ak.stock_zh_index_spot_em()
            
            # Filter major indices
            major_indices = {
                "000001": "上证指数",
                "399001": "深证成指",
                "000300": "沪深300",
                "000016": "上证50",
                "000905": "中证500",
                "399006": "创业板指",
                "000688": "科创50",
            }
            
            indices_data = {}
            for code, name in major_indices.items():
                row = df[df["代码"] == code]
                if not row.empty:
                    row = row.iloc[0]
                    indices_data[code] = {
                        "name": name,
                        "price": float(row.get("最新价", 0)),
                        "change": float(row.get("涨跌额", 0)),
                        "change_pct": float(row.get("涨跌幅", 0)),
                        "volume": float(row.get("成交量", 0)),
                        "amount": float(row.get("成交额", 0)),
                    }
            
            # Update cache
            await realtime_cache.set("indices", indices_data)
            
        except Exception as e:
            print(f"Index quotes refresh error: {e}")
    
    async def get_all(self) -> dict:
        """获取所有指数行情."""
        return await realtime_cache.get("indices") or {}
    
    async def get_one(self, code: str) -> dict:
        """获取单个指数行情."""
        indices = await self.get_all()
        return indices.get(code, {})


# Global quotes service
index_quotes = IndexQuotesService()
