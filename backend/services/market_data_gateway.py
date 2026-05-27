"""
Market Data Gateway with TieredCache integration.
Provides unified interface for market data fetching with caching.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.services.tiered_cache import tiered_cache
from backend.services.akshare_data import akshare_data_service
from backend.services.index_valuation import get_index_valuation_data, get_all_indices_valuation

logger = logging.getLogger(__name__)


class MarketDataGateway:
    """
    Gateway for fetching market data with automatic tiered caching.
    
    All data requests go through cache first (L1 → L2 → API).
    TTL is configurable per data type.
    """
    
    INDEX_QUOTES_TTL = 300  # 5 min for real-time quotes
    INDEX_VALUATION_TTL = 3600  # 1 hour for valuation data
    FUND_NAV_TTL = 1800  # 30 min for fund NAV
    GLOBAL_MARKET_TTL = 600  # 10 min for global data
    
    async def get_index_quotes(self) -> Dict[str, Dict]:
        """
        Get real-time index quotes with caching.
        
        Returns:
            Dict mapping index code to quote data
        """
        cache_key = "market:index_quotes"
        
        cached = tiered_cache.get(cache_key)
        if cached is not None:
            return cached
        
        quotes = await akshare_data_service.get_index_quotes()
        if quotes:
            tiered_cache.set(cache_key, quotes, ttl=self.INDEX_QUOTES_TTL)
        
        return quotes or {}
    
    async def get_index_valuation(self, index_code: str) -> Dict[str, Any]:
        """
        Get index valuation data (PE/PB/percentile) with caching.
        
        Args:
            index_code: Index code (e.g., "000300")
        
        Returns:
            Valuation data dict
        """
        cache_key = f"market:index_valuation:{index_code}"
        
        cached = tiered_cache.get(cache_key)
        if cached is not None:
            return cached
        
        valuation = await get_index_valuation_data(index_code)
        tiered_cache.set(cache_key, valuation, ttl=self.INDEX_VALUATION_TTL)
        
        return valuation
    
    async def get_all_index_valuations(self) -> List[Dict[str, Any]]:
        """
        Get all 17 core index valuations with caching.
        
        Returns:
            List of valuation dicts
        """
        cache_key = "market:index_valuations:all"
        
        cached = tiered_cache.get(cache_key)
        if cached is not None:
            return cached
        
        valuations = await get_all_indices_valuation()
        tiered_cache.set(cache_key, valuations, ttl=self.INDEX_VALUATION_TTL)
        
        return valuations
    
    async def get_futures_quotes(self, category: Optional[str] = None) -> List[Dict]:
        """
        Get futures quotes with caching.
        
        Args:
            category: Filter by category (金融期货/商品期货/能源期货)
        
        Returns:
            List of futures quote dicts
        """
        cache_key = f"market:futures_quotes:{category or 'all'}"
        
        cached = tiered_cache.get(cache_key)
        if cached is not None:
            return cached
        
        quotes = await akshare_data_service.get_futures_quotes(category)
        tiered_cache.set(cache_key, quotes, ttl=self.INDEX_QUOTES_TTL)
        
        return quotes
    
    async def get_global_indices(self) -> List[Dict]:
        """
        Get global market indices with caching.
        
        Returns:
            List of global index dicts
        """
        cache_key = "market:global_indices"
        
        cached = tiered_cache.get(cache_key)
        if cached is not None:
            return cached
        
        indices = await akshare_data_service.get_global_indices()
        tiered_cache.set(cache_key, indices, ttl=self.GLOBAL_MARKET_TTL)
        
        return indices
    
    async def get_currency_rates(self) -> List[Dict]:
        """
        Get currency exchange rates with caching.
        
        Returns:
            List of currency rate dicts
        """
        cache_key = "market:currency_rates"
        
        cached = tiered_cache.get(cache_key)
        if cached is not None:
            return cached
        
        rates = await akshare_data_service.get_currency_rates()
        tiered_cache.set(cache_key, rates, ttl=self.GLOBAL_MARKET_TTL)
        
        return rates
    
    async def get_commodities(self) -> List[Dict]:
        """
        Get commodity prices with caching.
        
        Returns:
            List of commodity dicts
        """
        cache_key = "market:commodities"
        
        cached = tiered_cache.get(cache_key)
        if cached is not None:
            return cached
        
        commodities = await akshare_data_service.get_commodities()
        tiered_cache.set(cache_key, commodities, ttl=self.GLOBAL_MARKET_TTL)
        
        return commodities
    
    async def get_global_market(self) -> Dict[str, Any]:
        """
        Get global market overview (indices + currencies + commodities).
        
        Returns:
            Aggregated global market dict
        """
        cache_key = "market:global_overview"
        
        cached = tiered_cache.get(cache_key)
        if cached is not None:
            return cached
        
        indices, currencies, commodities = await asyncio.gather(
            self.get_global_indices(),
            self.get_currency_rates(),
            self.get_commodities(),
        )
        
        result = {
            "indices": indices,
            "currencies": currencies,
            "commodities": commodities,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        tiered_cache.set(cache_key, result, ttl=self.GLOBAL_MARKET_TTL)
        return result
    
    async def get_domestic_sectors(self) -> List[Dict]:
        """
        Get domestic market sector performance with caching.
        
        Returns:
            List of sector performance dicts
        """
        cache_key = "market:domestic_sectors"
        
        cached = tiered_cache.get(cache_key)
        if cached is not None:
            return cached
        
        sectors = await akshare_data_service.get_domestic_sectors()
        tiered_cache.set(cache_key, sectors, ttl=self.INDEX_QUOTES_TTL)
        
        return sectors
    
    async def get_fund_nav_history(self, fund_code: str, days: int = 252) -> Dict:
        """
        Get fund NAV history with caching.
        
        Args:
            fund_code: Fund code
            days: Number of days
        
        Returns:
            NAV history dict
        """
        cache_key = f"fund:nav_history:{fund_code}:{days}"
        
        cached = tiered_cache.get(cache_key)
        if cached is not None:
            return cached
        
        history = await akshare_data_service.get_fund_nav_history(fund_code, days)
        tiered_cache.set(cache_key, history, ttl=self.FUND_NAV_TTL)
        
        return history
    
    def invalidate(self, key_pattern: str) -> int:
        """
        Invalidate cache entries matching pattern.
        
        Args:
            key_pattern: Key prefix pattern (e.g., "market:index_quotes")
        
        Returns:
            Number of entries invalidated
        """
        count = 0
        
        count += tiered_cache.delete(key_pattern)
        
        return count


import asyncio

market_data_gateway = MarketDataGateway()