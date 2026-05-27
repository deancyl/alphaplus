"""
Test suite for insurance IRR calculation with time alignment.
Tests XNPV, XIRR (Brent solver), payment timing, and backward compatibility.
"""
import pytest
from datetime import date, timedelta
from typing import List, Tuple

from backend.services.insurance_calculator import (
    xnpv,
    xirr_brent,
    create_insurance_cash_flows,
    project_cash_values,
    InsurancePolicy,
    PaymentTiming
)


class TestXNPV:
    """Test XNPV (Net Present Value for irregular cash flows)."""
    
    def test_xnpv_zero_rate(self):
        """XNPV with zero rate should sum all cash flows."""
        base = date(2024, 1, 1)
        cashflows = [
            (base, -1000),
            (base + timedelta(days=365), 500),
            (base + timedelta(days=730), 600)
        ]
        result = xnpv(0.0, cashflows)
        assert abs(result - 100.0) < 0.01
    
    def test_xnpv_positive_rate(self):
        """XNPV with positive rate should discount future cash flows."""
        base = date(2024, 1, 1)
        cashflows = [
            (base, -1000),
            (base + timedelta(days=365), 1100)
        ]
        result = xnpv(0.10, cashflows)
        expected = -1000 + 1100 / 1.10
        assert abs(result - expected) < 0.01
    
    def test_xnpv_irregular_intervals(self):
        """XNPV should handle irregular time intervals."""
        base = date(2024, 1, 1)
        cashflows = [
            (base, -1000),
            (base + timedelta(days=180), 300),
            (base + timedelta(days=400), 400),
            (base + timedelta(days=800), 500)
        ]
        result = xnpv(0.05, cashflows)
        assert isinstance(result, float)
        assert result != 0
    
    def test_xnpv_single_cashflow(self):
        """XNPV with single cash flow should return that amount."""
        base = date(2024, 1, 1)
        cashflows = [(base, 1000)]
        result = xnpv(0.05, cashflows)
        assert result == 1000
    
    def test_xnpv_empty_raises(self):
        """XNPV with empty cash flows should raise ValueError."""
        with pytest.raises(ValueError):
            xnpv(0.05, [])
    
    def test_xnpv_unsorted_dates(self):
        """XNPV should handle unsorted dates correctly."""
        base = date(2024, 1, 1)
        cashflows = [
            (base + timedelta(days=730), 600),
            (base, -1000),
            (base + timedelta(days=365), 500)
        ]
        result = xnpv(0.05, cashflows)
        assert isinstance(result, float)


class TestXIRRBrent:
    """Test XIRR using Brent's hybrid algorithm."""
    
    def test_xirr_simple_case(self):
        """XIRR for simple investment should converge."""
        base = date(2024, 1, 1)
        cashflows = [
            (base, -1000),
            (base + timedelta(days=365), 1100)
        ]
        irr = xirr_brent(cashflows)
        assert irr is not None
        assert abs(irr - 0.10) < 0.01
    
    def test_xirr_multi_year(self):
        """XIRR for multi-year investment."""
        base = date(2024, 1, 1)
        cashflows = [
            (base, -1000),
            (base + timedelta(days=365), 300),
            (base + timedelta(days=730), 300),
            (base + timedelta(days=1095), 300),
            (base + timedelta(days=1460), 300)
        ]
        irr = xirr_brent(cashflows)
        assert irr is not None
        assert 0 < irr < 1
    
    def test_xirr_all_positive_returns_none(self):
        """XIRR with all positive cash flows should return None."""
        base = date(2024, 1, 1)
        cashflows = [
            (base, 100),
            (base + timedelta(days=365), 100)
        ]
        irr = xirr_brent(cashflows)
        assert irr is None
    
    def test_xirr_all_negative_returns_none(self):
        """XIRR with all negative cash flows should return None."""
        base = date(2024, 1, 1)
        cashflows = [
            (base, -100),
            (base + timedelta(days=365), -100)
        ]
        irr = xirr_brent(cashflows)
        assert irr is None
    
    def test_xirr_single_cashflow_returns_none(self):
        """XIRR with single cash flow should return None."""
        base = date(2024, 1, 1)
        cashflows = [(base, -1000)]
        irr = xirr_brent(cashflows)
        assert irr is None
    
    def test_xirr_empty_returns_none(self):
        """XIRR with empty cash flows should return None."""
        irr = xirr_brent([])
        assert irr is None
    
    def test_xirr_complex_pattern(self):
        """XIRR for complex cash flow pattern."""
        base = date(2024, 1, 1)
        cashflows = [
            (base, -10000),
            (base + timedelta(days=30), 500),
            (base + timedelta(days=180), 2000),
            (base + timedelta(days=365), 3000),
            (base + timedelta(days=730), 8000)
        ]
        irr = xirr_brent(cashflows)
        assert irr is not None
        assert 0 < irr < 1
    
    def test_xirr_negative_return(self):
        """XIRR can be negative for losing investments."""
        base = date(2024, 1, 1)
        cashflows = [
            (base, -1000),
            (base + timedelta(days=365), 500)
        ]
        irr = xirr_brent(cashflows)
        assert irr is not None
        assert irr < 0
    
    def test_xirr_verifies_npv_zero(self):
        """XIRR should make NPV equal to zero."""
        base = date(2024, 1, 1)
        cashflows = [
            (base, -1000),
            (base + timedelta(days=365), 400),
            (base + timedelta(days=730), 400),
            (base + timedelta(days=1095), 400)
        ]
        irr = xirr_brent(cashflows)
        assert irr is not None
        npv = xnpv(irr, cashflows)
        assert abs(npv) < 0.01


