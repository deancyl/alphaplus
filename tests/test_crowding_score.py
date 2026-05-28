"""
Tests for crowding score calculation.
"""
import pytest
from unittest.mock import AsyncMock, patch
from backend.services.crowding_analysis import (
    calculate_holding_overlap,
    get_crowding_score,
)
from backend.services.duckdb_ingestion import (
    aggregate_by_stock,
    calculate_crowding_score,
)


@pytest.mark.asyncio
async def test_aggregate_by_stock_empty():
    """Test aggregation with no holdings."""
    with patch('backend.services.duckdb_ingestion.duckdb_pool_manager') as mock_pool:
        mock_pool.execute_read = AsyncMock(return_value=[])
        
        result = await aggregate_by_stock('600519')
        
        assert result['stock_code'] == '600519'
        assert result['total_funds'] == 0
        assert result['total_weight'] == 0.0
        assert result['avg_weight'] == 0.0
        assert result['max_weight'] == 0.0
        assert result['weight_std'] == 0.0
        assert result['top_fund'] == ''


@pytest.mark.asyncio
async def test_aggregate_by_stock_with_data():
    """Test aggregation with holding data."""
    mock_data = [
        ('FUND001', '2024-03-31', 0.05, '贵州茅台'),
        ('FUND002', '2024-03-31', 0.03, '贵州茅台'),
        ('FUND003', '2024-03-31', 0.02, '贵州茅台'),
    ]
    
    with patch('backend.services.duckdb_ingestion.duckdb_pool_manager') as mock_pool:
        mock_pool.execute_read = AsyncMock(return_value=mock_data)
        
        result = await aggregate_by_stock('600519')
        
        assert result['stock_code'] == '600519'
        assert result['stock_name'] == '贵州茅台'
        assert result['total_funds'] == 3
        assert result['total_weight'] == 0.10
        assert result['max_weight'] == 0.05
        assert result['top_fund'] == 'FUND001'


@pytest.mark.asyncio
async def test_calculate_crowding_score_empty():
    """Test crowding score with no holdings."""
    with patch('backend.services.duckdb_ingestion.duckdb_pool_manager') as mock_pool:
        mock_pool.execute_read = AsyncMock(return_value=[])
        
        result = await calculate_crowding_score('600519')
        
        assert result['stock_code'] == '600519'
        assert result['crowding_score'] == 0.0
        assert result['hhi_index'] == 0.0
        assert result['concentration_level'] == 'none'
        assert result['num_funds'] == 0


@pytest.mark.asyncio
async def test_calculate_crowding_score_low_concentration():
    """Test crowding score with low concentration."""
    mock_holdings = [
        ('FUND001', '2024-03-31', 0.01, 'Stock'),
        ('FUND002', '2024-03-31', 0.01, 'Stock'),
        ('FUND003', '2024-03-31', 0.01, 'Stock'),
        ('FUND004', '2024-03-31', 0.01, 'Stock'),
        ('FUND005', '2024-03-31', 0.01, 'Stock'),
    ]
    
    mock_weights = [(0.20,), (0.20,), (0.20,), (0.20,), (0.20,)]
    
    with patch('backend.services.duckdb_ingestion.duckdb_pool_manager') as mock_pool:
        mock_pool.execute_read = AsyncMock(side_effect=[mock_holdings, mock_weights])
        
        result = await calculate_crowding_score('600000')
        
        assert result['stock_code'] == '600000'
        assert result['crowding_score'] < 40
        assert result['concentration_level'] in ['low', 'medium']


@pytest.mark.asyncio
async def test_calculate_crowding_score_high_concentration():
    """Test crowding score with high concentration (one dominant fund)."""
    mock_holdings = [
        ('FUND001', '2024-03-31', 0.50, 'Stock'),
        ('FUND002', '2024-03-31', 0.05, 'Stock'),
        ('FUND003', '2024-03-31', 0.03, 'Stock'),
    ]
    
    mock_weights = [(0.862,), (0.086,), (0.052,)]
    
    with patch('backend.services.duckdb_ingestion.duckdb_pool_manager') as mock_pool:
        mock_pool.execute_read = AsyncMock(side_effect=[mock_holdings, mock_weights])
        
        result = await calculate_crowding_score('600000')
        
        assert result['stock_code'] == '600000'
        assert result['crowding_score'] > 50
        assert result['concentration_level'] in ['high', 'extreme']


