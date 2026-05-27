"""
Portfolio API endpoints.
CRUD operations for user portfolios and backtest execution.
"""
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.models.portfolio import UserPortfolio, BacktestResult as BacktestResultModel
from backend.schemas.portfolio import (
    PortfolioCreate,
    PortfolioUpdate,
    PortfolioResponse,
    PortfolioListResponse,
    FundAllocation,
    BacktestRequest,
    BacktestResultResponse,
    BacktestListResponse,
    BacktestDetailResponse,
    DailyReturn,
    BacktestStatistics,
    BrinsonAttribution,
)
from backend.services.backtest import run_backtest, BacktestError
from backend.services.brinson import calculate_brinson_attribution, BrinsonAttributionError

logger = logging.getLogger(__name__)

router = APIRouter()


def parse_json_field(value) -> List[Dict[str, Any]]:
    """Parse JSON field from SQLAlchemy model (can be str or list)."""
    if value is None:
        return []
    if isinstance(value, str):
        return json.loads(value)
    return value


def parse_json_dict(value) -> Dict[str, Any]:
    """Parse JSON field as dict from SQLAlchemy model (can be str or dict)."""
    if value is None:
        return {}
    if isinstance(value, str):
        return json.loads(value)
    return value


def build_backtest_response(bt: BacktestResultModel) -> BacktestResultResponse:
    """Build BacktestResultResponse from database model."""
    portfolio_returns_data = parse_json_field(bt.portfolio_returns)
    portfolio_returns = [
        DailyReturn(
            date=r["date"],
            return_pct=round(r["return"], 4),
            nav=round(r["nav"], 4)
        )
        for r in portfolio_returns_data
    ]
    
    benchmark_returns = None
    benchmark_returns_data = parse_json_field(bt.benchmark_returns)
    if benchmark_returns_data:
        benchmark_returns = [
            DailyReturn(
                date=r["date"],
                return_pct=round(r["return"], 4),
                nav=round(r["nav"], 4)
            )
            for r in benchmark_returns_data
        ]
    
    brinson = None
    brinson_data = parse_json_dict(bt.brinson_attribution)
    if brinson_data:
        brinson = BrinsonAttribution(
            allocation_effect=float(brinson_data["allocation_effect"]) if isinstance(brinson_data.get("allocation_effect"), str) else brinson_data["allocation_effect"],
            selection_effect=float(brinson_data["selection_effect"]) if isinstance(brinson_data.get("selection_effect"), str) else brinson_data["selection_effect"],
            interaction_effect=float(brinson_data["interaction_effect"]) if isinstance(brinson_data.get("interaction_effect"), str) else brinson_data["interaction_effect"],
            total_effect=float(brinson_data["total_effect"]) if isinstance(brinson_data.get("total_effect"), str) else brinson_data["total_effect"],
        )
    
    statistics_data = parse_json_dict(bt.statistics)
    
    return BacktestResultResponse(
        id=bt.id,
        portfolio_id=bt.portfolio_id,
        start_date=bt.start_date,
        end_date=bt.end_date,
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        statistics=BacktestStatistics(
            total_return=float(statistics_data["total_return"]) if isinstance(statistics_data.get("total_return"), str) else statistics_data["total_return"],
            annual_return=float(statistics_data["annual_return"]) if isinstance(statistics_data.get("annual_return"), str) else statistics_data["annual_return"],
            max_drawdown=float(statistics_data["max_drawdown"]) if isinstance(statistics_data.get("max_drawdown"), str) else statistics_data["max_drawdown"],
            sharpe_ratio=float(statistics_data["sharpe"]) if isinstance(statistics_data.get("sharpe"), str) else statistics_data["sharpe"],
            volatility=float(statistics_data["volatility"]) if isinstance(statistics_data.get("volatility"), str) else statistics_data["volatility"],
            sortino_ratio=float(statistics_data["sortino_ratio"]) if statistics_data.get("sortino_ratio") and isinstance(statistics_data.get("sortino_ratio"), str) else statistics_data.get("sortino_ratio"),
            calmar_ratio=float(statistics_data["calmar_ratio"]) if statistics_data.get("calmar_ratio") and isinstance(statistics_data.get("calmar_ratio"), str) else statistics_data.get("calmar_ratio"),
        ),
        brinson_attribution=brinson,
        created_at=bt.created_at
    )


