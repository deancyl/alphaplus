"""
Pydantic schemas for Wealth Management Product (WMP) API.

银行理财产品筛选相关数据结构定义。
"""
from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field


# ==================== WMP Item Schemas ====================

class WMPItem(BaseModel):
    """理财产品数据项."""
    product_code: str = Field(..., description="产品代码")
    product_name: str = Field(..., description="产品名称")
    yield_rate: Optional[float] = Field(None, description="预期收益率(%)")
    risk_level: str = Field(..., description="风险等级: PR1/PR2/PR3/PR4/PR5")
    duration: Optional[int] = Field(None, description="产品期限(天)")
    issuer: str = Field(..., description="发行机构(银行)")
    min_amount: Optional[float] = Field(None, description="起购金额(元)")
    product_type: Optional[str] = Field(None, description="产品类型: 固定收益类/权益类/混合类/商品及金融衍生品类")
    currency: Optional[str] = Field(None, description="币种: CNY/USD等")
    issue_date: Optional[str] = Field(None, description="发行日期 YYYY-MM-DD")
    maturity_date: Optional[str] = Field(None, description="到期日期 YYYY-MM-DD")
    is_active: bool = Field(default=True, description="是否在售")


# ==================== WMP Filter Schemas ====================

class WMPFilterParams(BaseModel):
    """理财产品筛选参数."""
    # 收益率筛选
    yield_min: Optional[float] = Field(None, description="预期收益率最小值(%)")
    yield_max: Optional[float] = Field(None, description="预期收益率最大值(%)")
    
    # 风险等级筛选
    risk_levels: Optional[List[str]] = Field(
        None, 
        description="风险等级列表: PR1/PR2/PR3/PR4/PR5"
    )
    
    # 期限筛选
    duration_min: Optional[int] = Field(None, description="产品期限最小值(天)")
    duration_max: Optional[int] = Field(None, description="产品期限最大值(天)")
    
    # 发行机构筛选
    issuer: Optional[str] = Field(None, description="发行机构名称(模糊匹配)")
    issuers: Optional[List[str]] = Field(None, description="发行机构列表(精确匹配)")
    
    # 起购金额筛选
    min_amount_max: Optional[float] = Field(None, description="起购金额最大值(元)")
    
    # 产品类型筛选
    product_types: Optional[List[str]] = Field(None, description="产品类型列表")
    
    # 币种筛选
    currency: Optional[str] = Field(None, description="币种: CNY/USD等")
    
    # 在售状态
    is_active: Optional[bool] = Field(None, description="是否仅筛选在售产品")
    
    # 分页参数
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=50, ge=1, le=200, description="每页数量")
    
    # 排序参数
    sort_by: Optional[str] = Field(
        default="yield_rate", 
        description="排序字段: yield_rate/duration/min_amount"
    )
    sort_order: str = Field(
        default="desc", 
        pattern="^(asc|desc)$", 
        description="排序方向"
    )


class WMPFilterResponse(BaseModel):
    """理财产品筛选响应."""
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    products: List[WMPItem] = Field(..., description="产品列表")
    data_source: Optional[str] = Field(None, description="数据来源")
    fallback_chain: Optional[List[str]] = Field(None, description="尝试的数据源列表")
    timestamp: str = Field(..., description="响应时间戳")


# ==================== WMP Statistics Schemas ====================

class WMPStatistics(BaseModel):
    """理财产品统计信息."""
    total_count: int = Field(..., description="产品总数")
    avg_yield: Optional[float] = Field(None, description="平均收益率(%)")
    yield_range: Optional[dict] = Field(None, description="收益率范围 {min, max}")
    risk_distribution: Optional[dict] = Field(None, description="风险等级分布 {PR1: count, ...}")
    duration_distribution: Optional[dict] = Field(None, description="期限分布")
    issuer_count: int = Field(..., description="发行机构数量")


class WMPStatisticsResponse(BaseModel):
    """理财产品统计响应."""
    statistics: WMPStatistics
    timestamp: str = Field(..., description="响应时间戳")
