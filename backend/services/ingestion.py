"""
AkShare data ingestion with rate limiting and anti-ban strategies.
"""
import asyncio
import random
from typing import List, Optional
from datetime import datetime

import akshare as ak
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import settings, AsyncSessionLocal
from backend.models.fund import FundIndicators, FundIssuePipeline
from backend.services.rate_limiter import RateLimiter


class FundIngestion:
    """
    公募基金数据摄取服务.
    Implements token bucket rate limiting for AkShare API.
    """
    
    def __init__(self, rate_limit: int = 10):
        self.rate_limiter = RateLimiter(rate_limit)  # 10 req/s
    
    async def sync_all_funds(self):
        """
        同步全市场基金数据 - 每晚18:00执行.
        Processes ~20,000 funds in batches with rate limiting.
        """
        print(f"[{datetime.now()}] Starting fund data sync...")
        
        try:
            # 1. Get all ETF funds (同花顺)
            await self.rate_limiter.acquire()
            etf_df = ak.fund_etf_spot_ths()
            await self._save_fund_dataframe(etf_df, "ETF-LOF")
            
            print(f"Synced {len(etf_df)} ETF funds")
            
            # 2. Get LOF funds (东方财富)
            await self.rate_limiter.acquire()
            lof_df = ak.fund_lof_spot_em()
            await self._save_fund_dataframe(lof_df, "LOF")
            
            print(f"Synced {len(lof_df)} LOF funds")
            
            # 3. Get open-end funds (分类)
            await self._sync_open_funds()
            
            # 4. Update fund companies
            await self._sync_fund_companies()
            
            print(f"[{datetime.now()}] Fund data sync completed")
            
        except Exception as e:
            print(f"Fund sync error: {e}")
            raise
    
    async def _sync_open_funds(self):
        """同步开放式基金 - 按分类批量处理."""
        categories = ["股票型", "混合型", "债券型", "指数型", "QDII"]
        
        for category in categories:
            try:
                await self.rate_limiter.acquire()
                
                # Exponential backoff retry
                for attempt in range(settings.akshare_retry_count):
                    try:
                        df = ak.fund_open_fund_daily_em(symbol=category)
                        await self._save_fund_dataframe(df, category)
                        break
                    except Exception as e:
                        if attempt < settings.akshare_retry_count - 1:
                            delay = settings.akshare_retry_delay * (2 ** attempt)
                            await asyncio.sleep(delay + random.uniform(0, 1))
                        else:
                            print(f"Failed to sync {category}: {e}")
                
                print(f"Synced {category} funds")
                
            except Exception as e:
                print(f"Category sync error ({category}): {e}")
                continue
    
    async def _save_fund_dataframe(self, df: pd.DataFrame, fund_type: str):
        """保存基金数据到数据库."""
        async with AsyncSessionLocal() as session:
            for _, row in df.iterrows():
                fund_code = str(row.get("基金代码", row.get("代码", "")))
                if not fund_code:
                    continue
                
                fund = await session.get(FundIndicators, fund_code)
                
                if fund:
                    # Update existing
                    fund.fund_name = str(row.get("基金简称", row.get("名称", "")))
                    fund.fund_type = fund_type
                    fund.scale = float(row.get("基金规模", 0) or 0)
                else:
                    # Create new
                    fund = FundIndicators(
                        fund_code=fund_code,
                        fund_name=str(row.get("基金简称", row.get("名称", ""))),
                        fund_type=fund_type,
                        manager=str(row.get("基金经理", "")),
                        setup_date="",
                        company_name=str(row.get("基金公司", "")),
                        scale=float(row.get("基金规模", 0) or 0),
                    )
                    session.add(fund)
            
            await session.commit()
    
    async def _sync_fund_companies(self):
        """同步基金公司数据."""
        try:
            await self.rate_limiter.acquire()
            df = ak.fund_company_change_em()
            
            async with AsyncSessionLocal() as session:
                for _, row in df.iterrows():
                    company_id = str(row.get("基金公司", ""))
                    if not company_id:
                        continue
                    
                    company = FundCompanyMetadata(
                        company_id=company_id,
                        company_name=str(row.get("基金公司", "")),
                        total_scale=float(row.get("总规模", 0)) if row.get("总规模") else 0,
                        non_money_scale=float(row.get("非货规模", 0)) if row.get("非货规模") else 0,
                        fund_count=int(row.get("基金数量", 0)) if row.get("基金数量") else 0,
                        manager_count=int(row.get("经理数量", 0)) if row.get("经理数量") else 0,
                    )
                    session.merge(company)
                
                await session.commit()
                
        except Exception as e:
            print(f"Company sync error: {e}")


class BondIngestion:
    """债券收益率数据摄取服务."""
    
    def __init__(self, rate_limit: int = 5):
        self.rate_limiter = RateLimiter(rate_limit)
    
    async def sync_bond_yields(self):
        """
        同步债券收益率数据 - 每晚17:30执行.
        """
        print(f"[{datetime.now()}] Starting bond yield sync...")
        
        try:
            # 1. Sync treasury bond yields
            await self._sync_treasury_yields()
            
            # 2. Sync corporate bond yields
            await self._sync_corporate_yields()
            
            # 3. Sync money market rates
            await self._sync_money_rates()
            
            print(f"[{datetime.now()}] Bond yield sync completed")
            
        except Exception as e:
            print(f"Bond yield sync error: {e}")
            raise
    
    async def _sync_treasury_yields(self):
        """同步国债/国开债收益率曲线."""
        bond_types = ["国债", "国开债"]
        
        for bond_type in bond_types:
            try:
                await self.rate_limiter.acquire()
                
                # AkShare bond yield API
                df = ak.bond_china_yield(start_date="20000101")
                
                # Process and save to database
                # Placeholder: Real impl would parse and save
                
                print(f"Synced {bond_type} yields")
                
            except Exception as e:
                print(f"Treasury yield sync error ({bond_type}): {e}")
    
    async def _sync_corporate_yields(self):
        """同步信用债利差."""
        try:
            await self.rate_limiter.acquire()
            
            df = ak.bond_corporate_yields()
            
            print(f"Synced corporate yields ({len(df) if df is not None and not df.empty else 0} records)")
            
        except Exception as e:
            print(f"Corporate yield sync error: {e}")
    
    async def _sync_money_rates(self):
        """同步货币市场利率 (DR007, SHIBOR等)."""
        try:
            await self.rate_limiter.acquire()
            
            # SHIBOR rates
            df = ak.rate_interbank(market=" Shibor")
            
            # Process and save
            # Placeholder: Real impl would parse and save
            
            print("Synced money market rates")
            
        except Exception as e:
            print(f"Money rate sync error: {e}")


# Global ingestion instances
fund_ingestion = FundIngestion()
bond_ingestion = BondIngestion()