# ==================== Portfolio CRUD ====================

@router.post("", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    portfolio_data: PortfolioCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new FOF portfolio.
    
    - **name**: Portfolio name (required)
    - **description**: Portfolio description (optional)
    - **funds**: List of fund allocations [{"fund_code": "000001", "weight": 0.3}, ...]
    """
    try:
        # Normalize weights if needed
        funds_list: List[Dict[str, Any]] = [f.model_dump() for f in portfolio_data.funds]
        total_weight = sum(f["weight"] for f in funds_list)
        
        if abs(total_weight - 1.0) > 0.01:
            # Auto-normalize
            funds_list = [
                {"fund_code": f["fund_code"], "weight": f["weight"] / total_weight}
                for f in funds_list
            ]
        
        # Create portfolio
        portfolio = UserPortfolio(
            name=portfolio_data.name,
            description=portfolio_data.description,
            funds=funds_list,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(portfolio)
        await db.commit()
        await db.refresh(portfolio)
        
        return PortfolioResponse(
            id=portfolio.id,
            name=portfolio.name,
            description=portfolio.description,
            funds=[FundAllocation(**f) for f in parse_json_field(portfolio.funds)],
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at
        )
        
    except Exception as e:
        logger.error(f"Failed to create portfolio: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create portfolio: {str(e)}"
        )


@router.get("", response_model=PortfolioListResponse)
async def list_portfolios(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    List all user portfolios.
    
    - **skip**: Number of portfolios to skip
    - **limit**: Maximum number of portfolios to return
    """
    try:
        # Count total
        count_result = await db.execute(select(UserPortfolio))
        total = len(count_result.scalars().all())
        
        # Fetch portfolios
        result = await db.execute(
            select(UserPortfolio)
            .order_by(desc(UserPortfolio.created_at))
            .offset(skip)
            .limit(limit)
        )
        portfolios = result.scalars().all()
        
        return PortfolioListResponse(
            total=total,
            portfolios=[
                PortfolioResponse(
                    id=p.id,
                    name=p.name,
                    description=p.description,
                    funds=[FundAllocation(**f) for f in parse_json_field(p.funds)],
                    created_at=p.created_at,
                    updated_at=p.updated_at
                )
                for p in portfolios
            ]
        )
        
    except Exception as e:
        logger.error(f"Failed to list portfolios: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list portfolios: {str(e)}"
        )


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get portfolio details by ID.
    
    - **portfolio_id**: Portfolio ID
    """
    try:
        result = await db.execute(
            select(UserPortfolio).where(UserPortfolio.id == portfolio_id)
        )
        portfolio = result.scalar_one_or_none()
        
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Portfolio {portfolio_id} not found"
            )
        
        return PortfolioResponse(
            id=portfolio.id,
            name=portfolio.name,
            description=portfolio.description,
            funds=[FundAllocation(**f) for f in parse_json_field(portfolio.funds)],
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get portfolio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get portfolio: {str(e)}"
        )


@router.put("/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio(
    portfolio_id: int,
    portfolio_data: PortfolioUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update portfolio details.
    
    - **portfolio_id**: Portfolio ID
    - **name**: New name (optional)
    - **description**: New description (optional)
    - **funds**: New fund allocations (optional)
    """
    try:
        result = await db.execute(
            select(UserPortfolio).where(UserPortfolio.id == portfolio_id)
        )
        portfolio = result.scalar_one_or_none()
        
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Portfolio {portfolio_id} not found"
            )
        
        # Update fields
        if portfolio_data.name is not None:
            portfolio.name = portfolio_data.name
        
        if portfolio_data.description is not None:
            portfolio.description = portfolio_data.description
        
        if portfolio_data.funds is not None:
            funds_list: List[Dict[str, Any]] = [f.model_dump() for f in portfolio_data.funds]
            total_weight = sum(f["weight"] for f in funds_list)
            
            if abs(total_weight - 1.0) > 0.01:
                funds_list = [
                    {"fund_code": f["fund_code"], "weight": f["weight"] / total_weight}
                    for f in funds_list
                ]
            
            portfolio.funds = funds_list
        
        portfolio.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(portfolio)
        
        return PortfolioResponse(
            id=portfolio.id,
            name=portfolio.name,
            description=portfolio.description,
            funds=[FundAllocation(**f) for f in parse_json_field(portfolio.funds)],
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update portfolio: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update portfolio: {str(e)}"
        )


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete portfolio by ID.
    
    - **portfolio_id**: Portfolio ID
    """
    try:
        result = await db.execute(
            select(UserPortfolio).where(UserPortfolio.id == portfolio_id)
        )
        portfolio = result.scalar_one_or_none()
        
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Portfolio {portfolio_id} not found"
            )
        
        await db.delete(portfolio)
        await db.commit()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete portfolio: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete portfolio: {str(e)}"
        )


# ==================== Backtest Operations ====================

@router.post("/{portfolio_id}/backtest", response_model=BacktestResultResponse, status_code=status.HTTP_201_CREATED)
async def run_portfolio_backtest(
    portfolio_id: int,
    backtest_request: BacktestRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Run backtest for portfolio.
    
    - **portfolio_id**: Portfolio ID
    - **start_date**: Start date (YYYY-MM-DD)
    - **end_date**: End date (YYYY-MM-DD)
    - **benchmark**: Benchmark index code (default: "000300" for 沪深300)
    """
    try:
        # Get portfolio
        result = await db.execute(
            select(UserPortfolio).where(UserPortfolio.id == portfolio_id)
        )
        portfolio = result.scalar_one_or_none()
        
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Portfolio {portfolio_id} not found"
            )
        
        # Run backtest
        backtest_result = await run_backtest(
            fund_allocations=parse_json_field(portfolio.funds),
            start_date=backtest_request.start_date,
            end_date=backtest_request.end_date,
            benchmark=backtest_request.benchmark,
            db=db
        )
        
        # Calculate Brinson attribution
        brinson_result = None
        brinson_dict = None
        if backtest_result.benchmark_returns:
            try:
                portfolio_returns_list = [
                    {"date": r.date, "return_pct": r.return_pct, "nav": r.nav}
                    for r in backtest_result.portfolio_returns
                ]
                benchmark_returns_list = [
                    {"date": r.date, "return_pct": r.return_pct, "nav": r.nav}
                    for r in backtest_result.benchmark_returns
                ]
                
                brinson_dict = calculate_brinson_attribution(
                    portfolio_returns=portfolio_returns_list,
                    benchmark_returns=benchmark_returns_list,
                    fund_allocations=backtest_result.fund_performance
                )
                
                brinson_result = BrinsonAttribution(
                    allocation_effect=brinson_dict["allocation_effect"],
                    selection_effect=brinson_dict["selection_effect"],
                    interaction_effect=brinson_dict["interaction_effect"],
                    total_effect=brinson_dict["total_effect"]
                )
                
            except BrinsonAttributionError as e:
                logger.warning(f"Brinson attribution failed: {e}")
        
        # Save backtest result to database
        backtest_record = BacktestResultModel(
            portfolio_id=portfolio_id,
            start_date=backtest_request.start_date,
            end_date=backtest_request.end_date,
            portfolio_returns=[
                {"date": r.date, "return": r.return_pct, "nav": r.nav}
                for r in backtest_result.portfolio_returns
            ],
            benchmark_returns=[
                {"date": r.date, "return": r.return_pct, "nav": r.nav}
                for r in backtest_result.benchmark_returns
            ] if backtest_result.benchmark_returns else None,
            statistics={
                "total_return": backtest_result.statistics.total_return,
                "annual_return": backtest_result.statistics.annual_return,
                "max_drawdown": backtest_result.statistics.max_drawdown,
                "sharpe": backtest_result.statistics.sharpe_ratio,
                "volatility": backtest_result.statistics.volatility,
                "sortino_ratio": backtest_result.statistics.sortino_ratio,
                "calmar_ratio": backtest_result.statistics.calmar_ratio,
            },
            brinson_attribution=brinson_dict if brinson_result else None,
            created_at=datetime.utcnow()
        )
        
        db.add(backtest_record)
        await db.commit()
        await db.refresh(backtest_record)
        
        return build_backtest_response(backtest_record)
        
    except BacktestError as e:
        logger.error(f"Backtest failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Backtest failed: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run backtest: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run backtest: {str(e)}"
        )