class TestCreateInsuranceCashFlows:
    """Test insurance cash flow generation with explicit dates."""
    
    def test_beginning_timing(self):
        """Beginning timing: premiums at t=0,1,2,...,n-1."""
        base = date(2024, 1, 1)
        cashflows, cv_date = create_insurance_cash_flows(
            premium=1000,
            payment_years=3,
            payment_timing="beginning",
            valuation_year=5,
            base_date=base
        )
        
        assert len(cashflows) == 3
        assert cashflows[0][0] == base
        assert cashflows[1][0] == base + timedelta(days=365)
        assert cashflows[2][0] == base + timedelta(days=730)
        assert cv_date == base + timedelta(days=5 * 365)
    
    def test_end_timing(self):
        """End timing: premiums at t=1,2,3,...,n."""
        base = date(2024, 1, 1)
        cashflows, cv_date = create_insurance_cash_flows(
            premium=1000,
            payment_years=3,
            payment_timing="end",
            valuation_year=5,
            base_date=base
        )
        
        assert len(cashflows) == 3
        assert cashflows[0][0] == base + timedelta(days=365)
        assert cashflows[1][0] == base + timedelta(days=730)
        assert cashflows[2][0] == base + timedelta(days=1095)
        assert cv_date == base + timedelta(days=5 * 365)
    
    def test_timing_difference_one_year(self):
        """Beginning and end timing differ by exactly one year."""
        base = date(2024, 1, 1)
        
        flows_beginning, _ = create_insurance_cash_flows(
            premium=1000, payment_years=3, payment_timing="beginning",
            valuation_year=5, base_date=base
        )
        
        flows_end, _ = create_insurance_cash_flows(
            premium=1000, payment_years=3, payment_timing="end",
            valuation_year=5, base_date=base
        )
        
        for i in range(3):
            days_diff = (flows_end[i][0] - flows_beginning[i][0]).days
            assert days_diff == 365
    
    def test_all_premiums_negative(self):
        """All premium cash flows should be negative."""
        base = date(2024, 1, 1)
        cashflows, _ = create_insurance_cash_flows(
            premium=1000, payment_years=5, payment_timing="beginning",
            valuation_year=10, base_date=base
        )
        
        for _, amount in cashflows:
            assert amount == -1000


class TestProjectCashValues:
    """Test cash value projection with time alignment."""
    
    def test_default_timing_is_beginning(self):
        """Default payment_timing should be 'beginning' for backward compatibility."""
        policy = InsurancePolicy(
            premium=10000,
            payment_years=5,
            age=30,
            gender='M'
        )
        projections = project_cash_values(
            policy=policy,
            projection_years=10,
            assumed_growth=3.5
        )
        
        assert len(projections) == 10
        assert all(p.irr is not None for p in projections)
    
    def test_timing_produces_different_irr(self):
        """Beginning and end timing should produce different IRRs."""
        policy = InsurancePolicy(
            premium=10000,
            payment_years=5,
            age=30,
            gender='M'
        )
        
        proj_beginning = project_cash_values(
            policy=policy, projection_years=10, assumed_growth=3.5,
            payment_timing="beginning"
        )
        
        proj_end = project_cash_values(
            policy=policy, projection_years=10, assumed_growth=3.5,
            payment_timing="end"
        )
        
        for i in range(len(proj_beginning)):
            if proj_beginning[i].irr is not None and proj_end[i].irr is not None:
                assert proj_beginning[i].irr != proj_end[i].irr
    
    def test_time_alignment_eliminated_one_year_bias(self):
        """Time alignment should eliminate the 1-year bias."""
        policy = InsurancePolicy(
            premium=10000,
            payment_years=3,
            age=30,
            gender='M'
        )
        
        projections = project_cash_values(
            policy=policy, projection_years=5, assumed_growth=5.0,
            payment_timing="beginning"
        )
        
        assert projections[0].year == 1
        assert projections[0].premium_paid == 10000
        assert projections[2].premium_paid == 30000
        assert projections[3].premium_paid == 30000
    
    def test_backward_compatibility(self):
        """Calling without payment_timing should work (default 'beginning')."""
        policy = InsurancePolicy(
            premium=10000,
            payment_years=5,
            age=30,
            gender='M'
        )
        
        projections_old_style = project_cash_values(
            policy=policy,
            projection_years=10,
            assumed_growth=3.5
        )
        
        projections_new_style = project_cash_values(
            policy=policy,
            projection_years=10,
            assumed_growth=3.5,
            payment_timing="beginning"
        )
        
        for old, new in zip(projections_old_style, projections_new_style):
            assert old.year == new.year
            assert old.premium_paid == new.premium_paid
            assert old.cash_value == new.cash_value
    
    def test_projections_have_valid_irr(self):
        """All projections should have valid IRR values."""
        policy = InsurancePolicy(
            premium=10000,
            payment_years=10,
            age=35,
            gender='F'
        )
        
        projections = project_cash_values(
            policy=policy, projection_years=20, assumed_growth=4.0,
            payment_timing="beginning"
        )
        
        for p in projections:
            assert p.irr is not None
            assert -100 < p.irr < 100


