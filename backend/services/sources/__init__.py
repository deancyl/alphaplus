"""
Source adapters for market data.
"""
from .akshare_source import AkshareSource
from .eastmoney_source import EastmoneySource
from .sina_source import SinaSource

__all__ = ["AkshareSource", "EastmoneySource", "SinaSource"]
