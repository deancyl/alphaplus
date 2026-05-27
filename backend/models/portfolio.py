"""
SQLAlchemy models for portfolio and backtest tables.
Based on existing patterns in backend/models/fund.py
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import String, Integer, Text, DateTime, Date, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import JSON

from backend.core.database import Base


# ==================== Portfolio Module Tables ====================

class UserPortfolio(Base):
    """用户组合表 - User FOF portfolio management."""
    __tablename__ = "user_portfolio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    funds: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)  # [{"fund_code": "000001", "weight": 0.3}, ...]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to backtest results
    backtest_results = relationship("BacktestResult", back_populates="portfolio", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_portfolio_created", "created_at"),
    )


class BacktestResult(Base):
    """回测结果表 - Backtest results with statistics and Brinson attribution."""
    __tablename__ = "backtest_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_portfolio.id", ondelete="CASCADE"), nullable=False)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    portfolio_returns: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)  # [{date, return, nav}, ...]
    benchmark_returns: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)  # [{date, return, nav}, ...]
    statistics: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)  # {"total_return", "annual_return", "max_drawdown", "sharpe", "volatility"}
    brinson_attribution: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # {"allocation_effect", "selection_effect", "interaction_effect", "total_effect"}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship to portfolio
    portfolio = relationship("UserPortfolio", back_populates="backtest_results")

    __table_args__ = (
        Index("idx_backtest_portfolio", "portfolio_id", "created_at"),
    )