class TestTimingComparison:
    """Test that different timings produce different IRRs."""
    
    def test_one_year_timing_gap(self):
        """Verify the 1-year timing gap between beginning and end produces different IRRs."""
        base = date(2024, 1, 1)
        
        flows_beginning, cv_date = create_insurance_cash_flows(
            premium=10000, payment_years=5, payment_timing="beginning",
            valuation_year=10, base_date=base
        )
        flows_beginning.append((cv_date, 80000))
        
        flows_end, cv_date = create_insurance_cash_flows(
            premium=10000, payment_years=5, payment_timing="end",
            valuation_year=10, base_date=base
        )
        flows_end.append((cv_date, 80000))
        
        irr_beginning = xirr_brent(flows_beginning)
        irr_end = xirr_brent(flows_end)
        
        assert irr_beginning is not None
        assert irr_end is not None
        assert irr_beginning != irr_end
    
    def test_timing_affects_break_even(self):
        """Different timing affects when investment breaks even."""
        policy = InsurancePolicy(
            premium=10000,
            payment_years=5,
            age=30,
            gender='M'
        )
        
        proj_beginning = project_cash_values(
            policy=policy, projection_years=15, assumed_growth=3.5,
            payment_timing="beginning"
        )
        
        proj_end = project_cash_values(
            policy=policy, projection_years=15, assumed_growth=3.5,
            payment_timing="end"
        )
        
        be_beginning = next((p.year for p in proj_beginning if p.cash_value >= p.premium_paid), None)
        be_end = next((p.year for p in proj_end if p.cash_value >= p.premium_paid), None)
        
        if be_beginning and be_end:
            assert be_beginning <= be_end


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_very_high_growth_rate(self):
        """Test with very high assumed growth rate."""
        policy = InsurancePolicy(
            premium=10000,
            payment_years=5,
            age=30,
            gender='M'
        )
        
        projections = project_cash_values(
            policy=policy, projection_years=10, assumed_growth=10.0,
            payment_timing="beginning"
        )
        
        assert all(p.irr is not None for p in projections)
        assert projections[-1].irr > projections[0].irr
    
    def test_zero_growth_rate(self):
        """Test with zero growth rate."""
        policy = InsurancePolicy(
            premium=10000,
            payment_years=5,
            age=30,
            gender='M'
        )
        
        projections = project_cash_values(
            policy=policy, projection_years=10, assumed_growth=0.0,
            payment_timing="beginning"
        )
        
        for p in projections:
            expected_cv = p.premium_paid * 0.85
            assert abs(p.cash_value - expected_cv) < 0.01
    
    def test_long_projection_period(self):
        """Test with long projection period."""
        policy = InsurancePolicy(
            premium=10000,
            payment_years=10,
            age=25,
            gender='M'
        )
        
        projections = project_cash_values(
            policy=policy, projection_years=50, assumed_growth=3.5,
            payment_timing="beginning"
        )
        
        assert len(projections) == 50
        assert all(p.irr is not None for p in projections[:30])
    
    def test_single_payment_year(self):
        """Test with single premium payment year."""
        policy = InsurancePolicy(
            premium=50000,
            payment_years=1,
            age=40,
            gender='F'
        )
        
        projections = project_cash_values(
            policy=policy, projection_years=10, assumed_growth=3.5,
            payment_timing="beginning"
        )
        
        assert all(p.premium_paid == 50000 for p in projections)
        assert all(p.irr is not None for p in projections)
