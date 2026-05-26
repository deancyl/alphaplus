"""
Pydantic schemas for API request/response validation.
"""
from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field


# ==================== Fund Filter Schemas ====================

class FundFilterRequest(BaseModel):
    """基金筛选请求 - 5-dimension cascade conditions."""
    # Basic Info
    fund_types: Optional[List[str]] = Field(default=None, description="基金类型列表 (25类)")
    setup_year_min: Optional[float] = Field(default=None, ge=0, description="成立年限最小值")
    setup_year_max: Optional[float] = Field(default=None, ge=0, description="成立年限最大值")
    scale_min: Optional[float] = Field(default=None, ge=0, description="规模最小值 (亿元)")
    scale_max: Optional[float] = Field(default=None, ge=0, description="规模最大值 (亿元)")
    company_names: Optional[List[str]] = Field(default=None, description="基金公司列表")
    
    # Holdings
    heavy_stocks: Optional[List[str]] = Field(default=None, description="重仓股票代码")
    heavy_bonds: Optional[List[str]] = Field(default=None, description="重仓债券代码")
    stock_position_min: Optional[float] = Field(default=None, ge=0, le=100, description="股票仓位最小值%")
    stock_position_max: Optional[float] = Field(default=None, ge=0, le=100, description="股票仓位最大值%")
    
    # Sector/Industry
    sw_level1: Optional[List[str]] = Field(default=None, description="申万一级行业")
    sw_level2: Optional[List[str]] = Field(default=None, description="申万二级行业")
    
    # Performance
    return_1y_min: Optional[float] = Field(default=None, description="近1年收益率最小值%")
    return_1y_max: Optional[float] = Field(default=None, description="近1年收益率最大值%")
    max_drawdown_1y_max: Optional[float] = Field(default=None, description="近1年最大回撤最大值%")
    sharpe_1y_min: Optional[float] = Field(default=None, description="近1年夏普最小值")
    
    # Manager Style
    manager_experience_min: Optional[float] = Field(default=None, description="经理从业年限最小值")
    turnover_rate_max: Optional[float] = Field(default=None, description="换手率最大值%")
    institution_holding_min: Optional[float] = Field(default=None, description="机构持仓占比最小值%")
    
    # Pagination
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=50, ge=1, le=200, description="每页数量")
    
    # Sort
    sort_by: Optional[str] = Field(default="return_1y", description="排序字段")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="排序方向")


class FundIndicatorResponse(BaseModel):
    """基金指标响应."""
    fund_code: str
    fund_name: str
    fund_type: str
    manager: Optional[str] = None
    setup_date: Optional[str] = None
    setup_year: Optional[float] = None
    scale: Optional[float] = None
    company_name: Optional[str] = None
    return_1y: Optional[float] = None
    volatility_1y: Optional[float] = None
    max_drawdown_1y: Optional[float] = None
    sharpe_1y: Optional[float] = None
    heavy_sector: Optional[str] = None


class FundFilterResponse(BaseModel):
    """基金筛选响应."""
    total: int
    page: int
    page_size: int
    funds: List[FundIndicatorResponse]


# ==================== Fund Compare Schemas ====================

