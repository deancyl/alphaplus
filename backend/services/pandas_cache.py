"""
Pandas in-memory cache for sub-10ms fund filtering performance.
Uses singleton pattern for GLOBAL_FUND_DF loaded on startup.
"""
import time
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from backend.core.database import DB_PATH, SYNC_DATABASE_URL
from backend.core.config import settings


logger = logging.getLogger(__name__)


# ==================== Global Singleton DataFrame ====================

class FundCache:
    """
    Singleton cache for fund indicators DataFrame.
    Thread-safe lazy initialization with refresh capability.
    """
    _instance: Optional['FundCache'] = None
    _df: Optional[pd.DataFrame] = None
    _last_refresh: Optional[float] = None
    _lock = False  # Simple lock for refresh operations
    
    # Columns to load (only filter/display columns to minimize memory)
    COLUMNS = [
        'fund_code', 'fund_name', 'fund_type', 'manager',
        'setup_date', 'setup_year', 'scale', 'company_name',
        'return_1y', 'volatility_1y', 'max_drawdown_1y', 'sharpe_1y',
        'heavy_sector'
    ]
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def df(self) -> pd.DataFrame:
        """Get cached DataFrame, initializing if needed."""
        if self._df is None:
            self._load_cache()
        assert self._df is not None  # Load ensures _df is set
        return self._df
    
    def _load_cache(self) -> None:
        """Load fund_indicators table into memory."""
        if self._lock:
            logger.warning("Cache refresh already in progress, skipping")
            return
        
        try:
            self._lock = True
            start_time = time.time()
            
            # Use sync engine for Pandas read_sql
            engine = create_engine(SYNC_DATABASE_URL)
            
            # Load only necessary columns
            query = f"""
                SELECT {', '.join(self.COLUMNS)}
                FROM fund_indicators
            """
            
            self._df = pd.read_sql(query, engine)
            
            # Optimize dtypes for memory efficiency
            self._df = self._optimize_dtypes(self._df)
            
            # Create lowercase fund_name column for case-insensitive search
            self._df['fund_name_lower'] = self._df['fund_name'].str.lower()
            
            self._last_refresh = time.time()
            
            elapsed_ms = (time.time() - start_time) * 1000
            memory_mb = self._df.memory_usage(deep=True).sum() / 1024 / 1024
            
            logger.info(
                f"Fund cache loaded: {len(self._df)} funds, "
                f"{memory_mb:.2f} MB, {elapsed_ms:.2f} ms"
            )
            
            engine.dispose()
            
        except Exception as e:
            logger.error(f"Failed to load fund cache: {e}")
            if self._df is None:
                # Initialize empty DataFrame to prevent repeated failures
                self._df = pd.DataFrame(columns=list(self.COLUMNS))
            raise
        finally:
            self._lock = False
    
    def _optimize_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Optimize DataFrame dtypes to reduce memory usage."""
        # String columns -> category for low cardinality
        for col in ['fund_type', 'company_name', 'heavy_sector']:
            if col in df.columns:
                df[col] = df[col].astype('category')
        
        # Float columns -> float32 (sufficient precision for financial metrics)
        float_cols = ['setup_year', 'scale', 'return_1y', 'volatility_1y', 
                      'max_drawdown_1y', 'sharpe_1y']
        for col in float_cols:
            if col in df.columns:
                df[col] = df[col].astype('float32')
        
        return df
    
    def refresh_cache(self) -> Dict[str, Any]:
        """Force reload from database."""
        logger.info("Refreshing fund cache...")
        self._df = None
        self._load_cache()
        return self.get_cache_stats()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        if self._df is None:
            return {
                "status": "not_loaded",
                "row_count": 0,
                "memory_mb": 0,
                "last_refresh": None,
            }
        
        memory_bytes = self._df.memory_usage(deep=True).sum()
        
        return {
            "status": "loaded",
            "row_count": len(self._df),
            "memory_mb": round(memory_bytes / 1024 / 1024, 2),
            "last_refresh": self._last_refresh,
            "columns": list(self._df.columns),
        }


# Global singleton instance
GLOBAL_FUND_DF = FundCache()


# ==================== Pandas Filter Service ====================

class PandasFilterService:
    """
    High-performance fund filtering using Pandas boolean indexing.
    Target: <10ms for 26K funds.
    """
    
    def __init__(self, cache: Optional[FundCache] = None):
        self.cache = cache or GLOBAL_FUND_DF
    
    def filter_funds(
        self,
        conditions: Dict[str, Any],
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "return_1y",
        sort_order: str = "desc",
    ) -> tuple[pd.DataFrame, int]:
        """
        Filter funds using vectorized Pandas operations.
        
        Args:
            conditions: Dict with filter conditions:
                - fund_types: List[str] - fund_type in list
                - scale_min, scale_max: float - scale range
                - return_1y_min, return_1y_max: float - return range
                - setup_year_min, setup_year_max: float - year range
                - company_names: List[str] - company filter
                - max_drawdown_1y_max: float - max drawdown filter
                - sharpe_1y_min: float - sharpe filter
                - fund_name_search: str - full-text search on fund_name
            page: Page number (1-indexed)
            page_size: Results per page
            sort_by: Column to sort by
            sort_order: 'asc' or 'desc'
        
        Returns:
            Tuple of (filtered DataFrame, total count)
        """
        start_time = time.time()
        
        df = self.cache.df
        
        # Build boolean mask using vectorized operations (no copy yet)
        mask = pd.Series([True] * len(df), index=df.index)
        
        # fund_type filter (isin)
        if conditions.get('fund_types'):
            mask &= df['fund_type'].isin(conditions['fund_types'])
        
        # scale range filter
        if conditions.get('scale_min') is not None:
            mask &= df['scale'] >= conditions['scale_min']
        if conditions.get('scale_max') is not None:
            mask &= df['scale'] <= conditions['scale_max']
        
        # return_1y range filter
        if conditions.get('return_1y_min') is not None:
            mask &= df['return_1y'] >= conditions['return_1y_min']
        if conditions.get('return_1y_max') is not None:
            mask &= df['return_1y'] <= conditions['return_1y_max']
        
        # setup_year range filter
        if conditions.get('setup_year_min') is not None:
            mask &= df['setup_year'] >= conditions['setup_year_min']
        if conditions.get('setup_year_max') is not None:
            mask &= df['setup_year'] <= conditions['setup_year_max']
        
        # company_names filter
        if conditions.get('company_names'):
            mask &= df['company_name'].isin(conditions['company_names'])
        
        # max_drawdown_1y filter
        if conditions.get('max_drawdown_1y_max') is not None:
            mask &= df['max_drawdown_1y'] <= conditions['max_drawdown_1y_max']
        
        # sharpe_1y filter
        if conditions.get('sharpe_1y_min') is not None:
            mask &= df['sharpe_1y'] >= conditions['sharpe_1y_min']
        
        # Full-text search on fund_name (case-insensitive)
        if conditions.get('fund_name_search'):
            search_term = conditions['fund_name_search'].lower()
            mask &= df['fund_name_lower'].str.contains(search_term, na=False)
        
        # Apply mask
        filtered_df = df.loc[mask]
        total = len(filtered_df)
        
        # Sort and paginate efficiently
        offset = (page - 1) * page_size
        end_idx = offset + page_size
        
        if sort_by in filtered_df.columns:
            ascending = sort_order == 'asc'
            # For first page, use nlargest/nsmallest for better performance
            if page == 1 and sort_by in ['return_1y', 'scale', 'sharpe_1y']:
                if ascending:
                    paginated_df = filtered_df.nsmallest(page_size, sort_by)
                else:
                    paginated_df = filtered_df.nlargest(page_size, sort_by)
            else:
                sorted_df = filtered_df.sort_values(by=sort_by, ascending=ascending, na_position='last')  # type: ignore
                paginated_df = sorted_df.iloc[offset:end_idx]
        else:
            paginated_df = filtered_df.iloc[offset:end_idx]
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.debug(f"Filter completed: {total} results, {elapsed_ms:.2f} ms")
        
        return paginated_df, total
    
    def get_fund_by_code(self, fund_code: str) -> Optional[pd.Series]:
        """Get single fund by code."""
        df = self.cache.df
        result = df[df['fund_code'] == fund_code]
        if len(result) == 0:
            return None
        return result.iloc[0]


# Global service instance
pandas_filter_service = PandasFilterService()
