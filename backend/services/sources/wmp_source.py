"""
Wealth Management Product (WMP) Source Adapter.

银行理财产品数据源适配器，支持多源获取和优雅降级。

Data Sources:
1. Primary: 中国理财网 (chinawealth.com.cn) - 官方数据
2. Fallback: 天天基金 (fund.eastmoney.com/lc/) - 东财理财数据
3. Mock: Simulated data for graceful degradation

Fields:
- product_code: 产品代码
- product_name: 产品名称
- yield_rate: 预期收益率(%)
- risk_level: 风险等级(PR1-PR5)
- duration: 产品期限(天)
- issuer: 发行机构
- min_amount: 起购金额(元)
"""
import asyncio
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from backend.schemas.wmp import WMPItem

logger = logging.getLogger(__name__)


# ==================== Base Adapter ====================

class WMPSourceAdapter(ABC):
    """Abstract base class for WMP data sources."""
    
    @abstractmethod
    async def fetch(self, endpoint: str, params: Optional[dict] = None) -> Any:
        """
        Fetch data from the source.
        
        Args:
            endpoint: Data endpoint to fetch
            params: Optional parameters
            
        Returns:
            Fetched data (typically list of WMPItem dicts)
        """
        pass
    
    def supports(self, endpoint: str) -> bool:
        """Check if this source supports the given endpoint."""
        return endpoint in ["wmp_list", "wmp_filter"]


# ==================== ChinaWealth Source (Primary) ====================

