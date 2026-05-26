"""
Seed script for populating test data.
Run: python scripts/seed_data.py
"""
import asyncio
import random
from datetime import datetime, timedelta
from sqlalchemy import select

from backend.core.database import init_db_pragma, AsyncSessionLocal, async_engine, Base
from backend.models.fund import (
    FundIndicators,
    FundIssuePipeline,
    FundCompanyMetadata,
    MarketFearGreedSentimentHistory,
    BondEquityYieldSpreadHistory,
    IndexValuationHistory,
    MarketCrowdingValuationHistory,
    MarketStyleStrengthHistory,
)


async def seed_funds():
    """Seed fund indicators with mock data."""
    fund_types = ["股票型", "混合型", "债券型", "指数型", "ETF", "QDII", "FOF"]
    companies = ["华夏基金", "易方达基金", "嘉实基金", "南方基金", "广发基金", "博时基金"]
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(FundIndicators))
        existing = len(result.scalars().all())
        if existing > 0:
            print(f"Skipping funds: {existing} records already exist")
            return
            
        for i in range(100):
            fund = FundIndicators(
                fund_code=f"{random.randint(1, 9)}{random.randint(1000, 9999)}",
                fund_name=f"测试基金{i+1}号",
                fund_type=random.choice(fund_types),
                manager=f"经理{random.randint(1, 50)}",
                setup_date=f"2020-01-{random.randint(1, 28):02d}",
                setup_year=random.uniform(1, 10),
                scale=random.uniform(0.5, 100),
                company_name=random.choice(companies),
                return_1y=random.uniform(-30, 50),
                volatility_1y=random.uniform(5, 25),
                max_drawdown_1y=random.uniform(5, 40),
                sharpe_1y=random.uniform(-1, 3),
                heavy_sector=None,
            )
            session.add(fund)
        
        await session.commit()
        print("Seeded 100 fund records")


async def seed_fear_greed():
    """Seed fear/greed index history."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MarketFearGreedSentimentHistory))
        existing = len(result.scalars().all())
        if existing > 0:
            print(f"Skipping fear_greed: {existing} records already exist")
            return
        
        for i in range(30):
            date = datetime.now() - timedelta(days=i)
            score = random.uniform(10, 90)
            
            status = "极度恐惧" if score < 20 else "恐惧" if score < 40 else "中性" if score < 60 else "贪婪" if score < 80 else "极度贪婪"
            
            record = MarketFearGreedSentimentHistory(
                trade_date=date.strftime("%Y-%m-%d"),
                composite_score=score,
                sentiment_status=status,
                factor_volatility=random.uniform(0, 100),
                factor_safe_haven=random.uniform(0, 100),
                factor_margin_ratio=random.uniform(0, 100),
                factor_volume_deviation=random.uniform(0, 100),
                factor_futures_basis=random.uniform(0, 100),
                factor_stock_strength=random.uniform(0, 100),
            )
            session.add(record)
        
        await session.commit()
        print("Seeded 30 fear/greed records")


async def seed_index_valuation():
    """Seed index valuation history."""
    indices = ["000300", "000905", "399006"]
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(IndexValuationHistory))
        existing = len(result.scalars().all())
        if existing > 0:
            print(f"Skipping index_valuation: {existing} records already exist")
            return
        
        for index_code in indices:
            for i in range(100):
                date = datetime.now() - timedelta(days=i)
                
                record = IndexValuationHistory(
                    index_code=index_code,
                    trade_date=date.strftime("%Y-%m-%d"),
                    pe_ttm=random.uniform(8, 30),
                    percentile_rank_10y=random.uniform(0, 100),
                    moving_mean_10y=random.uniform(10, 20),
                    index_close_price=random.uniform(3000, 5000),
                )
                session.add(record)
        
        await session.commit()
        print("Seeded 300 index valuation records")


async def seed_erp_spread():
    """Seed ERP spread history."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BondEquityYieldSpreadHistory))
        existing = len(result.scalars().all())
        if existing > 0:
            print(f"Skipping erp_spread: {existing} records already exist")
            return
        
        for i in range(500):
            date = datetime.now() - timedelta(days=i)
            
            record = BondEquityYieldSpreadHistory(
                index_code="000300",
                trade_date=date.strftime("%Y-%m-%d"),
                pe_ttm=random.uniform(8, 15),
                treasury_yield_10y=random.uniform(2.0, 4.5),
                erp_spread=random.uniform(-3, 5),
                percentile_rank_10y=random.uniform(0, 100),
                index_close_price=random.uniform(3000, 5000),
            )
            session.add(record)
        
        await session.commit()
        print("Seeded 500 ERP spread records")


