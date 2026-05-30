"""
SQLAlchemy models for all database tables.
Based on PRD Chapter 4 - High-performance local database physical structure design.
"""
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Float, Integer, Text, Date, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base


# ==================== Fund Module Tables ====================

class FundIndicators(Base):
    """公募底层基础宽表 - Primary filter table for fund screening."""
    __tablename__ = "fund_indicators"

    fund_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    fund_name: Mapped[str] = mapped_column(String(100))
    fund_type: Mapped[str] = mapped_column(String(50))  # 25 categories
    manager: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    setup_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    setup_year: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    scale: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 亿元
    company_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Performance metrics
    return_1y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volatility_1y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown_1y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sharpe_1y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    new_high_ratio_1y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 近一年内含新高率 (%)
    heavy_sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Manager honors (awards)
    manager_honors: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # 金牛奖,明星基金奖,招行五星

    __table_args__ = (
        Index("idx_fund_filter", "fund_type", "setup_year", "scale", "return_1y"),
    )


class FundIssuePipeline(Base):
    """基金新发周历管线表 - Weekly issuance calendar."""
    __tablename__ = "fund_issue_pipeline"

    fund_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    fund_name: Mapped[str] = mapped_column(String(100))
    company: Mapped[str] = mapped_column(String(100))
    subscribe_start_date: Mapped[str] = mapped_column(String(10))
    subscribe_end_date: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20))  # 首发/即将发售/成立/退市
    initial_scale: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delist_scale: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class FundCompanyMetadata(Base):
    """基金公司核心属性表."""
    __tablename__ = "fund_company_metadata"

    company_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(100))
    establish_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    total_scale: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 亿元
    non_money_scale: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fund_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    manager_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class FundCompanyDistributionHistory(Base):
    """基金公司分布/持仓长历史时序表 - For 100% stacked charts and Treemap."""
    __tablename__ = "fund_company_distribution_history"

    company_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    dist_type: Mapped[str] = mapped_column(String(50), primary_key=True)  # asset_class/sector/bond_type
    stat_quarter: Mapped[str] = mapped_column(String(10), primary_key=True)  # 2024Q1
    item_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    weight: Mapped[float] = mapped_column(Float)  # 百分比


# ==================== Market Data Tables ====================

class StockQuotesHistory(Base):
    """多市场行情时序表."""
    __tablename__ = "stock_quotes_history"

    stock_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    trade_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    close_price: Mapped[float] = mapped_column(Float)
    margin_balance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class MoneyMarketRates(Base):
    """货币市场利率表 - With sparkline data."""
    __tablename__ = "money_market_rates"

    rate_code: Mapped[str] = mapped_column(String(20), primary_key=True)  # DR007, SHIBOR_3M
    trade_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    rate_value: Mapped[float] = mapped_column(Float)
    sparkline_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array


class BondYieldCurveStructure(Base):
    """债券收益率曲线结构表."""
    __tablename__ = "bond_yield_curve_structure"

    bond_type: Mapped[str] = mapped_column(String(20), primary_key=True)  # 国债/国开/口行/农发/地方
    trade_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    tenor: Mapped[float] = mapped_column(Float, primary_key=True)  # 1, 2, 3, 5, 7, 10, 20, 30 (年)
    yield_ytm: Mapped[float] = mapped_column(Float)


class BondCreditSpreadHistory(Base):
    """信用债利差及历史百分位引擎表."""
    __tablename__ = "bond_credit_spread_history"

    bond_category: Mapped[str] = mapped_column(String(20), primary_key=True)  # 中票/城投/企业债
    rating: Mapped[str] = mapped_column(String(10), primary_key=True)  # AAA/AA+/AA
    tenor: Mapped[str] = mapped_column(String(10), primary_key=True)  # 1Y/3Y/5Y
    trade_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    benchmark_type: Mapped[str] = mapped_column(String(20), primary_key=True)  # 国债/国开
    yield_ytm: Mapped[float] = mapped_column(Float)
    credit_spread: Mapped[float] = mapped_column(Float)  # BP
    percentile_rank: Mapped[float] = mapped_column(Float)  # 0-100


# ==================== Macro Analytics Tables ====================

class MarketFearGreedSentimentHistory(Base):
    """恐惧贪婪指数历史表 - Six-factor decomposition."""
    __tablename__ = "market_fear_greed_sentiment_history"

    trade_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    composite_score: Mapped[float] = mapped_column(Float)  # 0-100
    sentiment_status: Mapped[str] = mapped_column(String(20))  # 极度恐惧/恐惧/中性/贪婪/极度贪婪
    # Six factors (0-100 each)
    factor_volatility: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    factor_safe_haven: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    factor_margin_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    factor_volume_deviation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    factor_futures_basis: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    factor_stock_strength: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class MarketStyleStrengthHistory(Base):
    """市场风格强度历史表 - 大小盘/价值成长相对强弱."""
    __tablename__ = "market_style_strength_history"

    trade_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    index_code_num: Mapped[str] = mapped_column(String(10), primary_key=True)  # 分子指数
    index_code_den: Mapped[str] = mapped_column(String(10), primary_key=True)  # 分母指数
    ratio_value: Mapped[float] = mapped_column(Float)
    percentile_rank_3y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 3年分位数

    __table_args__ = (
        Index("idx_style_strength_date", "trade_date"),
    )