@router.get("/{portfolio_id}/backtest", response_model=BacktestListResponse)
async def list_backtest_results(
    portfolio_id: int,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """
    List backtest results for portfolio.
    
    - **portfolio_id**: Portfolio ID
    - **skip**: Number of results to skip
    - **limit**: Maximum number of results to return
    """
    try:
        # Verify portfolio exists
        portfolio_result = await db.execute(
            select(UserPortfolio).where(UserPortfolio.id == portfolio_id)
        )
        if not portfolio_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Portfolio {portfolio_id} not found"
            )
        
        # Count total
        count_result = await db.execute(
            select(BacktestResultModel).where(BacktestResultModel.portfolio_id == portfolio_id)
        )
        total = len(count_result.scalars().all())
        
        # Fetch results
        result = await db.execute(
            select(BacktestResultModel)
            .where(BacktestResultModel.portfolio_id == portfolio_id)
            .order_by(desc(BacktestResultModel.created_at))
            .offset(skip)
            .limit(limit)
        )
        backtest_results = result.scalars().all()
        
        # Build response
        results_response = [build_backtest_response(bt) for bt in backtest_results]
        
        return BacktestListResponse(
            total=total,
            results=results_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list backtest results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list backtest results: {str(e)}"
        )


@router.get("/{portfolio_id}/backtest/{result_id}", response_model=BacktestDetailResponse)
async def get_backtest_result(
    portfolio_id: int,
    result_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed backtest result.
    
    - **portfolio_id**: Portfolio ID
    - **result_id**: Backtest result ID
    """
    try:
        # Get portfolio
        portfolio_result = await db.execute(
            select(UserPortfolio).where(UserPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()
        
        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Portfolio {portfolio_id} not found"
            )
        
        # Get backtest result
        result = await db.execute(
            select(BacktestResultModel).where(
                and_(
                    BacktestResultModel.id == result_id,
                    BacktestResultModel.portfolio_id == portfolio_id
                )
            )
        )
        bt = result.scalar_one_or_none()
        
        if not bt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest result {result_id} not found for portfolio {portfolio_id}"
            )
        
        # Build response
        result_response = build_backtest_response(bt)
        
        return BacktestDetailResponse(
            portfolio=PortfolioResponse(
                id=portfolio.id,
                name=portfolio.name,
                description=portfolio.description,
                funds=[FundAllocation(**f) for f in parse_json_field(portfolio.funds)],
                created_at=portfolio.created_at,
                updated_at=portfolio.updated_at
            ),
            result=result_response,
            fund_performance=[]  # Can be enhanced to show individual fund performance
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get backtest result: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get backtest result: {str(e)}"
        )


@router.delete("/{portfolio_id}/backtest/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_backtest_result(
    portfolio_id: int,
    result_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete backtest result.
    
    - **portfolio_id**: Portfolio ID
    - **result_id**: Backtest result ID
    """
    try:
        # Get backtest result
        result = await db.execute(
            select(BacktestResultModel).where(
                and_(
                    BacktestResultModel.id == result_id,
                    BacktestResultModel.portfolio_id == portfolio_id
                )
            )
        )
        bt = result.scalar_one_or_none()
        
        if not bt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest result {result_id} not found for portfolio {portfolio_id}"
            )
        
        await db.delete(bt)
        await db.commit()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete backtest result: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete backtest result: {str(e)}"
        )
