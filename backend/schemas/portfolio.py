"""
Pydantic schemas for portfolio API request/response validation.
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, Field, field_validator


# ==================== Fund Allocation Schemas ====================

class FundAllocation(BaseModel):
    """基金配置项."""
    fund_code: str = Field(..., description="基金代码")
    weight: float = Field(..., gt=0, le=1, description="权重 (0-1)")

    @field_validator('weight')
    @classmethod
    def validate_weight(cls, v):
        if v <= 0 or v > 1:
            raise ValueError("权重必须在 0-1 之间")
        return v


# ==================== Portfolio CRUD Schemas ====================

class PortfolioCreate(BaseModel):
    """创建组合请求."""
    name: str = Field(..., min_length=1, max_length=100, description="组合名称")
    description: Optional[str] = Field(None, description="组合描述")
    funds: List[FundAllocation] = Field(..., min_length=1, description="基金配置列表")

    @field_validator('funds')
    @classmethod
    def validate_funds(cls, v):
        # Check total weight
        total_weight = sum(f.weight for f in v)
        if abs(total_weight - 1.0) > 0.01:  # Allow 1% deviation
            # Auto-normalize weights
            for fund in v:
                fund.weight = fund.weight / total_weight
        return v


class PortfolioUpdate(BaseModel):
    """更新组合请求."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    funds: Optional[List[FundAllocation]] = None

    @field_validator('funds')
    @classmethod
    def validate_funds(cls, v):
        if v is not None:
            total_weight = sum(f.weight for f in v)
            if abs(total_weight - 1.0) > 0.01:
                for fund in v:
                    fund.weight = fund.weight / total_weight
        return v


class PortfolioResponse(BaseModel):
    """组合响应."""
    id: int
    name: str
    description: Optional[str] = None
    funds: List[FundAllocation]
    created_at: datetime
    updated_at: datetime


class PortfolioListResponse(BaseModel):
    """组合列表响应."""
    total: int
    portfolios: List[PortfolioResponse]


# ==================== Backtest Request/Response Schemas ====================

class BacktestRequest(BaseModel):
    """回测请求."""
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="结束日期 YYYY-MM-DD")
    benchmark: str = Field(default="000300", description="基准指数代码 (默认沪深300)")
    linking_method: Literal["auto", "carino", "menchero"] = Field(
        default="auto",
        description="多期Brinson归因链接方法: auto(自动选择), carino, menchero"
    )
    period_granularity: Literal["daily", "weekly", "monthly"] = Field(
        default="monthly",
        description="期间粒度: daily(日度), weekly(周度), monthly(月度)"
    )


class DailyReturn(BaseModel):
    """日收益数据."""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    return_pct: float = Field(..., description="收益率 (%)")
    nav: float = Field(..., description="单位净值")


class BacktestStatistics(BaseModel):
    """回测统计指标."""
    total_return: float = Field(..., description="总收益率 (%)")
    annual_return: float = Field(..., description="年化收益率 (%)")
    max_drawdown: float = Field(..., description="最大回撤 (%)")
    sharpe_ratio: float = Field(..., description="夏普比率")
    volatility: float = Field(..., description="年化波动率 (%)")
    sortino_ratio: Optional[float] = Field(None, description="索提诺比率")
    calmar_ratio: Optional[float] = Field(None, description="卡尔玛比率")


class BrinsonAttribution(BaseModel):
    """Brinson归因结果 (单期)."""
    allocation_effect: float = Field(..., description="配置效应 (%)")
    selection_effect: float = Field(..., description="选择效应 (%)")
    interaction_effect: float = Field(..., description="交互效应 (%)")
    total_effect: float = Field(..., description="总效应 (%)")


class PeriodAttribution(BaseModel):
    """单期归因明细."""
    period_start: date = Field(..., description="期间开始日期")
    period_end: date = Field(..., description="期间结束日期")
    allocation_effect: float = Field(..., description="配置效应 (%)")
    selection_effect: float = Field(..., description="选择效应 (%)")
    interaction_effect: float = Field(..., description="交互效应 (%)")
    linking_coefficient: float = Field(..., description="链接系数 k_t")
    portfolio_return: float = Field(..., description="组合收益率 (%)")
    benchmark_return: float = Field(..., description="基准收益率 (%)")
    excess_return: float = Field(..., description="超额收益率 (%)")


class MultiPeriodBrinsonAttribution(BaseModel):
    """多期Brinson归因结果."""
    method: str = Field(..., description="链接方法: carino 或 menchero")
    allocation_effect: float = Field(..., description="累计配置效应 (%)")
    selection_effect: float = Field(..., description="累计选择效应 (%)")
    interaction_effect: float = Field(..., description="累计交互效应 (%)")
    total_effect: float = Field(..., description="累计总效应 (%)")
    residual: float = Field(..., description="残差 (应 < 1e-12)")
    portfolio_compound_return: float = Field(..., description="组合复合收益率 (%)")
    benchmark_compound_return: float = Field(..., description="基准复合收益率 (%)")
    excess_return: float = Field(..., description="复合超额收益率 (%)")
    periods: List[PeriodAttribution] = Field(..., description="各期归因明细")


class BacktestResultResponse(BaseModel):
    """回测结果响应."""
    id: int
    portfolio_id: int
    start_date: str
    end_date: str
    portfolio_returns: List[DailyReturn]
    benchmark_returns: Optional[List[DailyReturn]] = None
    statistics: BacktestStatistics
    brinson_attribution: Optional[BrinsonAttribution] = None
    multi_period_brinson_attribution: Optional[MultiPeriodBrinsonAttribution] = None
    created_at: datetime


class BacktestListResponse(BaseModel):
    """回测结果列表响应."""
    total: int
    results: List[BacktestResultResponse]


# ==================== Backtest Detail Response ====================

class BacktestDetailResponse(BaseModel):
    """回测详情响应 (包含完整数据)."""
    portfolio: PortfolioResponse
    result: BacktestResultResponse
    fund_performance: Optional[List[Dict]] = Field(None, description="各基金表现明细")