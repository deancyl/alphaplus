"""
Unit tests for backend formatter utilities.
"""
import pytest
from backend.utils.formatters import round2, round4, round_percent, round_price


class TestRound2:
    """Tests for round2 function."""
    
    def test_round2_basic(self):
        assert round2(1.2345) == 1.23
        assert round2(1.2355) == 1.24  # Python banker's rounding
        assert round2(100.999) == 101.0
    
    def test_round2_negative(self):
        assert round2(-1.2345) == -1.23
        assert round2(-100.999) == -101.0
    
    def test_round2_zero(self):
        assert round2(0.0) == 0.0
        assert round2(0.001) == 0.0
    
    def test_round2_none(self):
        assert round2(None) is None
    
    def test_round2_already_rounded(self):
        assert round2(1.23) == 1.23
        assert round2(100.0) == 100.0


class TestRound4:
    """Tests for round4 function."""
    
    def test_round4_basic(self):
        assert round4(0.123456) == 0.1235
        assert round4(0.999999) == 1.0
    
    def test_round4_none(self):
        assert round4(None) is None


class TestRoundPercent:
    """Tests for round_percent function."""
    
    def test_round_percent_basic(self):
        assert round_percent(50.123) == 50.12
    
    def test_round_percent_none(self):
        assert round_percent(None) is None


class TestRoundPrice:
    """Tests for round_price function."""
    
    def test_round_price_basic(self):
        assert round_price(100.123) == 100.12
    
    def test_round_price_none(self):
        assert round_price(None) is None