class FundCompareRequest(BaseModel):
    """基金对比请求 - 最多15只."""
    fund_codes: List[str] = Field(..., min_length=1, max_length=15, description="基金代码列表")
    benchmark: str = Field(default="000300", description="基准指数代码 (默认沪深300)")
    start_date: Optional[str] = Field(default=None, description="开始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(default=None, description="结束日期 YYYY-MM-DD")


class CorrelationMatrixResponse(BaseModel):
    """相关性矩阵响应."""
    fund_codes: List[str]
    correlation_matrix: List[List[float]]  # N x N Pearson correlation
    calculation_date: str = Field(..., description="计算日期 YYYY-MM-DD")
    sample_size: int = Field(..., description="样本数量 (交易日数)")
    data_quality: Optional[dict] = Field(default=None, description="数据质量信息")


class FactorExposureResponse(BaseModel):
    """因子暴露响应 - 14 coefficients."""
    fund_code: str
    # 6 style factors
    large_cap_value: float
    large_cap_growth: float
    mid_cap_value: float
    mid_cap_growth: float
    small_cap_value: float
    small_cap_growth: float
    # 8 sector factors
    consumer: float
    tmt: float
    manufacturing: float
    healthcare: float
    cyclical: float
    utilities: float
    conglomerate: float
    cash: float
    intercept: float


# ==================== Market Overview Schemas ====================

class IndexQuoteResponse(BaseModel):
    """指数行情响应."""
    code: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: Optional[float]
    amount: Optional[float]


class FearGreedResponse(BaseModel):
    """恐惧贪婪指数响应."""
    trade_date: str
    composite_score: float
    sentiment_status: str
    factor_volatility: Optional[float]
    factor_safe_haven: Optional[float]
    factor_margin_ratio: Optional[float]
    factor_volume_deviation: Optional[float]
    factor_futures_basis: Optional[float]
    factor_stock_strength: Optional[float]


class ERPSpreadResponse(BaseModel):
    """股债ERP响应."""
    index_code: str
    index_name: str
    trade_date: str
    pe_ttm: float
    treasury_yield_10y: float
    erp_spread: float
    percentile_rank_10y: Optional[float]
    index_close_price: Optional[float]


class TrajectoryPoint(BaseModel):
    """Phase space trajectory point."""
    x: float = Field(..., description="Crowding score (0-100)")
    y: float = Field(..., description="PE percentile (0-100)")
    date: str = Field(..., description="Date YYYY-MM-DD")


class TrajectoryVector(BaseModel):
    """Enhanced trajectory vector with velocity and rotation."""
    asset: str = Field(..., description="Asset code/name")
    start: TrajectoryPoint = Field(..., description="Start point T₀")
    end: TrajectoryPoint = Field(..., description="End point T₁")
    velocity: float = Field(..., description="Average velocity (crowding change per day)")
    rotation: str = Field(..., description="Rotation classification: clockwise/counter_clockwise/neutral/expansion/contraction")
    magnitude: Optional[float] = Field(None, description="Trajectory magnitude")
    direction_deg: Optional[float] = Field(None, description="Direction in degrees")


class TrajectoryResponse(BaseModel):
    """Phase space trajectory response for ECharts visualization."""
    vectors: List[TrajectoryVector] = Field(..., description="List of trajectory vectors")
    regime_change: bool = Field(..., description="Whether regime change detected")
    regime_change_count: Optional[int] = Field(None, description="Number of regime changes")


class CrowdingRotationVector(BaseModel):
    """拥挤度旋转向量 - Legacy format for backward compatibility."""
    asset_code: str
    asset_name: str
    t0_date: str
    t1_date: str
    t0_crowding: float
    t1_crowding: float
    t0_pe_percentile: float
    t1_pe_percentile: float


# ==================== Bond Market Schemas ====================

class YieldCurveResponse(BaseModel):
    """收益率曲线响应."""
    bond_type: str
    trade_date: str
    curve: List[dict]  # [{tenor: 1, yield: 2.5}, ...]


class CreditSpreadResponse(BaseModel):
    """信用利差响应."""
    bond_category: str
    rating: str
    tenor: str
    trade_date: str
    yield_ytm: float
    credit_spread: float
    percentile_rank: float


# ==================== Heatmap Matrix Schemas ====================

class HeatmapCell(BaseModel):
    """热力图单元格."""
    row: str  # 行标签 (如指数名)
    col: str  # 列标签 (如时间周期)
    value: float  # 数值
    color: str  # 颜色 rgba


class HeatmapMatrixResponse(BaseModel):
    """热力矩阵响应."""
    rows: List[str]
    cols: List[str]
    cells: List[HeatmapCell]


# ==================== Dashboard Aggregation Schemas ====================

class DashboardDataQuality(BaseModel):
    """Dashboard data quality indicator."""
    partial: bool = Field(..., description="Whether any sub-call failed")
    errors: Optional[dict] = Field(default=None, description="Error messages per metric")


class DashboardResponse(BaseModel):
    """首页看板聚合响应 - 恐惧贪婪、ERP、风格强度、拥挤度."""
    fear_greed: List[dict] = Field(default_factory=list, description="恐惧贪婪指数历史")
    erp: List[dict] = Field(default_factory=list, description="股债ERP历史")
    style_strength: List[dict] = Field(default_factory=list, description="风格强度历史")
    crowding: List[dict] = Field(default_factory=list, description="拥挤度分析历史")
    timestamp: str = Field(..., description="响应时间戳")
    data_quality: DashboardDataQuality = Field(..., description="数据质量信息")


# ==================== Fund Similarity Schemas ====================

class SimilarFund(BaseModel):
    """相似基金."""
    fund_code: str
    fund_name: str
    similarity: float = Field(..., description="Similarity score (0-1, higher is more similar)")


class FactorExposureItem(BaseModel):
    """因子暴露项."""
    factor_name: str
    factor_type: str = Field(..., description="style or sector")
    weight: float


class FundSimilarityResponse(BaseModel):
    """基金相似度响应."""
    fund_code: str
    similar_funds: List[SimilarFund] = Field(..., description="Top N similar funds")
    factor_exposure: List[FactorExposureItem] = Field(..., description="Factor exposure of input fund")
    calculation_method: str = Field(default="euclidean", description="Distance calculation method")
    elapsed_ms: Optional[float] = Field(None, description="Calculation time in milliseconds")


# ==================== AIP Calculator Schemas ====================

class AIPCalculateRequest(BaseModel):
    """定投计算请求."""
    fund_code: str = Field(..., description="基金代码")
    frequency: str = Field(..., pattern="^(weekly|biweekly|monthly)$", description="定投频率: weekly/biweekly/monthly")
    amount: float = Field(..., gt=0, description="每期投资金额(元)")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(default=None, description="结束日期 YYYY-MM-DD, 默认今天")


class AIPCalculateResponse(BaseModel):
    """定投计算响应."""
    fund_code: str
    fund_name: str
    frequency: str
    amount: float
    total_investment: float = Field(..., description="累计投资金额")
    current_value: float = Field(..., description="当前市值")
    return_rate: float = Field(..., description="收益率(%)")
    max_drawdown: float = Field(..., description="最大回撤(%)")
    volatility: float = Field(..., description="年化波动率(%)")
    periods: int = Field(..., description="投资期数")
    units_total: float = Field(..., description="累计份额")
    lump_sum_comparison: dict = Field(..., description="一次性投资对比 {value, return_rate}")
    investment_dates: List[str] = Field(..., description="投资日期列表")
    nav_history: List[dict] = Field(..., description="净值历史 [{date, nav, units, value, cumulative_return}]")
