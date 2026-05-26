"""
APScheduler service for nightly data ingestion.
"""
import asyncio
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from backend.core import settings


class SchedulerService:
    """
    APScheduler wrapper for managing scheduled data ingestion jobs.
    Uses SQLite for job persistence.
    """
    
    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._running = False
    
    async def start(self):
        """Start the scheduler with configured jobs."""
        if self._running:
            return
        
        # Configure job store (SQLite for persistence)
        jobstores = {
            "default": SQLAlchemyJobStore(
                url=f"sqlite:///{settings.database_path.replace('.db', '_jobs.db')}"
            )
        }
        
        self._scheduler = AsyncIOScheduler(jobstores=jobstores)
        
        # Add scheduled jobs
        self._add_jobs()
        
        # Start scheduler
        self._scheduler.start()
        self._running = True
    
    async def stop(self):
        """Stop the scheduler gracefully."""
        if not self._running or not self._scheduler:
            return
        
        self._scheduler.shutdown(wait=True)
        self._running = False
    
    def _add_jobs(self):
        """Add all scheduled jobs."""
        
        # Job 1: Fund data sync at 18:00
        self._scheduler.add_job(
            self._sync_fund_data,
            trigger=CronTrigger(hour=settings.fund_sync_hour, minute=0),
            id="fund_data_sync",
            name="公募基金数据同步",
            replace_existing=True,
            max_instances=1,
        )
        
        # Job 2: Bond yield sync at 17:30
        self._scheduler.add_job(
            self._sync_bond_yields,
            trigger=CronTrigger(hour=settings.bond_sync_hour, minute=30),
            id="bond_yield_sync",
            name="债券收益率数据同步",
            replace_existing=True,
            max_instances=1,
        )
        
        # Job 3: Index quotes refresh every 5 seconds during trading hours
        self._scheduler.add_job(
            self._refresh_index_quotes,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour="9-11,13-15",
                second=f"*/{settings.index_refresh_interval}",
            ),
            id="index_quotes_refresh",
            name="指数行情刷新",
            replace_existing=True,
            max_instances=1,
        )
    
    async def _sync_fund_data(self):
        """Sync fund data from AkShare."""
        from backend.services.ingestion import fund_ingestion
        try:
            await fund_ingestion.sync_all_funds()
        except Exception as e:
            print(f"Fund sync error: {e}")
    
    async def _sync_bond_yields(self):
        """Sync bond yield data."""
        from backend.services.ingestion import bond_ingestion
        try:
            await bond_ingestion.sync_bond_yields()
        except Exception as e:
            print(f"Bond yield sync error: {e}")
    
    async def _refresh_index_quotes(self):
        """Refresh real-time index quotes."""
        from backend.services.quotes import index_quotes
        try:
            await index_quotes.refresh()
        except Exception as e:
            print(f"Index quotes refresh error: {e}")
    
    @property
    def is_running(self) -> bool:
        return self._running


# Global scheduler instance
scheduler_service = SchedulerService()
