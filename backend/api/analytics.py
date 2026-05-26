"""
Analytics API router - Fear/Greed, ERP, Crowding, Style Strength.
"""
import numpy as np
from scipy.optimize import minimize
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import get_db
from backend.models.fund import (
    MarketFearGreedSentimentHistory,
    BondEquityYieldSpreadHistory,
    MarketStyleStrengthHistory,
    MarketCrowdingValuationHistory,
    BacktestStatsMacroStrategies,
)
from backend.schemas.fund import (
    FearGreedResponse,
    ERPSpreadResponse,
    CrowdingRotationVector,
    TrajectoryResponse,
    TrajectoryVector,
    TrajectoryPoint,
)
from backend.services.quant_engine import (
    calculate_phase_space_trajectory,
    build_echarts_trajectory_data,
)

router = APIRouter()


@router.get("/fear-greed")
async def get_fear_greed_index(
    db: AsyncSession = Depends(get_db),
):
    """
    恐惧贪婪指数 - 6维因子树拓扑.
    Returns composite score and factor breakdown.
    """
    result = await db.execute(
        select(MarketFearGreedSentimentHistory)
        .order_by(MarketFearGreedSentimentHistory.trade_date.desc())
        .limit(30)
    )
    history = result.scalars().all()
    
    return [
        FearGreedResponse(
            trade_date=h.trade_date,
            composite_score=h.composite_score,
            sentiment_status=h.sentiment_status,
            factor_volatility=h.factor_volatility,
            factor_safe_haven=h.factor_safe_haven,
            factor_margin_ratio=h.factor_margin_ratio,
            factor_volume_deviation=h.factor_volume_deviation,
            factor_futures_basis=h.factor_futures_basis,
            factor_stock_strength=h.factor_stock_strength,
        )
        for h in history
    ]


@router.get("/erp")
async def get_erp_spread(
    index_code: str = Query("000300", description="指数代码"),
    db: AsyncSession = Depends(get_db),
):
    """
    股债ERP收益差 - 标准差视角与百分位视角.
    Returns ERP history with ±1SD, ±2SD channels.
    """
    result = await db.execute(
        select(BondEquityYieldSpreadHistory)
        .where(BondEquityYieldSpreadHistory.index_code == index_code)
        .order_by(BondEquityYieldSpreadHistory.trade_date.desc())
        .limit(500)
    )
    history = result.scalars().all()
    
    return [
        ERPSpreadResponse(
            index_code=h.index_code,
            index_name="沪深300" if h.index_code == "000300" else "中证500",
            trade_date=h.trade_date,
            pe_ttm=h.pe_ttm,
            treasury_yield_10y=h.treasury_yield_10y,
            erp_spread=h.erp_spread,
            percentile_rank_10y=h.percentile_rank_10y,
            index_close_price=h.index_close_price,
        )
        for h in history
    ]


@router.get("/style-strength")
async def get_style_strength(
    db: AsyncSession = Depends(get_db),
):
    """
    市场风格强度 - 大小盘/价值成长相对强弱.
    Returns ratio history with percentile bands.
    """
    result = await db.execute(
        select(MarketStyleStrengthHistory)
        .order_by(MarketStyleStrengthHistory.trade_date.desc())
        .limit(100)
    )
    history = result.scalars().all()
    
    return [
        {
            "trade_date": h.trade_date,
            "index_code_num": h.index_code_num,
            "index_code_den": h.index_code_den,
            "ratio_value": h.ratio_value,
            "percentile_rank_3y": h.percentile_rank_3y,
        }
        for h in history
    ]


