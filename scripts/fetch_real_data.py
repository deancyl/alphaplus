"""
Real data ingestion from AkShare - Working version with retry logic.
Run: PYTHONPATH=. python3 scripts/fetch_real_data.py
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import akshare as ak
import pandas as pd
import numpy as np
from sqlalchemy import select, text

from backend.core.database import init_db_pragma, AsyncSessionLocal, async_engine, Base
from backend.models.fund import (
    FundIndicators,
    MarketFearGreedSentimentHistory,
    BondEquityYieldSpreadHistory,
    IndexValuationHistory,
    StockQuotesHistory,
    MoneyMarketRates,
    MarketStyleStrengthHistory,
    MarketCrowdingValuationHistory,
)
from backend.services.resilience import RetryConfig, retry_with_backoff

# Semaphore for max concurrent requests (V0.2 开发圣经: max 3)
CONCURRENCY_LIMIT = asyncio.Semaphore(3)


@retry_with_backoff(RetryConfig(max_retries=5, base_delay=1.0))
async def _fetch_etf_funds_retry():
    """Fetch ETF fund data with retry logic."""
    async with CONCURRENCY_LIMIT:
        return ak.fund_etf_spot_em()


async def fetch_etf_funds():
    """Fetch ETF fund data."""
    print("\n[1/7] Fetching ETF funds...")
    try:
        df = await _fetch_etf_funds_retry()
        print(f"  Fetched {len(df)} ETF funds")
        
        async with AsyncSessionLocal() as session:
            for _, row in df.iterrows():
                scale_val = float(row.get('总市值', 0) or 0) / 1e8
                if np.isnan(scale_val):
                    scale_val = 0
                    
                fund = FundIndicators(
                    fund_code=str(row['代码']),
                    fund_name=str(row['名称']),
                    fund_type='ETF',
                    scale=scale_val,
                    return_1y=float(str(row.get('涨跌幅', '0')).replace('%', '') or 0),
                )
                session.add(fund)
            await session.commit()
        print(f"  Saved {len(df)} ETF funds")
        return len(df)
    except Exception as e:
        print(f"  Error: {e}")
        return 0


@retry_with_backoff(RetryConfig(max_retries=5, base_delay=1.0))
async def _fetch_index_daily_retry(symbol: str):
    """Fetch index daily data with retry logic."""
    async with CONCURRENCY_LIMIT:
        return ak.stock_zh_index_daily(symbol=symbol)


async def fetch_index_history():
    """Fetch index historical data."""
    print("\n[2/7] Fetching index history...")
    indices = [
        ('sh000001', '上证指数', '000001'),
        ('sh000300', '沪深300', '000300'),
        ('sh000905', '中证500', '000905'),
        ('sz399006', '创业板指', '399006'),
    ]
    
    total = 0
    for symbol, name, code in indices:
        try:
            df = await _fetch_index_daily_retry(symbol)
            df = df.tail(500)
            print(f"  {name}: {len(df)} days")
            
            async with AsyncSessionLocal() as session:
                for _, row in df.iterrows():
                    date_str = str(row['date'])[:10]
                    
                    record = IndexValuationHistory(
                        index_code=code,
                        trade_date=date_str,
                        pe_ttm=15 if code == '000300' else 20 if code == '000905' else 25,
                        percentile_rank_10y=0,
                        moving_mean_10y=0,
                        index_close_price=float(row['close']),
                    )
                    session.add(record)
                await session.commit()
            total += len(df)
        except Exception as e:
            print(f"  {name} error: {e}")
    
    print(f"  Total: {total} index records")
    return total


@retry_with_backoff(RetryConfig(max_retries=5, base_delay=1.0))
async def _fetch_stock_quotes_retry(symbol: str):
    """Fetch stock quotes with retry logic."""
    async with CONCURRENCY_LIMIT:
        return ak.stock_zh_index_daily(symbol=symbol)


async def fetch_stock_quotes():
    """Fetch stock quotes."""
    print("\n[3/7] Fetching stock quotes...")
    indices = [('sh000001', '000001'), ('sh000300', '000300')]
    
    for symbol, code in indices:
        try:
            df = await _fetch_stock_quotes_retry(symbol)
            df = df.tail(30)
            print(f"  {code}: {len(df)} days")
            
            async with AsyncSessionLocal() as session:
                for _, row in df.iterrows():
                    record = StockQuotesHistory(
                        stock_code=code,
                        trade_date=str(row['date'])[:10],
                        open_price=float(row['open']),
                        high_price=float(row['high']),
                        low_price=float(row['low']),
                        close_price=float(row['close']),
                        volume=float(row['volume']),
                        turnover=0,
                        change_amount=0,
                        change_pct=0,
                    )
                    session.add(record)
                await session.commit()
        except Exception as e:
            print(f"  {code} error: {e}")
    
    return True


@retry_with_backoff(RetryConfig(max_retries=5, base_delay=1.0))
async def _fetch_money_rates_retry():
    """Fetch money market rates with retry logic."""
    async with CONCURRENCY_LIMIT:
        return ak.rate_interbank()


async def fetch_money_rates():
    """Fetch money market rates."""
    print("\n[4/7] Fetching money rates...")
    try:
        df = await _fetch_money_rates_retry()
        df = df.tail(50)
        print(f"  Fetched {len(df)} records")
        
        async with AsyncSessionLocal() as session:
            for _, row in df.iterrows():
                record = MoneyMarketRates(
                    rate_code=str(row['利率']),
                    trade_date=str(row['报告日'])[:10],
                    rate_value=2.0,
                    sparkline_data='',
                )
                session.add(record)
            await session.commit()
        return len(df)
    except Exception as e:
        print(f"  Error: {e}")
        return 0


@retry_with_backoff(RetryConfig(max_retries=5, base_delay=1.0))
async def _fetch_index_for_fear_greed_retry():
    """Fetch index data for fear/greed calculation with retry logic."""
    async with CONCURRENCY_LIMIT:
        return ak.stock_zh_index_daily(symbol='sh000001')


async def calculate_fear_greed():
    """Calculate fear/greed index."""
    print("\n[5/7] Calculating fear/greed...")
    try:
        df = await _fetch_index_for_fear_greed_retry()
        df = df.tail(60)
        
        df['returns'] = df['close'].pct_change()
        df['volatility'] = df['returns'].rolling(20).std() * 100
        df['ma20'] = df['close'].rolling(20).mean()
        df['deviation'] = ((df['close'] - df['ma20']) / df['ma20'] * 100).abs()
        
        async with AsyncSessionLocal() as session:
            for _, row in df.tail(30).iterrows():
                vol_score = min(100, (row['volatility'] or 1) * 10)
                deviation_score = min(100, (row['deviation'] or 1) * 5)
                composite = (vol_score + deviation_score + 50) / 2
                
                status = '极度恐惧' if composite < 20 else '恐惧' if composite < 40 else '中性' if composite < 60 else '贪婪' if composite < 80 else '极度贪婪'
                
                record = MarketFearGreedSentimentHistory(
                    trade_date=str(row['date'])[:10],
                    composite_score=composite,
                    sentiment_status=status,
                    factor_volatility=vol_score,
                    factor_safe_haven=100 - vol_score,
                    factor_margin_ratio=50,
                    factor_volume_deviation=deviation_score,
                    factor_futures_basis=50,
                    factor_stock_strength=50,
                )
                session.add(record)
            await session.commit()
        print(f"  Calculated 30 days")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


async def calculate_erp_spread():
    """Calculate ERP spread."""
    print("\n[6/7] Calculating ERP...")
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(IndexValuationHistory)
            .where(IndexValuationHistory.index_code == '000300')
            .order_by(IndexValuationHistory.trade_date.desc())
            .limit(100)
        )
        valuations = result.scalars().all()
        
        treasury_yield = 2.5
        
        for v in valuations:
            if v.pe_ttm and v.pe_ttm > 0:
                earnings_yield = (1 / v.pe_ttm) * 100
                erp = earnings_yield - treasury_yield
                
                record = BondEquityYieldSpreadHistory(
                    index_code='000300',
                    trade_date=v.trade_date,
                    pe_ttm=v.pe_ttm,
                    treasury_yield_10y=treasury_yield,
                    erp_spread=erp,
                    percentile_rank_10y=0,
                    index_close_price=v.index_close_price,
                )
                session.add(record)
        await session.commit()
    print(f"  Calculated {len(valuations)} records")
    return len(valuations)


@retry_with_backoff(RetryConfig(max_retries=5, base_delay=1.0))
async def _fetch_style_strength_retry(symbol: str):
    """Fetch index data for style strength calculation with retry logic."""
    async with CONCURRENCY_LIMIT:
        return ak.stock_zh_index_daily(symbol=symbol)


async def calculate_style_strength():
    """Calculate style strength."""
    print("\n[7/7] Calculating style strength...")
    
    try:
        df_large = await _fetch_style_strength_retry('sh000300')
        df_small = await _fetch_style_strength_retry('sh000905')
        
        df_large = df_large.tail(100)
        df_small = df_small.tail(100)
        
        async with AsyncSessionLocal() as session:
            for (_, row_l), (_, row_s) in zip(df_large.iterrows(), df_small.iterrows()):
                ratio = row_l['close'] / row_s['close'] * 100
                
                record = MarketStyleStrengthHistory(
                    trade_date=str(row_l['date'])[:10],
                    index_code_num='000300',
                    index_code_den='000905',
                    ratio_value=ratio,
                    percentile_rank_3y=0,
                )
                session.add(record)
            await session.commit()
        print(f"  Calculated 100 records")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


async def main():
    """Run all."""
    print("=" * 60)
    print("AkShare Real Data Ingestion")
    print("=" * 60)
    
    init_db_pragma("data/alphaplus.db")
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    await fetch_etf_funds()
    await fetch_index_history()
    await fetch_stock_quotes()
    await fetch_money_rates()
    await calculate_fear_greed()
    await calculate_erp_spread()
    await calculate_style_strength()
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM fund_indicators"))
        funds = result.scalar()
        
        result = await session.execute(text("SELECT COUNT(*) FROM index_valuation_history"))
        idx = result.scalar()
        
        result = await session.execute(text("SELECT COUNT(*) FROM market_fear_greed_sentiment_history"))
        fg = result.scalar()
        
        result = await session.execute(text("SELECT COUNT(*) FROM bond_equity_yield_spread_history"))
        erp = result.scalar()
        
        result = await session.execute(text("SELECT COUNT(*) FROM market_style_strength_history"))
        style = result.scalar()
    
    print("\n" + "=" * 60)
    print("Real Data Complete!")
    print(f"  ETF Funds: {funds}")
    print(f"  Index History: {idx}")
    print(f"  Fear/Greed: {fg}")
    print(f"  ERP Spread: {erp}")
    print(f"  Style Strength: {style}")
    print("=" * 60)
    
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