@pytest.mark.asyncio
async def test_holding_overlap_no_funds():
    """Test overlap calculation with no funds."""
    result = await calculate_holding_overlap([])
    assert result == 0.0
    
    result = await calculate_holding_overlap([{'fund_code': 'FUND001'}])
    assert result == 0.0


@pytest.mark.asyncio
async def test_holding_overlap_no_common():
    """Test overlap with no common stocks."""
    funds = [
        {'fund_code': 'FUND001'},
        {'fund_code': 'FUND002'},
    ]
    
    with patch('backend.services.crowding_analysis._calculate_pairwise_overlap') as mock_overlap:
        mock_overlap.return_value = 0.0
        
        result = await calculate_holding_overlap(funds)
        assert result == 0.0


@pytest.mark.asyncio
async def test_holding_overlap_with_common():
    """Test overlap with common stocks."""
    funds = [
        {'fund_code': 'FUND001'},
        {'fund_code': 'FUND002'},
    ]
    
    with patch('backend.services.crowding_analysis._calculate_pairwise_overlap') as mock_overlap:
        mock_overlap.return_value = 0.5
        
        result = await calculate_holding_overlap(funds)
        assert result == 0.5


@pytest.mark.asyncio
async def test_get_crowding_score_integration():
    """Test comprehensive crowding score integration."""
    mock_agg_result = {
        'stock_code': '600519',
        'stock_name': '贵州茅台',
        'total_funds': 5,
        'total_weight': 0.15,
        'avg_weight': 0.03,
        'max_weight': 0.05,
        'weight_std': 0.01,
        'top_fund': 'FUND001',
        'quarter_distribution': {'2024-03-31': 5}
    }
    
    mock_crowding_result = {
        'stock_code': '600519',
        'crowding_score': 25.5,
        'hhi_index': 2550.0,
        'concentration_level': 'medium',
        'num_funds': 5,
        'avg_weight': 0.03,
        'top_5_weight_pct': 75.0
    }
    
    mock_funds_result = {
        'stock_code': '600519',
        'stock_name': '贵州茅台',
        'total_funds': 5,
        'aggregate_exposure': 15.0,
        'funds': [
            {'fund_code': 'FUND001', 'holding_ratio': 0.05},
            {'fund_code': 'FUND002', 'holding_ratio': 0.03},
        ]
    }
    
    with patch('backend.services.crowding_analysis.aggregate_by_stock', AsyncMock(return_value=mock_agg_result)), \
         patch('backend.services.crowding_analysis.calc_crowding_score', AsyncMock(return_value=mock_crowding_result)), \
         patch('backend.services.crowding_analysis.search_funds_by_stock', AsyncMock(return_value=mock_funds_result)), \
         patch('backend.services.crowding_analysis.calculate_holding_overlap', AsyncMock(return_value=0.35)):
        
        result = await get_crowding_score('600519')
        
        assert result['stock_code'] == '600519'
        assert result['stock_name'] == '贵州茅台'
        assert result['total_funds'] == 5
        assert result['crowding_score'] == 25.5
        assert result['concentration_level'] == 'medium'
        assert result['overlap_coefficient'] == 0.35
        assert 'quarter_distribution' in result


def test_crowding_score_calculation_formula():
    """Test the HHI and crowding score calculation formulas."""
    import math
    
    weights = [0.50, 0.30, 0.20]
    total = sum(weights)
    normalized = [w / total * 100 for w in weights]
    
    hhi = sum(w ** 2 for w in normalized)
    
    assert hhi == pytest.approx(3800, rel=0.01)
    
    crowding_score = min(100, hhi / 100)
    assert crowding_score == pytest.approx(38.0, rel=0.01)
    
    if crowding_score < 15:
        level = 'low'
    elif crowding_score < 40:
        level = 'medium'
    elif crowding_score < 70:
        level = 'high'
    else:
        level = 'extreme'
    
    assert level == 'medium'


def test_hhi_perfect_competition():
    """Test HHI with perfect competition (equal weights)."""
    n = 10
    weights = [100 / n] * n
    
    hhi = sum(w ** 2 for w in weights)
    
    assert hhi == pytest.approx(1000, rel=0.01)
    
    crowding_score = min(100, hhi / 100)
    assert crowding_score == pytest.approx(10.0, rel=0.01)


def test_hhi_monopoly():
    """Test HHI with monopoly (one dominant holder)."""
    weights = [100]
    
    hhi = sum(w ** 2 for w in weights)
    assert hhi == 10000
    
    crowding_score = min(100, hhi / 100)
    assert crowding_score == 100.0