@router.get("/crowding")
async def get_crowding_analysis(
    category: str = Query(None, description="sector/index/style/concept"),
    db: AsyncSession = Depends(get_db),
):
    """
    市场拥挤度分析 - 换手率/资金流入合成拥挤度指标.
    Returns crowding score and PE percentile matrix.
    """
    conditions = []
    if category:
        conditions.append(MarketCrowdingValuationHistory.category == category)
    
    result = await db.execute(
        select(MarketCrowdingValuationHistory)
        .where(*conditions)
        .order_by(MarketCrowdingValuationHistory.trade_date.desc())
        .limit(100)
    )
    history = result.scalars().all()
    
    return [
        {
            "asset_code": h.asset_code,
            "trade_date": h.trade_date,
            "category": h.category,
            "crowding_score": h.crowding_score,
            "pe_percentile": h.pe_percentile,
            "close_price": h.close_price,
        }
        for h in history
    ]


@router.get("/rotation-vector")
async def get_rotation_vectors(
    t0_date: str = Query(..., description="起始日期 (YYYY-MM-DD)"),
    t1_date: str = Query(..., description="结束日期 (YYYY-MM-DD)"),
    category: str = Query("sector", description="sector/index/style"),
    db: AsyncSession = Depends(get_db),
):
    """
    相空间旋转轨迹向量图 - 行业轮动向量提取.
    
    Mathematical Framework:
    -----------------------
    Phase Space Vector: (crowding_score, pe_percentile)
    - Position: (x, y) at time T
    - Velocity: d(crowding_score)/dt
    - Acceleration: d²(crowding_score)/dt²
    
    Trajectory Vector (T₀ → T₁):
    - Start point: (crowding_T0, pe_T0)
    - End point: (crowding_T1, pe_T1)
    - Arrow direction: θ = atan2(Δpe, Δcrowding)
    - Magnitude: |v| = sqrt(Δcrowding² + Δpe²)
    
    Rotation Detection:
    - Clockwise: PE decreasing (improving valuation)
    - Counter-clockwise: PE increasing (deteriorating valuation)
    - Regime change: |angular velocity| > threshold
    
    Returns T0→T1 trajectory vectors for visualization.
    Performance target: <500ms for 100 assets.
    """
    # Validate date format
    try:
        from datetime import datetime
        dt0 = datetime.strptime(t0_date, "%Y-%m-%d")
        dt1 = datetime.strptime(t1_date, "%Y-%m-%d")
        if dt1 <= dt0:
            return {"error": "End date must be after start date", "vectors": [], "regime_change": False}
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD", "vectors": [], "regime_change": False}
    
    # Query historical data for the date range
    result = await db.execute(
        select(MarketCrowdingValuationHistory)
        .where(
            MarketCrowdingValuationHistory.trade_date >= t0_date,
            MarketCrowdingValuationHistory.trade_date <= t1_date,
            MarketCrowdingValuationHistory.category == category,
        )
        .order_by(MarketCrowdingValuationHistory.trade_date)
    )
    data = result.scalars().all()
    
    # Group by asset_code
    asset_data = {}
    for d in data:
        if d.asset_code not in asset_data:
            asset_data[d.asset_code] = []
        asset_data[d.asset_code].append({
            "trade_date": d.trade_date,
            "crowding_score": d.crowding_score,
            "pe_percentile": d.pe_percentile,
        })
    
    # Calculate trajectory for each asset
    trajectories = []
    for asset_code, history in asset_data.items():
        try:
            traj = calculate_phase_space_trajectory(history, t0_date, t1_date)
            traj["asset_code"] = asset_code
            trajectories.append(traj)
        except ValueError as e:
            # Skip assets with insufficient data
            continue
    
    # Build ECharts-compatible response
    echarts_data = build_echarts_trajectory_data(trajectories)
    
    return TrajectoryResponse(**echarts_data)