class BondEquityYieldSpreadHistory(Base):
    """股债ERP历史表 - Equity Risk Premium."""
    __tablename__ = "bond_equity_yield_spread_history"

    index_code: Mapped[str] = mapped_column(String(10), primary_key=True)  # 沪深300/中证500
    trade_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    pe_ttm: Mapped[float] = mapped_column(Float)
    treasury_yield_10y: Mapped[float] = mapped_column(Float)
    erp_spread: Mapped[float] = mapped_column(Float)  # = 1/PE - 国债收益率
    moving_mean_10y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    std_dev_1y_10y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    std_dev_2y_10y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    percentile_rank_10y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    index_close_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("idx_erp_index_date", "index_code", "trade_date"),
    )


class IndexValuationHistory(Base):
    """指数估值历史表 - PE百分位."""
    __tablename__ = "index_valuation_history"

    index_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    trade_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    pe_ttm: Mapped[float] = mapped_column(Float)
    percentile_rank_10y: Mapped[float] = mapped_column(Float)
    moving_mean_10y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    index_close_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("idx_valuation_index_date", "index_code", "trade_date"),
    )


class MarketCrowdingValuationHistory(Base):
    """市场拥挤度与估值历史表 - For rotation vector analysis."""
    __tablename__ = "market_crowding_valuation_history"

    asset_code: Mapped[str] = mapped_column(String(20), primary_key=True)  # 板块/行业/指数代码
    trade_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    category: Mapped[str] = mapped_column(String(20), primary_key=True)  # sector/index/style/concept
    crowding_score: Mapped[float] = mapped_column(Float)  # 0-100
    pe_percentile: Mapped[float] = mapped_column(Float)  # 0-100
    close_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("idx_crowding_date", "trade_date"),
        Index("idx_crowding_category_date", "category", "trade_date"),
    )


class BacktestStatsMacroStrategies(Base):
    """宏观策略持有期期望回测矩阵引擎表 - Millisecond-level filtering."""
    __tablename__ = "backtest_stats_macro_strategies"

    index_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    metric_type: Mapped[str] = mapped_column(String(20), primary_key=True)  # fear_greed/erp/crowding
    range_min: Mapped[float] = mapped_column(Float, primary_key=True)
    range_max: Mapped[float] = mapped_column(Float, primary_key=True)
    holding_period: Mapped[str] = mapped_column(String(10), primary_key=True)  # 3M/6M/1Y
    win_probability: Mapped[float] = mapped_column(Float)  # 0-100%
    avg_return: Mapped[float] = mapped_column(Float)  # %


class FundNavHistory(Base):
    """基金净值历史表 - For correlation matrix calculation."""
    __tablename__ = "fund_nav_history"

    fund_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    nav_date: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD
    nav_value: Mapped[float] = mapped_column(Float)  # 单位净值
    daily_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 日收益率%

    __table_args__ = (
        Index("idx_fund_nav", "fund_code", "nav_date"),
    )


class MarketCalendar(Base):
    """多市场周历表 - Multi-market weekly calendar for fund issuance dashboard."""
    __tablename__ = "market_calendar"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_code: Mapped[str] = mapped_column(String(20), nullable=False)  # ASHARE, HK, US
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_trading_day: Mapped[bool] = mapped_column(default=True)
    week_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # ISO week number
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    market_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # A股, 港股, 美股
    holiday_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 春节, 国庆

    __table_args__ = (
        Index("idx_market_date", "market_code", "trade_date"),
    )


# ==================== User Favorites & Fund Pool Tables ====================

class UserFavoritesRegistry(Base):
    """用户收藏注册表 - User favorites for funds, WMPs, stocks, insurance."""
    __tablename__ = "user_favorites_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), default="default", index=True)
    product_type: Mapped[str] = mapped_column(String(20), nullable=False)  # fund, wmp, stock, insurance
    product_code: Mapped[str] = mapped_column(String(20), nullable=False)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # For drag-drop reorder
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "product_type", "product_code", name="uq_user_favorites"),
        Index("idx_user_favorites", "user_id", "product_type"),
    )


class FundPoolRegistry(Base):
    """基金池注册表 - Entry pool, focus pool, exit pool management."""
    __tablename__ = "fund_pool_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pool_type: Mapped[str] = mapped_column(String(20), nullable=False)  # entry, focus, exit
    fund_code: Mapped[str] = mapped_column(String(10), nullable=False)
    fund_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, removed
    added_date: Mapped[date] = mapped_column(Date, default=date.today)
    removed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("pool_type", "fund_code", name="uq_fund_pool"),
        Index("idx_fund_pool", "pool_type", "status"),
    )


class FundPortfolioHoldings(Base):
    """基金持仓明细表 - Fund portfolio stock holdings details."""
    __tablename__ = "fund_portfolio_holdings"

    fund_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    report_date: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD or YYYYQ1
    stock_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    stock_name: Mapped[str] = mapped_column(String(100), nullable=False)
    holding_ratio: Mapped[float] = mapped_column(Float)  # 占净值比例 (%)
    holding_value: Mapped[float] = mapped_column(Float)  # 持仓市值 (万元)
    holding_change: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 新进/增持/减持/不变
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_fund_holdings", "fund_code", "report_date"),
        Index("idx_stock_reverse", "stock_code", "report_date"),  # For stock-reverse query
    )


class FundIndustryAllocation(Base):
    """基金行业配置表 - Fund portfolio industry allocation details."""
    __tablename__ = "fund_industry_allocation"

    fund_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    report_date: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD
    industry: Mapped[str] = mapped_column(String(100), primary_key=True)  # 行业名称
    allocation_ratio: Mapped[float] = mapped_column(Float)  # 配置比例 (%)
    market_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 市值 (万元)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_fund_industry", "fund_code", "report_date"),
    )
