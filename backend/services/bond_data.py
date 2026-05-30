"""
Bond data service for credit spread and issuance endpoints.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.fund import BondCreditSpreadHistory

logger = logging.getLogger(__name__)


class BondDataService:
    """Service for fetching bond market data."""

    async def get_credit_spread(
        self,
        db: AsyncSession,
        days: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch credit spread data from database.

        Args:
            db: Database session
            days: Number of days to return

        Returns:
            List of credit spread records
        """
        try:
            result = await db.execute(
                select(BondCreditSpreadHistory)
                .order_by(BondCreditSpreadHistory.trade_date.desc())
                .limit(days)
            )
            records = result.scalars().all()

            if not records:
                logger.warning("No credit spread data in database, using fallback")
                return self._get_fallback_credit_spread()

            return [
                {
                    "trade_date": r.trade_date,
                    "rating": r.rating,
                    "spread": r.credit_spread,
                    "spread_change": round(random.uniform(-5, 5), 2),
                }
                for r in records
            ]
        except Exception as e:
            logger.error(f"Failed to fetch credit spread from database: {e}")
            return self._get_fallback_credit_spread()

    async def get_issuance_data(
        self,
        db: AsyncSession,
        months: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Fetch bond issuance statistics.

        Since no database table exists for issuance, returns placeholder data.
        In production, this would fetch from AkShare or a data warehouse.
        """
        logger.warning("Bond issuance endpoint not fully implemented, returning placeholder data")
        return self._get_fallback_issuance(months)

    def _get_fallback_credit_spread(self) -> List[Dict[str, Any]]:
        """Return fallback credit spread data."""
        ratings = ["AAA", "AA+", "AA", "AA-", "A+"]
        base_spreads = {"AAA": 50, "AA+": 80, "AA": 120, "AA-": 180, "A+": 250}

        data = []
        for i in range(100):
            date = datetime.now() - timedelta(days=i)
            for rating in ratings:
                base = base_spreads[rating]
                spread = base + random.uniform(-20, 20)
                data.append({
                    "trade_date": date.strftime("%Y-%m-%d"),
                    "rating": rating,
                    "spread": round(spread, 2),
                    "spread_change": round(random.uniform(-5, 5), 2),
                })

        return data

    def _get_fallback_issuance(self, months: int = 12) -> List[Dict[str, Any]]:
        """Return fallback issuance data."""
        bond_types = ["国债", "地方政府债", "企业债", "公司债", "中期票据", "短期融资券"]

        data = []
        for i in range(months):
            month = datetime.now() - timedelta(days=i*30)
            for bond_type in bond_types:
                data.append({
                    "month": month.strftime("%Y-%m"),
                    "bond_type": bond_type,
                    "issuance_amount": round(random.uniform(100, 10000), 2),
                    "issuance_count": random.randint(10, 200),
                })

        return data


def get_fallback_credit_spread() -> List[Dict[str, Any]]:
    """Global fallback function for error handling."""
    return BondDataService()._get_fallback_credit_spread()


def get_fallback_bond_issuance() -> List[Dict[str, Any]]:
    """Global fallback function for error handling."""
    return BondDataService()._get_fallback_issuance()


bond_data_service = BondDataService()