"""
Market schemas for index valuation API endpoints.
"""
from typing import List
from pydantic import BaseModel, Field


class IndexValuationItem(BaseModel):
    """Single index valuation data."""
    index_code: str = Field(..., description="指数代码")
    index_name: str = Field(..., description="指数名称")
    pe_ttm: float = Field(..., description="市盈率TTM")
    pb: float = Field(..., description="市净率")
    dividend_yield: float = Field(..., description="股息率%")
    pe_percentile: float = Field(..., description="PE百分位 (0-100)")
    pb_percentile: float = Field(..., description="PB百分位 (0-100)")
    zone: str = Field(..., description="估值区间: 低估/正常/高估")
    is_simulated: bool = Field(..., description="是否为模拟数据")


class IndexValuationResponse(BaseModel):
    """Response for all indices valuation."""
    items: List[IndexValuationItem] = Field(..., description="指数估值列表")
    total: int = Field(..., description="总数")
    timestamp: str = Field(..., description="时间戳")


class IndexPEHistoryItem(BaseModel):
    """Single PE history data point."""
    date: str = Field(..., description="日期")
    pe: float = Field(..., description="PE值")
    percentile: float = Field(..., description="百分位")


class IndexPEHistoryResponse(BaseModel):
    """Response for index PE history."""
    index_code: str = Field(..., description="指数代码")
    index_name: str = Field(..., description="指数名称")
    history: List[IndexPEHistoryItem] = Field(..., description="PE历史数据")
