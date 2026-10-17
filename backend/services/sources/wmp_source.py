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
from backend.core.config import settings

logger = logging.getLogger(__name__)


class UnavailableSource(RuntimeError):
    """Raised by an adapter whose upstream is not wired.

    Distinct from a transport failure: it means "this project has no live
    integration for that source yet", so the gateway must not treat it as a
    transient error worth retrying, and must never substitute generated rows.
    """


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

    NOTE: the public site exposes no stable machine-readable endpoint that this
    adapter can rely on (the listing is a POST-form HTML page behind a session
    cookie).  Until that integration exists this source declares itself
    unavailable rather than returning generated rows — the previous
    implementation returned ``_generate_mock_data()``, i.e. random bank names,
    random yields and random maturity dates, which is fabricated market data.
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
        """Raise ``UnavailableSource`` — no live WMP upstream is wired yet."""
        logger.info("ChinaWealth: no live endpoint wired for %s", endpoint)
        raise UnavailableSource("chinawealth_no_live_endpoint")


# ==================== Eastmoney WMP Source (Fallback) ====================

class EastmoneyWMPSource(WMPSourceAdapter):
    """
    天天基金理财数据源 - 东财理财产品.

    API: https://fund.eastmoney.com/lc/

    Like ChinaWealth, the listing is an HTML page without a documented stable
    JSON endpoint, so this source reports unavailable instead of generating
    random products.
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
        """Raise ``UnavailableSource`` — no live WMP upstream is wired yet."""
        logger.info("EastmoneyWMP: no live endpoint wired for %s", endpoint)
        raise UnavailableSource("eastmoney_no_live_endpoint")


# ==================== Mock WMP Source (Graceful Degradation) ====================

class MockWMPSource(WMPSourceAdapter):
    """
    Reference-data source for explicit degradation only.

    This adapter generates rows that are *not* real products.  It is therefore
    registered but only consulted when ``settings.allow_simulated_fallback`` is
    explicitly enabled, and every row is tagged ``is_simulated=True`` so a
    caller can never mistake it for live data.
    """

    async def fetch(self, endpoint: str, params: Optional[dict] = None) -> List[dict]:
        """Generate clearly-tagged reference rows."""
        logger.info(f"MockWMP: Generating tagged reference data for {endpoint}")

        # Simulate minimal delay
        await asyncio.sleep(0.05)

        return self._generate_mock_data(50)

    def _generate_mock_data(self, count: int) -> List[dict]:
        """Generate reference WMP rows, tagged so they cannot be mistaken live."""
        banks = ["工商银行", "建设银行", "农业银行", "中国银行", "交通银行", "招商银行"]
        risk_levels = ["PR1", "PR2", "PR3"]

        products = []
        for i in range(count):
            bank = random.choice(banks)
            risk = random.choice(risk_levels)

            yield_rate = round(2.0 + risk_levels.index(risk) * 0.6 + random.uniform(0, 0.5), 2)
            duration = random.choice([90, 180, 270, 365])
            min_amount = random.choice([1, 5, 10]) * 10000

            products.append({
                "product_code": f"SIMULATED{str(i+1).zfill(8)}",
                "product_name": f"模拟参考理财产品{i+1}号",
                "yield_rate": yield_rate,
                "risk_level": risk,
                "duration": duration,
                "issuer": bank,
                "min_amount": min_amount,
                "product_type": "固定收益类",
                "currency": "CNY",
                "issue_date": datetime.now().strftime("%Y-%m-%d"),
                "maturity_date": (datetime.now() + timedelta(days=duration)).strftime("%Y-%m-%d"),
                "is_active": True,
                "is_simulated": True,
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
            # The reference adapter is only consulted when the operator has
            # explicitly opted into simulated fallbacks.  With the default
            # policy it is skipped entirely, so a "no live source" outcome stays
            # an honest empty result instead of generated products.
            if source_name == "mock" and not settings.allow_simulated_fallback:
                continue

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
