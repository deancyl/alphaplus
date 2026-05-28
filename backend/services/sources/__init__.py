"""
Source adapters for market data.
"""
from .adata_client import ADataClient
from .akshare_source import AkshareSource
from .eastmoney_source import EastmoneySource
from .sina_source import SinaSource
from .wmp_source import (
    WMPSourceAdapter,
    ChinaWealthSource,
    EastmoneyWMPSource,
    MockWMPSource,
    WMPDataGateway,
    wmp_gateway,
    init_wmp_gateway,
)

__all__ = [
    "ADataClient",
    "AkshareSource",
    "EastmoneySource",
    "SinaSource",
    "WMPSourceAdapter",
    "ChinaWealthSource",
    "EastmoneyWMPSource",
    "MockWMPSource",
    "WMPDataGateway",
    "wmp_gateway",
    "init_wmp_gateway",
]
