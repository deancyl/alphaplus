"""
Tests for database models and operations.
"""
import pytest
from sqlalchemy import select

from backend.core.database import Base, async_engine, AsyncSessionLocal, init_db_pragma
from backend.models.fund import FundIndicators, MarketFearGreedSentimentHistory


@pytest.fixture(autouse=True)
async def setup_db():
    """Setup test database."""
    init_db_pragma(":memory:")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await async_engine.dispose()


@pytest.mark.asyncio
async def test_create_fund():
    """Test creating a fund record."""
    async with AsyncSessionLocal() as session:
        fund = FundIndicators(
            fund_code="000001",
            fund_name="测试基金",
            fund_type="股票型",
            manager="张三",
            setup_date="2020-01-01",
            company_name="华夏基金",
        )
        session.add(fund)
        await session.commit()
        
        # Query back
        result = await session.execute(
            select(FundIndicators).where(FundIndicators.fund_code == "000001")
        )
        saved = result.scalar_one()
        assert saved.fund_name == "测试基金"
        assert saved.fund_type == "股票型"


@pytest.mark.asyncio
async def test_create_fear_greed():
    """Test creating fear/greed record."""
    async with AsyncSessionLocal() as session:
        record = MarketFearGreedSentimentHistory(
            trade_date="2024-01-15",
            composite_score=45.5,
            sentiment_status="中性",
        )
        session.add(record)
        await session.commit()
        
        # Query back
        result = await session.execute(
            select(MarketFearGreedSentimentHistory).where(
                MarketFearGreedSentimentHistory.trade_date == "2024-01-15"
            )
        )
        saved = result.scalar_one()
        assert saved.composite_score == 45.5
        assert saved.sentiment_status == "中性"
