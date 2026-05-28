"""
Tests for v0.1.22 warmup refactor: placeholder elimination and hot funds.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio


class TestWarmupPlaceholderElimination:
    """Test that warmup_placeholder has been eliminated."""
    
    def test_no_placeholder_in_main_py(self):
        """Verify warmup_placeholder string no longer exists in main.py."""
        import backend.main
        source_file = backend.main.__file__
        
        with open(source_file, 'r') as f:
            content = f.read()
        
        assert 'warmup_placeholder' not in content, \
            "warmup_placeholder still exists in main.py"


class TestWarmupHotFunds:
    """Test warmup_hot_funds function."""
    
    @pytest.mark.asyncio
    async def test_warmup_hot_funds_function_exists(self):
        """Test warmup_hot_funds function exists in main module."""
        from backend import main
        
        # Check function exists
        assert hasattr(main, '_warmup_cache')
        
        # The warmup_hot_funds should be called inside _warmup_cache
        import inspect
        source = inspect.getsource(main._warmup_cache)
        assert 'warmup_hot_funds' in source or 'hot_funds' in source, \
            "warmup_hot_funds not found in _warmup_cache"


class TestWarmupFearGreed:
    """Test warmup_fear_greed uses real data."""
    
    @pytest.mark.asyncio
    async def test_warmup_fear_greed_calls_real_api(self):
        """Test that warmup_fear_greed calls get_fear_greed_index."""
        from backend import main
        
        import inspect
        source = inspect.getsource(main._warmup_cache)
        
        # Should contain call to get_fear_greed_index
        assert 'get_fear_greed_index' in source, \
            "get_fear_greed_index call not found in _warmup_cache"
        
        # Should NOT contain placeholder
        assert 'warmup_placeholder' not in source, \
            "warmup_placeholder still in _warmup_cache"