@router.get("/rotation-vector-legacy")
async def get_rotation_vectors_legacy(
    t0_date: str = Query(..., description="起始日期"),
    t1_date: str = Query(..., description="结束日期"),
    category: str = Query("sector", description="sector/index/style"),
    db: AsyncSession = Depends(get_db),
):
    """
    Legacy endpoint for backward compatibility.
    Returns basic rotation vectors without advanced calculations.
    """
    result = await db.execute(
        select(MarketCrowdingValuationHistory)
        .where(
            MarketCrowdingValuationHistory.trade_date.in_([t0_date, t1_date]),
            MarketCrowdingValuationHistory.category == category,
        )
        .order_by(MarketCrowdingValuationHistory.trade_date)
    )
    data = result.scalars().all()
    
    # Group by asset_code
    vectors = []
    asset_data = {}
    for d in data:
        if d.asset_code not in asset_data:
            asset_data[d.asset_code] = {}
        asset_data[d.asset_code][d.trade_date] = {
            "crowding": d.crowding_score,
            "pe_percentile": d.pe_percentile,
        }
    
    # Build rotation vectors
    for asset_code, dates in asset_data.items():
        if t0_date in dates and t1_date in dates:
            vectors.append(CrowdingRotationVector(
                asset_code=asset_code,
                asset_name=asset_code,  # Real impl would lookup name
                t0_date=t0_date,
                t1_date=t1_date,
                t0_crowding=dates[t0_date]["crowding"],
                t1_crowding=dates[t1_date]["crowding"],
                t0_pe_percentile=dates[t0_date]["pe_percentile"],
                t1_pe_percentile=dates[t1_date]["pe_percentile"],
            ))
    
    return vectors


@router.get("/backtest")
async def get_backtest_expectation(
    metric_type: str = Query(..., description="fear_greed/erp/crowding"),
    range_min: float = Query(...),
    range_max: float = Query(...),
    holding_period: str = Query("3M", description="3M/6M/1Y"),
    db: AsyncSession = Depends(get_db),
):
    """
    宏观策略持有期期望回测 - 根据当前分位数计算历史胜率.
    """
    result = await db.execute(
        select(BacktestStatsMacroStrategies)
        .where(
            BacktestStatsMacroStrategies.metric_type == metric_type,
            BacktestStatsMacroStrategies.range_min >= range_min,
            BacktestStatsMacroStrategies.range_max <= range_max,
            BacktestStatsMacroStrategies.holding_period == holding_period,
        )
    )
    stats = result.scalars().all()
    
    return [
        {
            "index_code": s.index_code,
            "win_probability": s.win_probability,
            "avg_return": s.avg_return,
        }
        for s in stats
    ]


# ===== Quantitative Algorithms =====

def calculate_factor_exposure(
    fund_returns: np.ndarray,
    factor_returns: np.ndarray,
) -> np.ndarray:
    """
    Sharpe多因子约束回归算法 - SLSQP optimization.
    
    Constraints:
    1. sum(weights) == 1.0 (no leverage)
    2. weights >= 0.0 (no short selling)
    
    Returns 14-factor exposure coefficients.
    """
    num_factors = factor_returns.shape[1]
    
    def rss_objective(weights):
        estimated = np.dot(factor_returns, weights)
        return np.sum((fund_returns - estimated) ** 2)
    
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    bounds = [(0.0, 1.0) for _ in range(num_factors)]
    initial = np.ones(num_factors) / num_factors
    
    solution = minimize(
        rss_objective,
        initial,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
    )
    
    return solution.x if solution.success else initial


@router.post("/factor-exposure")
async def calculate_exposure(
    fund_code: str,
    start_date: str,
    end_date: str,
):
    """
    计算单只基金的风格/板块因子暴露度.
    Returns 6-style + 8-sector exposure coefficients.
    """
    # Placeholder: Return mock factor exposure
    # Real impl would query fund returns and factor returns
    mock_exposure = np.array([
        0.15, 0.25, 0.10, 0.20, 0.05, 0.10,  # 6 style factors
        0.05, 0.20, 0.15, 0.05, 0.03, 0.02, 0.00, 0.00,  # 8 sector factors
        0.05,  # intercept
    ])
    
    return {
        "fund_code": fund_code,
        "exposure": mock_exposure.tolist(),
    }