class ChinaWealthSource(WMPSourceAdapter):
    """
    中国理财网数据源 - 银保监会官方数据.
    
    API: http://www.chinawealth.com.cn/zzlc/jsp/lccp/lccp.jsp
    Note: 官方网站数据，需要解析HTML或使用API
    """
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.base_url = "http://www.chinawealth.com.cn"
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json, text/html",
                }
            )
        return self._client
    
    async def fetch(self, endpoint: str, params: Optional[dict] = None) -> List[dict]:
        """
        Fetch WMP data from ChinaWealth.
        
        Note: 实际实现需要解析HTML或调用真实API
        此处返回模拟数据用于演示
        """
        logger.info(f"ChinaWealth: Fetching {endpoint}")
        
        try:
            # 实际生产环境需要真实API调用
            # 这里模拟返回数据，实际应该调用真实接口
            # client = await self._get_client()
            # response = await client.get(f"{self.base_url}/api/wmp/list")
            
            # 模拟延迟
            await asyncio.sleep(0.1)
            
            # 返回模拟数据
            return self._generate_mock_data(100)
            
        except Exception as e:
            logger.warning(f"ChinaWealth fetch failed: {e}")
            raise
    
    def _generate_mock_data(self, count: int) -> List[dict]:
        """Generate mock WMP data for testing."""
        banks = ["工商银行", "建设银行", "农业银行", "中国银行", "交通银行",
                 "招商银行", "浦发银行", "民生银行", "兴业银行", "中信银行"]
        risk_levels = ["PR1", "PR2", "PR3", "PR4", "PR5"]
        product_types = ["固定收益类", "混合类", "权益类", "商品及金融衍生品类"]
        
        products = []
        for i in range(count):
            bank = random.choice(banks)
            risk = random.choice(risk_levels)
            
            # 风险等级越高，收益率越高
            base_yield = 2.0 + risk_levels.index(risk) * 0.8
            yield_rate = round(base_yield + random.uniform(-0.5, 1.0), 2)
            
            # 期限通常在30天到365天
            duration = random.choice([30, 60, 90, 120, 180, 270, 365, 540, 730])
            
            # 起购金额
            min_amount = random.choice([1, 5, 10, 20, 50, 100]) * 10000
            
            products.append({
                "product_code": f"LC{datetime.now().year}{str(i+1).zfill(6)}",
                "product_name": f"{bank}理财{random.choice(['稳利', '尊享', '优选', '添利'])}{i+1}号",
                "yield_rate": yield_rate,
                "risk_level": risk,
                "duration": duration,
                "issuer": bank,
                "min_amount": min_amount,
                "product_type": random.choice(product_types),
                "currency": "CNY",
                "issue_date": (datetime.now() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"),
                "maturity_date": (datetime.now() + timedelta(days=duration)).strftime("%Y-%m-%d"),
                "is_active": random.random() > 0.2,
            })
        
        return products


# ==================== Eastmoney WMP Source (Fallback) ====================

class EastmoneyWMPSource(WMPSourceAdapter):
    """
    天天基金理财数据源 - 东财理财产品.
    
    API: https://fund.eastmoney.com/lc/
    """
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.base_url = "https://fund.eastmoney.com"
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
                    "Referer": "https://fund.eastmoney.com/",
                }
            )
        return self._client
    
    async def fetch(self, endpoint: str, params: Optional[dict] = None) -> List[dict]:
        """
        Fetch WMP data from Eastmoney.
        
        Note: 实际实现需要解析HTML或调用真实API
        """
        logger.info(f"EastmoneyWMP: Fetching {endpoint}")
        
        try:
            # 模拟API调用
            await asyncio.sleep(0.15)
            
            # 返回模拟数据
            return self._generate_mock_data(80)
            
        except Exception as e:
            logger.warning(f"EastmoneyWMP fetch failed: {e}")
            raise
    
    def _generate_mock_data(self, count: int) -> List[dict]:
        """Generate mock WMP data for testing."""
        banks = ["工商银行", "建设银行", "农业银行", "中国银行", "交通银行",
                 "招商银行", "浦发银行", "民生银行", "兴业银行", "中信银行",
                 "光大银行", "平安银行", "华夏银行", "广发银行", "邮储银行"]
        risk_levels = ["PR1", "PR2", "PR3", "PR4", "PR5"]
        product_types = ["固定收益类", "混合类", "权益类"]
        
        products = []
        for i in range(count):
            bank = random.choice(banks)
            risk = random.choice(risk_levels)
            
            base_yield = 2.5 + risk_levels.index(risk) * 0.7
            yield_rate = round(base_yield + random.uniform(-0.3, 0.8), 2)
            duration = random.choice([30, 60, 90, 120, 180, 270, 365])
            min_amount = random.choice([1, 5, 10, 20, 50]) * 10000
            
            products.append({
                "product_code": f"EM{datetime.now().year}{str(i+1).zfill(6)}",
                "product_name": f"{bank}{random.choice(['天天', '周周', '月月', '季度'])}盈{i+1}",
                "yield_rate": yield_rate,
                "risk_level": risk,
                "duration": duration,
                "issuer": bank,
                "min_amount": min_amount,
                "product_type": random.choice(product_types),
                "currency": "CNY",
                "issue_date": (datetime.now() - timedelta(days=random.randint(1, 20))).strftime("%Y-%m-%d"),
                "maturity_date": (datetime.now() + timedelta(days=duration)).strftime("%Y-%m-%d"),
                "is_active": True,
            })
        
        return products


# ==================== Mock WMP Source (Graceful Degradation) ====================

class MockWMPSource(WMPSourceAdapter):
    """
    Mock WMP data source for graceful degradation.
    
    Used when all real sources fail.
    """
    
    async def fetch(self, endpoint: str, params: Optional[dict] = None) -> List[dict]:
        """Generate mock WMP data."""
        logger.info(f"MockWMP: Generating data for {endpoint}")
        
        # Simulate minimal delay
        await asyncio.sleep(0.05)
        
        return self._generate_mock_data(50)
    
    def _generate_mock_data(self, count: int) -> List[dict]:
        """Generate realistic mock WMP data."""
        banks = ["工商银行", "建设银行", "农业银行", "中国银行", "交通银行", "招商银行"]
        risk_levels = ["PR1", "PR2", "PR3"]
        product_types = ["固定收益类", "混合类"]
        
        products = []
        for i in range(count):
            bank = random.choice(banks)
            risk = random.choice(risk_levels)
            
            yield_rate = round(2.0 + risk_levels.index(risk) * 0.6 + random.uniform(0, 0.5), 2)
            duration = random.choice([90, 180, 270, 365])
            min_amount = random.choice([1, 5, 10]) * 10000
            
            products.append({
                "product_code": f"MOCK{str(i+1).zfill(8)}",
                "product_name": f"模拟理财产品{i+1}号",
                "yield_rate": yield_rate,
                "risk_level": risk,
                "duration": duration,
                "issuer": bank,
                "min_amount": min_amount,
                "product_type": random.choice(product_types),
                "currency": "CNY",
                "issue_date": datetime.now().strftime("%Y-%m-%d"),
                "maturity_date": (datetime.now() + timedelta(days=duration)).strftime("%Y-%m-%d"),
                "is_active": True,
            })
        
        return products