async def seed_style_strength():
    """Seed market style strength history."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MarketStyleStrengthHistory))
        existing = len(result.scalars().all())
        if existing > 0:
            print(f"Skipping style_strength: {existing} records already exist")
            return
        
        for i in range(100):
            date = datetime.now() - timedelta(days=i)
            
            record = MarketStyleStrengthHistory(
                trade_date=date.strftime("%Y-%m-%d"),
                index_code_num="000300",
                index_code_den="399006",
                ratio_value=random.uniform(0.8, 1.3),
                percentile_rank_3y=random.uniform(0, 100),
            )
            session.add(record)
        
        await session.commit()
        print("Seeded 100 style strength records")


async def seed_crowding():
    """Seed market crowding history."""
    sectors = ["银行", "非银金融", "食品饮料", "医药生物", "电子", "计算机", "电力设备", "汽车"]
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MarketCrowdingValuationHistory))
        existing = len(result.scalars().all())
        if existing > 0:
            print(f"Skipping crowding: {existing} records already exist")
            return
        
        for sector in sectors:
            for i in range(30):
                date = datetime.now() - timedelta(days=i)
                
                record = MarketCrowdingValuationHistory(
                    asset_code=sector,
                    trade_date=date.strftime("%Y-%m-%d"),
                    category="sector",
                    crowding_score=random.uniform(0, 100),
                    pe_percentile=random.uniform(0, 100),
                    close_price=random.uniform(100, 10000),
                )
                session.add(record)
        
        await session.commit()
        print("Seeded 240 crowding records")


async def seed_fund_issue():
    """Seed fund issue pipeline."""
    statuses = ["首发", "即将发售", "成立", "退市"]
    companies = ["华夏基金", "易方达基金", "嘉实基金", "南方基金", "广发基金"]
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(FundIssuePipeline))
        existing = len(result.scalars().all())
        if existing > 0:
            print(f"Skipping fund_issue: {existing} records already exist")
            return
        
        for i in range(50):
            start_date = datetime.now() + timedelta(days=random.randint(-30, 30))
            end_date = start_date + timedelta(days=random.randint(7, 30))
            
            record = FundIssuePipeline(
                fund_code=f"{random.randint(1, 9)}{random.randint(1000, 9999)}",
                fund_name=f"新发基金{i+1}号",
                company=random.choice(companies),
                subscribe_start_date=start_date.strftime("%Y-%m-%d"),
                subscribe_end_date=end_date.strftime("%Y-%m-%d"),
                status=random.choice(statuses),
                initial_scale=random.uniform(1, 50) if random.random() > 0.5 else None,
                delist_scale=None,
            )
            session.add(record)
        
        await session.commit()
        print("Seeded 50 fund issue records")


async def seed_fund_companies():
    """Seed fund company metadata."""
    companies = [
        ("华夏基金", "1998-04-09"),
        ("易方达基金", "2001-04-17"),
        ("嘉实基金", "1999-03-25"),
        ("南方基金", "1998-03-06"),
        ("广发基金", "2003-08-05"),
        ("博时基金", "1998-07-13"),
        ("招商基金", "2002-12-27"),
        ("汇添富基金", "2005-02-03"),
        ("富国基金", "1999-04-13"),
        ("工银瑞信基金", "2005-06-21"),
    ]
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(FundCompanyMetadata))
        existing = len(result.scalars().all())
        if existing > 0:
            print(f"Skipping fund_companies: {existing} records already exist")
            return
        
        for name, establish_date in companies:
            record = FundCompanyMetadata(
                company_id=name[:2] + str(random.randint(1000, 9999)),
                company_name=name,
                establish_date=establish_date,
                total_scale=random.uniform(1000, 15000),
                non_money_scale=random.uniform(500, 8000),
                fund_count=random.randint(50, 400),
                manager_count=random.randint(20, 150),
            )
            session.add(record)
        
        await session.commit()
        print("Seeded 10 fund company records")


async def main():
    """Run all seed functions."""
    # Initialize database
    init_db_pragma("data/alphaplus.db")
    
    # Create tables
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Seed data
    await seed_funds()
    await seed_fear_greed()
    await seed_index_valuation()
    await seed_erp_spread()
    await seed_style_strength()
    await seed_crowding()
    await seed_fund_issue()
    await seed_fund_companies()
    
    print("\nAll data seeding complete!")
    
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())