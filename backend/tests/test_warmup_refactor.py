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
        """Test warmup_hot_funds exists and is wired into the warmup task list.

        Since the v0.1.22 refactor the per-source tasks live in
        ``_run_warmup_tasks`` (``_warmup_cache`` only schedules it), so the
        wiring is asserted there.
        """
        from backend import main
        import inspect

        assert hasattr(main, '_warmup_cache')
        assert hasattr(main, '_warmup_hot_funds')

        source = inspect.getsource(main._run_warmup_tasks)
        assert '_warmup_hot_funds' in source, \
            "warmup_hot_funds not found in _run_warmup_tasks task list"


class TestWarmupFearGreed:
    """Test warmup_fear_greed uses real data."""
    
    @pytest.mark.asyncio
    async def test_warmup_fear_greed_calls_real_api(self):
        """Test that the fear-greed warmup task is wired in and placeholder-free."""
        from backend import main
        import inspect

        assert hasattr(main, '_warmup_fear_greed_endpoint')

        source = inspect.getsource(main._run_warmup_tasks)
        assert '_warmup_fear_greed_endpoint' in source, \
            "fear-greed warmup task not found in _run_warmup_tasks task list"

        warmup_source = inspect.getsource(main._warmup_cache)
        assert 'warmup_placeholder' not in warmup_source, \
            "warmup_placeholder still in _warmup_cache"
