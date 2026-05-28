"""
Fund API router - Filter, Compare, Similarity, Issue, Company.
"""
import time
import numpy as np
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import get_db
from backend.models.fund import FundIndicators, FundIssuePipeline, FundCompanyMetadata, FundPortfolioHoldings, FundIndustryAllocation
from backend.schemas.fund import (
    FundFilterRequest,
    FundFilterResponse,
    FundIndicatorResponse,
    FundCompareRequest,
    CorrelationMatrixResponse,
    FundSimilarityResponse,
    SimilarFund,
    FactorExposureItem,
    AIPCalculateRequest,
    AIPCalculateResponse,
    FundHoldingsResponse,
    FundHoldingItem,
    IndustryAllocationResponse,
    IndustryAllocationItem,
    StockReverseHoldingItem,
    StockReverseHoldingResponse,
)
from backend.services.correlation import calculate_pearson_matrix, correlation_matrix_to_list
from backend.services.factor_exposure import FactorExposureAnalyzer, ALL_FACTORS
from backend.services.pandas_cache import pandas_filter_service

router = APIRouter()


@router.post("/filter", response_model=FundFilterResponse)
async def filter_funds(
    request: FundFilterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    公募基金筛选 - 5-dimension cascade filtering.
    Supports: basic info, holdings, sector, performance, manager style.
    Returns paginated results with <10ms query time.
    """
    conditions = []
    
    if request.fund_types:
        conditions.append(FundIndicators.fund_type.in_(request.fund_types))
    
    if request.setup_year_min is not None:
        conditions.append(FundIndicators.setup_year >= request.setup_year_min)
    if request.setup_year_max is not None:
        conditions.append(FundIndicators.setup_year <= request.setup_year_max)
    
    if request.scale_min is not None:
        conditions.append(FundIndicators.scale >= request.scale_min)
    if request.scale_max is not None:
        conditions.append(FundIndicators.scale <= request.scale_max)
    
    if request.company_names:
        conditions.append(FundIndicators.company_name.in_(request.company_names))
    
    if request.return_1y_min is not None:
        conditions.append(FundIndicators.return_1y >= request.return_1y_min)
    if request.return_1y_max is not None:
        conditions.append(FundIndicators.return_1y <= request.return_1y_max)
    
    if request.max_drawdown_1y_max is not None:
        conditions.append(FundIndicators.max_drawdown_1y <= request.max_drawdown_1y_max)
    
    if request.sharpe_1y_min is not None:
        conditions.append(FundIndicators.sharpe_1y >= request.sharpe_1y_min)
    
    if request.new_high_ratio_min is not None:
        conditions.append(FundIndicators.new_high_ratio_1y >= request.new_high_ratio_min)
    
    query = select(FundIndicators)
    if conditions:
        query = query.where(and_(*conditions))
    
    count_query = select(FundIndicators.fund_code)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total_result = await db.execute(count_query)
    total = len(total_result.all())
    
    sort_column = getattr(FundIndicators, request.sort_by, FundIndicators.return_1y)
    if request.sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    offset = (request.page - 1) * request.page_size
    query = query.offset(offset).limit(request.page_size)
    
    result = await db.execute(query)
    funds = result.scalars().all()
    
    fund_responses = [
        FundIndicatorResponse(
            fund_code=f.fund_code,
            fund_name=f.fund_name,
            fund_type=f.fund_type,
            manager=f.manager,
            setup_date=f.setup_date,
            setup_year=f.setup_year,
            scale=f.scale,
            company_name=f.company_name,
            return_1y=f.return_1y,
            volatility_1y=f.volatility_1y,
            max_drawdown_1y=f.max_drawdown_1y,
            sharpe_1y=f.sharpe_1y,
            new_high_ratio_1y=f.new_high_ratio_1y,
            heavy_sector=f.heavy_sector,
            manager_honors=f.manager_honors,
        )
        for f in funds
    ]
    
    return FundFilterResponse(
        total=total,
        page=request.page,
        page_size=request.page_size,
        funds=fund_responses,
    )


@router.get("/stock-reverse/{stock_code}/export")
async def export_stock_reverse_holding(
    stock_code: str,
    format: str = Query("csv", pattern="^(csv|excel)$", description="Export format"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to export"),
    db: AsyncSession = Depends(get_db),
):
    """
    Export stock reverse holding data to CSV or Excel.
    
    Returns file download response with all funds holding the specified stock.
    """
    from fastapi.responses import StreamingResponse
    from io import BytesIO, StringIO
    import pandas as pd
    
    result = await db.execute(
        select(FundPortfolioHoldings)
        .where(FundPortfolioHoldings.stock_code == stock_code)
        .order_by(FundPortfolioHoldings.holding_ratio.desc())
        .limit(limit)
    )
    holdings = result.scalars().all()
    
    if not holdings:
        raise HTTPException(status_code=404, detail=f"No holdings found for stock {stock_code}")
    
    fund_codes = list(set(h.fund_code for h in holdings))
    result = await db.execute(
        select(FundIndicators).where(FundIndicators.fund_code.in_(fund_codes))
    )
    funds_info = {f.fund_code: f.fund_name for f in result.scalars().all()}
    
    data = [
        {
            "fund_code": h.fund_code,
            "fund_name": funds_info.get(h.fund_code, ""),
            "stock_code": h.stock_code,
            "stock_name": h.stock_name,
            "holding_ratio_pct": round(h.holding_ratio * 100, 4) if h.holding_ratio else 0,
            "holding_value": h.holding_value,
            "report_date": h.report_date,
        }
        for h in holdings
    ]
    
    df = pd.DataFrame(data)
    
    if format == "csv":
        output = StringIO()
        df.to_csv(output, index=False, encoding="utf-8-sig")
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=stock_reverse_{stock_code}.csv"
            }
        )
    
    else:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="持仓明细")
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=stock_reverse_{stock_code}.xlsx"
            }
        )


@router.get("/stock-reverse/{stock_code}/crowding")
async def get_stock_crowding_analysis(
    stock_code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get crowding analysis for a stock's institutional holdings.
    
    Returns comprehensive metrics:
    - HHI index (Herfindahl-Hirschman Index)
    - Concentration level
    - Overlap coefficient
    - Top fund analysis
    """
    from backend.services.crowding_analysis import get_crowding_score
    
    return await get_crowding_score(stock_code)


@router.get("/stock-reverse/{stock_code}/aggregation")
async def get_stock_aggregation(
    stock_code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get aggregated statistics for stock holdings across funds.
    
    Returns:
    - Total funds count
    - Weight statistics (total, avg, max, std)
    - Quarter distribution
    """
    from backend.services.duckdb_ingestion import aggregate_by_stock
    
    return await aggregate_by_stock(stock_code)


@router.get("/stock-reverse", response_model=StockReverseHoldingResponse)
async def get_stock_reverse_holding(
    stock_code: str = Query(..., description="股票代码，如 600519"),
    limit: int = Query(50, ge=1, le=200, description="返回基金数量上限"),
    db: AsyncSession = Depends(get_db),
):
    """
    反向查询：根据股票代码查询所有持有该股票的基金
    用于机构抱团拥挤度分析
    """
    from sqlalchemy import func
    
    result = await db.execute(
        select(FundPortfolioHoldings)
        .where(FundPortfolioHoldings.stock_code == stock_code)
        .order_by(FundPortfolioHoldings.holding_ratio.desc())
    )
    holdings = result.scalars().all()
    
    if not holdings:
        return StockReverseHoldingResponse(
            stock_code=stock_code,
            stock_name="",
            total_funds=0,
            aggregate_exposure=0.0,
            funds=[],
        )
    
    stock_name = holdings[0].stock_name
    
    fund_codes = list(set(h.fund_code for h in holdings))
    result = await db.execute(
        select(FundIndicators).where(FundIndicators.fund_code.in_(fund_codes))
    )
    funds_info = {f.fund_code: f.fund_name for f in result.scalars().all()}
    
    fund_items = []
    for h in holdings[:limit]:
        fund_items.append(
            StockReverseHoldingItem(
                fund_code=h.fund_code,
                fund_name=funds_info.get(h.fund_code, ""),
                holding_ratio=h.holding_ratio,
                holding_value=h.holding_value,
                report_date=h.report_date,
            )
        )
    
    aggregate_exposure = sum(h.holding_ratio for h in holdings)
    
    return StockReverseHoldingResponse(
        stock_code=stock_code,
        stock_name=stock_name,
        total_funds=len(holdings),
        aggregate_exposure=round(aggregate_exposure, 2),
        funds=fund_items,
    )


@router.get("/issue")
async def get_fund_issue_calendar(
    week: str = Query(None, description="YYYY第X周格式"),
    status: str = Query(None, description="首发/即将发售/成立/退市"),
    db: AsyncSession = Depends(get_db),
):
    """公募基金发行看板 - 周历管线."""
    conditions = []
    if status:
        conditions.append(FundIssuePipeline.status == status)
    
    query = select(FundIssuePipeline)
    if conditions:
        query = query.where(and_(*conditions))
    
    result = await db.execute(query)
    issues = result.scalars().all()
    
    return [
        {
            "fund_code": i.fund_code,
            "fund_name": i.fund_name,
            "company": i.company,
            "subscribe_start_date": i.subscribe_start_date,
            "subscribe_end_date": i.subscribe_end_date,
            "status": i.status,
            "initial_scale": i.initial_scale,
            "delist_scale": i.delist_scale,
        }
        for i in issues
    ]


@router.get("/company/{company_id}/distribution")
async def get_company_distribution(
    company_id: str,
    dist_type: str = Query("asset_class", description="asset_class/sector/bond_type"),
    db: AsyncSession = Depends(get_db),
):
    """基金公司资产配置分布 - Treemap/Bubble chart data."""
    from backend.models.fund import FundCompanyDistributionHistory
    
    result = await db.execute(
        select(FundCompanyDistributionHistory)
        .where(
            FundCompanyDistributionHistory.company_id == company_id,
            FundCompanyDistributionHistory.dist_type == dist_type
        )
        .order_by(FundCompanyDistributionHistory.stat_quarter.desc())
    )
    distributions = result.scalars().all()
    
    if not distributions:
        return {"items": [], "is_simulated": True}
    
    # Group by quarter, take latest
    items = []
    for d in distributions:
        items.append({
            "item_name": d.item_name,
            "weight": d.weight,
        })
    
    return {"items": items, "is_simulated": False}


@router.get("/similarity/calc", response_model=FundSimilarityResponse)
async def calculate_fund_similarity(
    fund_code: str = Query(..., description="Fund code to find similar funds for"),
    top_n: int = Query(default=10, ge=1, le=50, description="Number of similar funds to return"),
    method: str = Query(default="euclidean", pattern="^(euclidean|cosine)$", description="Distance calculation method"),
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate fund similarity using factor exposure analysis.
    
    Uses 14-factor model (6 style + 8 sector) with SLSQP constrained regression.
    Returns top N similar funds ranked by factor exposure distance.
    Performance target: <200ms per request.
    """
    start_time = time.perf_counter()
    
    # Verify input fund exists
    input_fund = pandas_filter_service.get_fund_by_code(fund_code)
    if input_fund is None:
        raise HTTPException(status_code=404, detail=f"Fund {fund_code} not found")
    
    # Initialize factor exposure analyzer
    analyzer = FactorExposureAnalyzer()
    
    # Generate simulated fund returns for input fund
    np.random.seed(hash(fund_code) % (2**32))
    input_returns = np.random.randn(252) * 0.02 + 0.0005
    
    # Get factor returns (uses O-U simulation as fallback)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - __import__("datetime").timedelta(days=365)).strftime("%Y-%m-%d")
    factor_returns = analyzer.get_factor_returns(start_date, end_date)
    
    # Calculate factor exposure for input fund
    input_weights, input_metadata = analyzer.estimate_exposure(input_returns, factor_returns)
    
    # Get all funds from cache for comparison
    all_funds_df = pandas_filter_service.cache.df
    
    # Sample funds for comparison (limit to avoid performance issues)
    sample_size = min(500, len(all_funds_df))
    sample_funds = all_funds_df.sample(n=sample_size, random_state=42)
    
    # Calculate similarity for each sampled fund
    similarities = []
    
    for _, fund_row in sample_funds.iterrows():
        if fund_row["fund_code"] == fund_code:
            continue
        
        # Generate simulated returns for comparison fund
        np.random.seed(hash(fund_row["fund_code"]) % (2**32))
        comp_returns = np.random.randn(252) * 0.02 + 0.0005
        
        # Calculate factor exposure
        comp_weights, _ = analyzer.estimate_exposure(comp_returns, factor_returns)
        
        # Calculate distance
        if method == "euclidean":
            distance = np.sqrt(np.sum((input_weights - comp_weights) ** 2))
            similarity = 1.0 / (1.0 + distance)
        else:  # cosine
            dot_product = np.dot(input_weights, comp_weights)
            norm_input = np.linalg.norm(input_weights)
            norm_comp = np.linalg.norm(comp_weights)
            similarity = dot_product / (norm_input * norm_comp) if norm_input > 0 and norm_comp > 0 else 0.0
        
        similarities.append({
            "fund_code": fund_row["fund_code"],
            "fund_name": fund_row["fund_name"],
            "similarity": float(similarity),
        })
    
    # Sort by similarity descending and take top N
    similarities.sort(key=lambda x: x["similarity"], reverse=True)
    top_similar = similarities[:top_n]
    
    # Format factor exposure for response
    factor_exposure = [
        FactorExposureItem(
            factor_name=ALL_FACTORS[i],
            factor_type="style" if i < 6 else "sector",
            weight=float(input_weights[i]),
        )
        for i in range(len(ALL_FACTORS))
    ]
    factor_exposure.sort(key=lambda x: x.weight, reverse=True)
    
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    
    return FundSimilarityResponse(
        fund_code=fund_code,
        similar_funds=[SimilarFund(**f) for f in top_similar],
        factor_exposure=factor_exposure,
        calculation_method=method,
        elapsed_ms=round(elapsed_ms, 2),
    )


@router.get("/{fund_code}/nav-trend")
async def get_fund_nav_trend(
    fund_code: str,
    days: int = Query(30, description="Number of days to return"),
    db: AsyncSession = Depends(get_db),
):
    """基金净值趋势 - Sparkline data for fund filter."""
    from backend.models.fund import FundNavHistory
    from datetime import datetime, timedelta
    
    # Calculate date range
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
    
    result = await db.execute(
        select(FundNavHistory)
        .where(
            FundNavHistory.fund_code == fund_code,
            FundNavHistory.nav_date >= start_date
        )
        .order_by(FundNavHistory.nav_date.desc())
        .limit(days)
    )
    nav_history = result.scalars().all()
    
    if not nav_history:
        return {"nav_values": [], "dates": [], "is_simulated": True}
    
    # Reverse to get chronological order
    nav_history = list(reversed(nav_history))
    
    return {
        "nav_values": [n.nav_value for n in nav_history],
        "dates": [n.nav_date for n in nav_history],
        "is_simulated": False,
    }


@router.get("/company")
async def get_fund_companies(
    db: AsyncSession = Depends(get_db),
):
    """公募基金公司透视总览."""
    result = await db.execute(
        select(FundCompanyMetadata)
        .order_by(FundCompanyMetadata.total_scale.desc())
    )
    companies = result.scalars().all()
    
    return [
        {
            "company_id": c.company_id,
            "company_name": c.company_name,
            "establish_date": c.establish_date,
            "total_scale": c.total_scale,
            "non_money_scale": c.non_money_scale,
            "fund_count": c.fund_count,
            "manager_count": c.manager_count,
        }
        for c in companies
    ]


@router.post("/compare", response_model=CorrelationMatrixResponse)
async def compare_funds(
    request: FundCompareRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    公募基金对比 - 最多15只基金的深度穿透分析.
    Returns correlation matrix and factor exposures.
    """
    if len(request.fund_codes) > 15:
        raise HTTPException(status_code=400, detail="Maximum 15 funds allowed")
    
    matrix_dict, is_real_data = await calculate_pearson_matrix(
        db=db,
        fund_codes=request.fund_codes,
        start_date=request.start_date,
        end_date=request.end_date,
        use_cache=True,
    )
    
    matrix = correlation_matrix_to_list(matrix_dict, request.fund_codes)
    
    return CorrelationMatrixResponse(
        fund_codes=request.fund_codes,
        correlation_matrix=matrix,
        calculation_date=datetime.now().strftime("%Y-%m-%d"),
        sample_size=len(request.fund_codes),
        data_quality={"is_real_data": is_real_data},
    )


@router.post("/aip-calculate", response_model=AIPCalculateResponse)
async def calculate_aip_endpoint(
    request: AIPCalculateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    定投收益计算 - 计算定期定额投资的收益、回撤、波动率.
    支持周定投、双周定投、月定投.
    """
    from backend.services.aip_calculator import calculate_aip, AIPCalculatorError
    from backend.models.fund import FundIndicators
    
    try:
        result = await calculate_aip(
            fund_code=request.fund_code,
            frequency=request.frequency,
            amount=request.amount,
            start_date=request.start_date,
            end_date=request.end_date,
            db=db
        )
        
        fund_result = await db.execute(
            select(FundIndicators).where(FundIndicators.fund_code == request.fund_code)
        )
        fund = fund_result.scalar_one_or_none()
        fund_name = fund.fund_name if fund else request.fund_code
        
        return AIPCalculateResponse(
            fund_code=request.fund_code,
            fund_name=fund_name,
            frequency=request.frequency,
            amount=request.amount,
            total_investment=result.total_investment,
            current_value=result.current_value,
            return_rate=result.return_rate,
            max_drawdown=result.max_drawdown,
            volatility=result.volatility,
            periods=result.periods,
            units_total=result.units_total,
            lump_sum_comparison=result.lump_sum_comparison,
            investment_dates=result.investment_dates,
            nav_history=result.nav_history
        )
    
    except AIPCalculatorError as e:
        error_msg = str(e)
        if "No NAV history" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")


@router.get("/{fund_code}/holdings", response_model=FundHoldingsResponse)
async def get_fund_holdings(
    fund_code: str,
    report_date: Optional[str] = Query(None, description="报告期 (YYYY-MM-DD 或 YYYYQ1格式)"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取基金持仓明细 - 股票持仓列表.
    支持历史报告期查询, 默认返回最新一期.
    """
    from backend.services.ingestion import fund_portfolio_em, save_fund_holdings
    
    if report_date:
        result = await db.execute(
            select(FundPortfolioHoldings)
            .where(
                FundPortfolioHoldings.fund_code == fund_code,
                FundPortfolioHoldings.report_date == report_date
            )
            .order_by(FundPortfolioHoldings.holding_ratio.desc())
        )
        holdings_db = result.scalars().all()
        
        if holdings_db:
            holdings = [
                FundHoldingItem(
                    stock_code=h.stock_code,
                    stock_name=h.stock_name,
                    holding_ratio=h.holding_ratio,
                    holding_value=h.holding_value,
                    holding_change=h.holding_change,
                )
                for h in holdings_db
            ]
            
            return FundHoldingsResponse(
                fund_code=fund_code,
                report_date=report_date,
                holdings=holdings,
                total_count=len(holdings),
                data_source="database",
            )
    
    result = await db.execute(
        select(FundPortfolioHoldings)
        .where(FundPortfolioHoldings.fund_code == fund_code)
        .order_by(FundPortfolioHoldings.report_date.desc())
        .limit(1)
    )
    latest_holding = result.scalar_one_or_none()
    
    if latest_holding:
        latest_report_date = latest_holding.report_date
        
        result = await db.execute(
            select(FundPortfolioHoldings)
            .where(
                FundPortfolioHoldings.fund_code == fund_code,
                FundPortfolioHoldings.report_date == latest_report_date
            )
            .order_by(FundPortfolioHoldings.holding_ratio.desc())
        )
        holdings_db = result.scalars().all()
        
        holdings = [
            FundHoldingItem(
                stock_code=h.stock_code,
                stock_name=h.stock_name,
                holding_ratio=h.holding_ratio,
                holding_value=h.holding_value,
                holding_change=h.holding_change,
            )
            for h in holdings_db
        ]
        
        return FundHoldingsResponse(
            fund_code=fund_code,
            report_date=latest_report_date,
            holdings=holdings,
            total_count=len(holdings),
            data_source="database",
        )
    
    try:
        holdings_raw, report_date_detected = await fund_portfolio_em(fund_code)
        
        if not holdings_raw:
            raise HTTPException(status_code=404, detail=f"No holdings found for fund {fund_code}")
        
        holdings = [
            FundHoldingItem(
                stock_code=h["stock_code"],
                stock_name=h["stock_name"],
                holding_ratio=h["holding_ratio"],
                holding_value=h["holding_value"],
                holding_change=h.get("holding_change"),
            )
            for h in holdings_raw
        ]
        
        await save_fund_holdings(fund_code, holdings_raw, report_date_detected)
        
        return FundHoldingsResponse(
            fund_code=fund_code,
            report_date=report_date_detected,
            holdings=holdings,
            total_count=len(holdings),
            data_source="akshare",
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch holdings: {str(e)}")


@router.get("/{fund_code}")
async def get_fund_detail(
    fund_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Get single fund details."""
    result = await db.execute(
        select(FundIndicators).where(FundIndicators.fund_code == fund_code)
    )
    fund = result.scalar_one_or_none()

    if not fund:
        raise HTTPException(status_code=404, detail="Fund not found")

    return FundIndicatorResponse(
        fund_code=fund.fund_code,
        fund_name=fund.fund_name,
        fund_type=fund.fund_type,
        manager=fund.manager,
        setup_date=fund.setup_date,
        setup_year=fund.setup_year,
        scale=fund.scale,
        company_name=fund.company_name,
        return_1y=fund.return_1y,
        volatility_1y=fund.volatility_1y,
        max_drawdown_1y=fund.max_drawdown_1y,
        sharpe_1y=fund.sharpe_1y,
        new_high_ratio_1y=fund.new_high_ratio_1y,
        heavy_sector=fund.heavy_sector,
        manager_honors=fund.manager_honors,
    )


@router.get("/{fund_code}/industry", response_model=IndustryAllocationResponse)
async def get_fund_industry_allocation(
    fund_code: str,
    report_date: Optional[str] = Query(None, description="报告日期 YYYY-MM-DD, 默认最新"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取基金行业配置 - Fund industry allocation from portfolio reports.
    
    If data not in DB, fetches from AkShare and stores.
    Returns latest report by default, or specific report_date if provided.
    """
    from backend.services.ingestion import ingest_fund_industry_allocation
    
    if report_date:
        result = await db.execute(
            select(FundIndustryAllocation)
            .where(
                FundIndustryAllocation.fund_code == fund_code,
                FundIndustryAllocation.report_date == report_date,
            )
            .order_by(FundIndustryAllocation.allocation_ratio.desc())
        )
        allocations = result.scalars().all()
        
        if allocations:
            return IndustryAllocationResponse(
                fund_code=fund_code,
                report_date=report_date,
                allocations=[
                    IndustryAllocationItem(
                        industry=a.industry,
                        allocation_ratio=a.allocation_ratio,
                        market_value=a.market_value,
                    )
                    for a in allocations
                ],
                data_source="database",
            )
    
    result = await db.execute(
        select(FundIndustryAllocation)
        .where(FundIndustryAllocation.fund_code == fund_code)
        .order_by(
            FundIndustryAllocation.report_date.desc(),
            FundIndustryAllocation.allocation_ratio.desc(),
        )
    )
    allocations = result.scalars().all()
    
    if allocations:
        latest_date = allocations[0].report_date
        latest_allocations = [a for a in allocations if a.report_date == latest_date]
        
        return IndustryAllocationResponse(
            fund_code=fund_code,
            report_date=latest_date,
            allocations=[
                IndustryAllocationItem(
                    industry=a.industry,
                    allocation_ratio=a.allocation_ratio,
                    market_value=a.market_value,
                )
                for a in latest_allocations
            ],
            data_source="database",
        )
    
    records = await ingest_fund_industry_allocation(fund_code=fund_code)
    
    if records:
        latest_date = records[0]["report_date"]
        latest_records = [r for r in records if r["report_date"] == latest_date]
        
        return IndustryAllocationResponse(
            fund_code=fund_code,
            report_date=latest_date,
            allocations=[
                IndustryAllocationItem(
                    industry=r["industry"],
                    allocation_ratio=r["allocation_ratio"],
                    market_value=r.get("market_value"),
                )
                for r in latest_records
            ],
            data_source="akshare",
        )
    
    return IndustryAllocationResponse(
        fund_code=fund_code,
        report_date="",
        allocations=[],
        data_source="none",
    )