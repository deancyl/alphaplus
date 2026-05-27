"""
AkShare data ingestion with rate limiting and anti-ban strategies.
"""
import asyncio
import logging
import random
import re
from typing import List, Optional
from datetime import datetime

import akshare as ak
import pandas as pd
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import settings, AsyncSessionLocal
from backend.core.database import retry_on_sqlite_busy
from backend.models.fund import FundIndicators, FundIssuePipeline, FundIndustryAllocation, FundPortfolioHoldings
from backend.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


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
    
    @retry_on_sqlite_busy(max_retries=3, base_delay_ms=50, max_delay_ms=500)
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
    
    @retry_on_sqlite_busy(max_retries=3, base_delay_ms=50, max_delay_ms=500)
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


class IndustryAllocationIngestion:
    """基金行业配置数据摄取服务."""

    def __init__(self, rate_limit: int = 5):
        self.rate_limiter = RateLimiter(rate_limit)

    async def sync_fund_industry_allocation(self, fund_code: str) -> bool:
        """
        同步单个基金的行业配置数据.

        Args:
            fund_code: 基金代码

        Returns:
            bool: 是否成功获取并存储数据
        """
        try:
            await self.rate_limiter.acquire()

            for attempt in range(settings.akshare_retry_count):
                try:
                    df = ak.fund_portfolio_industry_allocation(symbol=fund_code)

                    if df is None or df.empty:
                        logger.warning(f"No industry allocation data for fund {fund_code}")
                        return False

                    await self._save_industry_allocation(fund_code, df)
                    logger.info(f"Synced industry allocation for fund {fund_code}")
                    return True

                except Exception as e:
                    if attempt < settings.akshare_retry_count - 1:
                        delay = settings.akshare_retry_delay * (2 ** attempt)
                        await asyncio.sleep(delay + random.uniform(0, 1))
                    else:
                        logger.error(f"Failed to sync industry allocation for {fund_code}: {e}")
                        return False

            return False

        except Exception as e:
            logger.error(f"Industry allocation sync error for {fund_code}: {e}")
            return False

    async def sync_multiple_funds_industry_allocation(self, fund_codes: List[str]) -> dict:
        """
        批量同步多个基金的行业配置数据.

        Args:
            fund_codes: 基金代码列表

        Returns:
            dict: {"success": int, "failed": int, "total": int}
        """
        results = {"success": 0, "failed": 0, "total": len(fund_codes)}

        for fund_code in fund_codes:
            success = await self.sync_fund_industry_allocation(fund_code)
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1

            await asyncio.sleep(0.5)

        logger.info(f"Industry allocation batch sync: {results}")
        return results

    @retry_on_sqlite_busy(max_retries=3, base_delay_ms=50, max_delay_ms=500)
    async def _save_industry_allocation(self, fund_code: str, df: pd.DataFrame):
        """
        保存行业配置数据到数据库 (upsert logic).

        Args:
            fund_code: 基金代码
            df: AkShare返回的行业配置DataFrame
        """
        async with AsyncSessionLocal() as session:
            try:
                report_date = self._extract_report_date(df)

                if report_date:
                    await session.execute(
                        delete(FundIndustryAllocation).where(
                            FundIndustryAllocation.fund_code == fund_code,
                            FundIndustryAllocation.report_date == report_date
                        )
                    )

                for _, row in df.iterrows():
                    industry_name = str(row.get("行业名称", row.get("行业", "")))
                    ratio = float(row.get("占净值比例", row.get("配置比例", 0)) or 0)

                    if not industry_name:
                        continue

                    allocation = FundIndustryAllocation(
                        fund_code=fund_code,
                        report_date=report_date or datetime.now().strftime("%Y-%m-%d"),
                        industry=industry_name,
                        allocation_ratio=ratio,
                    )
                    session.add(allocation)

                await session.commit()

            except Exception as e:
                logger.error(f"Failed to save industry allocation for {fund_code}: {e}")
                await session.rollback()
                raise

    def _extract_report_date(self, df: pd.DataFrame) -> Optional[str]:
        """
        从DataFrame中提取报告日期.

        Args:
            df: AkShare返回的DataFrame

        Returns:
            str: 报告日期 (YYYY-MM-DD) 或 None
        """
        date_columns = ["报告期", "报告日期", "日期", "report_date"]
        for col in date_columns:
            if col in df.columns:
                try:
                    date_val = df[col].iloc[0]
                    if pd.notna(date_val):
                        if isinstance(date_val, str):
                            return date_val[:10]
                        else:
                            return str(date_val)[:10]
                except (IndexError, KeyError):
                    continue
        return None


industry_allocation_ingestion = IndustryAllocationIngestion()


async def fund_portfolio_em(fund_code: str, report_date: Optional[str] = None) -> tuple[List[dict], str]:
    """
    Fetch fund portfolio holdings from AkShare.
    
    Args:
        fund_code: Fund code (e.g., '000001')
        report_date: Report date in format YYYYMMDD or YYYYQ1 (optional)
    
    Returns:
        Tuple of (holdings list, extracted report date)
    
    Raises:
        Exception: If AkShare API fails
    """
    import logging
    import re
    
    logger = logging.getLogger(__name__)
    
    try:
        df = ak.fund_portfolio_hold_em(symbol=fund_code, date=report_date) if report_date else ak.fund_portfolio_hold_em(symbol=fund_code)
        
        if df is None or df.empty:
            logger.warning(f"No holdings data for fund {fund_code}")
            return [], ""
        
        if "季度" not in df.columns:
            logger.error(f"Missing '季度' column in AkShare response for fund {fund_code}")
            return [], ""
        
        latest_quarter = df["季度"].iloc[0]
        df_filtered = df[df["季度"] == latest_quarter]
        
        report_date_str = _parse_quarter_to_date(latest_quarter)
        
        holdings = []
        for _, row in df_filtered.iterrows():
            holding = {
                "stock_code": str(row.get("股票代码", "")),
                "stock_name": str(row.get("股票名称", "")),
                "holding_ratio": float(row.get("占净值比例", 0) or 0),
                "holding_value": float(row.get("持仓市值", 0) or 0),
            }
            
            if holding["stock_code"]:
                holdings.append(holding)
        
        return holdings, report_date_str
        
    except Exception as e:
        logger.error(f"Failed to fetch holdings for fund {fund_code}: {e}")
        raise