# ==================== WMP Gateway ====================

class WMPDataGateway:
    """
    WMP data gateway with multi-source failover.
    
    Similar to MarketDataGateway, but specialized for WMP data.
    
    Example:
        gateway = WMPDataGateway()
        gateway.register_source("chinawealth", ChinaWealthSource(), priority=1)
        gateway.register_source("eastmoney", EastmoneyWMPSource(), priority=2)
        gateway.register_source("mock", MockWMPSource(), priority=99)
        
        result = await gateway.fetch_wmp_list()
    """
    
    def __init__(self):
        self._sources: Dict[str, tuple] = {}  # name -> (adapter, priority)
    
    def register_source(self, name: str, adapter: WMPSourceAdapter, priority: int = 1) -> None:
        """
        Register a data source.
        
        Args:
            name: Source name
            adapter: Source adapter instance
            priority: Lower number = higher priority (tried first)
        """
        self._sources[name] = (adapter, priority)
        logger.info(f"Registered WMP source '{name}' with priority {priority}")
    
    def _get_ordered_sources(self) -> List[tuple]:
        """Get sources sorted by priority."""
        return sorted(
            [(name, adapter) for name, (adapter, _) in self._sources.items()],
            key=lambda x: self._sources[x[0]][1]
        )
    
    async def fetch_wmp_list(self, preferred_source: Optional[str] = None) -> tuple:
        """
        Fetch WMP list with automatic failover.
        
        Args:
            preferred_source: Try this source first (optional)
            
        Returns:
            Tuple of (data_list, source_name, fallback_chain)
        """
        fallback_chain = []
        
        # Get ordered sources
        sources = self._get_ordered_sources()
        
        # Move preferred source to front if specified
        if preferred_source:
            sources = [
                (n, a) for n, a in sources if n == preferred_source
            ] + [
                (n, a) for n, a in sources if n != preferred_source
            ]
        
        # Try each source in order
        for source_name, adapter in sources:
            fallback_chain.append(source_name)
            
            try:
                data = await adapter.fetch("wmp_list")
                
                if data:
                    logger.info(f"Successfully fetched WMP data from '{source_name}'")
                    return data, source_name, fallback_chain
                    
            except Exception as e:
                logger.warning(f"Source '{source_name}' failed: {e}")
                continue
        
        # All sources failed
        logger.error("All WMP sources failed")
        return [], None, fallback_chain


# ==================== Singleton Gateway ====================

# Global WMP gateway instance
wmp_gateway = WMPDataGateway()


def init_wmp_gateway() -> None:
    """
    Initialize WMP gateway with default sources.
    
    Called during application startup.
    """
    # Register primary source
    wmp_gateway.register_source(
        "chinawealth",
        ChinaWealthSource(timeout=10.0),
        priority=1
    )
    
    # Register fallback source
    wmp_gateway.register_source(
        "eastmoney",
        EastmoneyWMPSource(timeout=10.0),
        priority=2
    )
    
    # Register mock source for graceful degradation
    wmp_gateway.register_source(
        "mock",
        MockWMPSource(),
        priority=99
    )
    
    logger.info("WMP gateway initialized with 3 sources")
