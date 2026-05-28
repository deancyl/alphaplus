"""
APScheduler service for nightly data ingestion.

Delegates task execution to isolated worker process via ProcessManager
to avoid OOM on large ETL operations.
"""
import asyncio
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from backend.core import settings
from backend.core.process_manager import get_process_manager


class SchedulerService:
    """
    APScheduler wrapper for managing scheduled data ingestion jobs.
    
    Uses isolated worker process for task execution to provide:
    - Memory isolation (large ETL doesn't OOM FastAPI)
    - Crash isolation (worker failure doesn't affect API)
    - Automatic restart on failure
    """
    
    def __init__(self):
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._running = False
    
    async def start(self):
        """Start the scheduler with configured jobs."""
        if self._running:
            return
        
        jobstores = {
            "default": SQLAlchemyJobStore(
                url=f"sqlite:///{settings.database_path.replace('.db', '_jobs.db')}"
            )
        }
        
        self._scheduler = AsyncIOScheduler(jobstores=jobstores)
        
        self._add_jobs()
        
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
        assert self._scheduler is not None, "Scheduler must be initialized"
        
        self._scheduler.add_job(
            self._refresh_pandas_cache,
            trigger=CronTrigger(hour=17, minute=0),
            id="pandas_cache_refresh",
            name="Pandas缓存刷新",
            replace_existing=True,
            max_instances=1,
        )
        
        self._scheduler.add_job(
            self._sync_fund_data,
            trigger=CronTrigger(hour=settings.fund_sync_hour, minute=0),
            id="fund_data_sync",
            name="公募基金数据同步",
            replace_existing=True,
            max_instances=1,
        )
        
        self._scheduler.add_job(
            self._sync_bond_yields,
            trigger=CronTrigger(hour=settings.bond_sync_hour, minute=30),
            id="bond_yield_sync",
            name="债券收益率数据同步",
            replace_existing=True,
            max_instances=1,
        )
        
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
        
        self._scheduler.add_job(
            self._quarterly_holdings_ingestion,
            trigger=CronTrigger(
                month="1,4,7,10",
                day="16-31",
                hour=2,
                minute=0,
            ),
            id="quarterly_holdings_ingestion",
            name="季度持仓数据摄入",
            replace_existing=True,
            max_instances=1,
        )
    
    async def _schedule_worker_task(self, task_type: str, payload: Optional[dict] = None):
        """Schedule a task to be executed by the isolated worker process."""
        try:
            process_manager = get_process_manager()
            actual_payload = payload or {}
            actual_payload['task_type'] = task_type
            
            task_id = process_manager.schedule_task(
                task_type=task_type,
                payload=actual_payload,
                priority=0
            )
            print(f"Scheduled worker task: {task_id} (type={task_type})")
            return task_id
        except Exception as e:
            print(f"Failed to schedule worker task: {e}")
            return None
    
    async def _refresh_pandas_cache(self):
        """Refresh Pandas in-memory cache - delegate to worker."""
        await self._schedule_worker_task('pandas_cache_refresh')
    
    async def _sync_fund_data(self):
        """Sync fund data from AkShare - delegate to worker."""
        await self._schedule_worker_task('fund_sync')
    
    async def _sync_bond_yields(self):
        """Sync bond yield data - delegate to worker."""
        await self._schedule_worker_task('bond_sync')
    
    async def _refresh_index_quotes(self):
        """Refresh real-time index quotes - delegate to worker."""
        await self._schedule_worker_task('index_refresh')
    
    async def _quarterly_holdings_ingestion(self):
        """Quarterly holdings ingestion - delegate to worker."""
        await self._schedule_worker_task('holdings_ingestion')
    
    @property
    def is_running(self) -> bool:
        return self._running


scheduler_service = SchedulerService()