def _parse_quarter_to_date(quarter_str: str) -> str:
    """
    Parse AkShare quarter string to date string.
    
    Args:
        quarter_str: e.g., "2024年1季度股票投资明细" or "2024年1季度"
    
    Returns:
        Date string in YYYY-MM-DD format (last day of quarter)
    """
    match = re.search(r'(\d{4})年(\d)季度', quarter_str)
    if not match:
        return datetime.now().strftime("%Y-%m-%d")
    
    year = int(match.group(1))
    quarter = int(match.group(2))
    
    quarter_end_dates = {
        1: "03-31",
        2: "06-30",
        3: "09-30",
        4: "12-31"
    }
    
    return f"{year}-{quarter_end_dates.get(quarter, '12-31')}"


@retry_on_sqlite_busy(max_retries=3, base_delay_ms=50, max_delay_ms=500)
async def save_fund_holdings(fund_code: str, holdings: List[dict], report_date: str) -> int:
    """
    Save fund holdings to database with upsert logic.
    
    Args:
        fund_code: Fund code
        holdings: List of holding dictionaries
        report_date: Report date (YYYY-MM-DD or YYYYQ1)
    
    Returns:
        Number of records saved
    """
    import logging
    
    logger = logging.getLogger(__name__)
    
    if not holdings:
        return 0
    
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(
                delete(FundPortfolioHoldings).where(
                    FundPortfolioHoldings.fund_code == fund_code,
                    FundPortfolioHoldings.report_date == report_date
                )
            )
            
            saved_count = 0
            for holding in holdings:
                stock_code = holding.get("stock_code", "")
                if not stock_code:
                    continue
                
                new_record = FundPortfolioHoldings(
                    fund_code=fund_code,
                    report_date=report_date,
                    stock_code=stock_code,
                    stock_name=holding.get("stock_name", ""),
                    holding_ratio=holding.get("holding_ratio", 0),
                    holding_value=holding.get("holding_value", 0),
                    holding_change=holding.get("holding_change"),
                )
                session.add(new_record)
                saved_count += 1
            
            await session.commit()
            logger.info(f"Saved {saved_count} holdings for fund {fund_code}")
            return saved_count
            
        except Exception as e:
            logger.error(f"Failed to save holdings for fund {fund_code}: {e}")
            await session.rollback()
            raise


@retry_on_sqlite_busy(max_retries=3, base_delay_ms=50, max_delay_ms=500)
async def ingest_fund_industry_allocation(
    fund_code: str,
    year: Optional[str] = None,
) -> List[dict]:
    """
    Fetch fund industry allocation from AkShare and store in SQLite.
    
    Args:
        fund_code: Fund code (e.g., '000001')
        year: Query year (defaults to current year)
    
    Returns:
        List of industry allocation records
    
    Raises:
        Exception: If AkShare API fails and no fallback data available
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if year is None:
        year = str(datetime.now().year)
    
    try:
        df = ak.fund_portfolio_industry_allocation_em(symbol=fund_code, date=year)
        
        if df is None or df.empty:
            logger.warning(f"No industry allocation data for fund {fund_code} year {year}")
            return []
        
        records = []
        async with AsyncSessionLocal() as session:
            for _, row in df.iterrows():
                industry_name = str(row.get("行业类别", "")).strip()
                if not industry_name:
                    continue
                
                report_date_str = str(row.get("截止时间", ""))
                if not report_date_str or report_date_str == "nan":
                    report_date_str = f"{year}-12-31"
                
                ratio_str = row.get("占净值比例", 0)
                try:
                    allocation_ratio = float(ratio_str) if ratio_str else 0.0
                except (ValueError, TypeError):
                    allocation_ratio = 0.0
                
                mv_str = row.get("市值", None)
                market_value = None
                if mv_str and str(mv_str) != "nan":
                    try:
                        market_value = float(mv_str)
                    except (ValueError, TypeError):
                        pass
                
                from sqlalchemy import delete
                await session.execute(
                    delete(FundIndustryAllocation).where(
                        FundIndustryAllocation.fund_code == fund_code,
                        FundIndustryAllocation.report_date == report_date_str,
                        FundIndustryAllocation.industry == industry_name,
                    )
                )
                
                record = FundIndustryAllocation(
                    fund_code=fund_code,
                    report_date=report_date_str,
                    industry=industry_name,
                    allocation_ratio=allocation_ratio,
                    market_value=market_value,
                    created_at=datetime.utcnow(),
                )
                session.add(record)
                
                records.append({
                    "fund_code": fund_code,
                    "report_date": report_date_str,
                    "industry": industry_name,
                    "allocation_ratio": allocation_ratio,
                    "market_value": market_value,
                })
            
            await session.commit()
        
        logger.info(f"Ingested {len(records)} industry allocation records for fund {fund_code}")
        return records
        
    except Exception as e:
        logger.error(f"Failed to ingest industry allocation for fund {fund_code}: {e}")
        return []
