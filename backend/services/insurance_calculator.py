"""
Insurance product calculation services.
IRR (Internal Rate of Return) for cash value projection.
"""
import logging
import numpy as np
from typing import List, Optional, Literal, Tuple, Callable
from dataclasses import dataclass
from datetime import date, timedelta
from scipy.optimize import brentq, newton

logger = logging.getLogger(__name__)

PaymentTiming = Literal["beginning", "end"]  # 年初/年末


def _bisection_fallback(
    f: Callable[[float], float],
    a: float,
    b: float,
    tol: float = 1e-10,
    max_iter: int = 1000
) -> Optional[float]:
    """
    Bisection method for root finding with guaranteed convergence.
    
    Used as third-tier fallback when Newton and Brent fail.
    """
    fa = f(a)
    fb = f(b)
    
    if fa * fb > 0:
        return None
    
    for i in range(max_iter):
        c = (a + b) / 2
        fc = f(c)
        
        if abs(fc) < tol or abs(b - a) < tol:
            return c
        
        if fa * fc < 0:
            b = c
            fb = fc
        else:
            a = c
            fa = fc
    
    return (a + b) / 2


def count_sign_changes(cashflows: List[float]) -> int:
    """
    Count the number of sign changes in cash flow sequence.
    
    According to Descartes' Rule of Signs, the number of positive real roots
    of a polynomial is at most equal to the number of sign changes in its
    coefficients.
    
    For IRR calculation: NPV(r) = sum(CF[i] / (1+r)^i) = 0
    
    Args:
        cashflows: List of cash flow values
    
    Returns:
        Number of sign changes (upper bound on number of positive IRR solutions)
    """
    if not cashflows:
        return 0
    
    signs = []
    for cf in cashflows:
        if abs(cf) > 1e-10:
            signs.append(1 if cf > 0 else -1)
    
    if len(signs) < 2:
        return 0
    
    changes = 0
    for i in range(1, len(signs)):
        if signs[i] != signs[i-1]:
            changes += 1
    
    return changes


@dataclass
class IRRResult:
    """IRR calculation result with diagnostics."""
    irr: Optional[float]
    method: Literal['newton', 'brent', 'bisection', 'failed']
    iterations: int
    residual: float
    sign_changes: int
    warning: Optional[str] = None
    convergence: bool = True


@dataclass
class InsurancePolicy:
    premium: float  # Annual premium
    payment_years: int  # Payment period
    age: int  # Current age
    gender: str  # 'M' or 'F'


@dataclass
class CashValueProjection:
    year: int
    premium_paid: float
    cash_value: float
    death_benefit: float
    irr: Optional[float]


def xnpv(rate: float, cashflows: List[Tuple[date, float]]) -> float:
    """
    Calculate Net Present Value for irregular cash flows.
    
    Formula: XNPV(r) = Σ [CF_i / (1+r)^((date_i - date_0)/365)]
    
    Args:
        rate: Annual discount rate (e.g., 0.05 for 5%)
        cashflows: List of (date, cash_flow) tuples
                   Negative for payments, positive for receipts
    
    Returns:
        Net Present Value of the cash flows
    
    Raises:
        ValueError: If cashflows is empty
    """
    if not cashflows:
        raise ValueError("Cash flows cannot be empty")
    
    if len(cashflows) == 1:
        return cashflows[0][1]
    
    # Sort by date
    sorted_flows = sorted(cashflows, key=lambda x: x[0])
    base_date = sorted_flows[0][0]
    
    npv = 0.0
    for flow_date, flow_amount in sorted_flows:
        days_diff = (flow_date - base_date).days
        years = days_diff / 365.0
        if rate == 0:
            npv += flow_amount
        else:
            npv += flow_amount / ((1 + rate) ** years)
    
    return npv


def xirr_brent(
    cashflows: List[Tuple[date, float]],
    guess: float = 0.1,
    max_iterations: int = 1000,
    tol: float = 1e-10,
) -> IRRResult:
    """
    Calculate XIRR using Brent hybrid method with fallback to bisection.
    
    Args:
        cashflows: List of (date, amount) tuples
        guess: Initial guess for IRR
        max_iterations: Maximum solver iterations
        tol: Convergence tolerance
    
    Returns:
        IRRResult with IRR value and diagnostics
    """
    if not cashflows or len(cashflows) < 2:
        return IRRResult(
            irr=None,
            method='failed',
            iterations=0,
            residual=float('inf'),
            sign_changes=0,
            warning="Insufficient cash flows",
            convergence=False,
        )
    
    amounts = [cf[1] for cf in cashflows]
    sign_changes = count_sign_changes(amounts)
    
    has_positive = any(amt > 0 for amt in amounts)
    has_negative = any(amt < 0 for amt in amounts)
    
    if not has_positive or not has_negative:
        return IRRResult(
            irr=None,
            method='failed',
            iterations=0,
            residual=float('inf'),
            sign_changes=sign_changes,
            warning="No sign change in cash flows",
            convergence=False,
        )
    
    warning = None
    if sign_changes > 1:
        warning = f"Multiple IRR solutions may exist ({sign_changes} sign changes detected)"
        logger.warning(warning)
    
    def npv_func(rate: float) -> float:
        return xnpv(rate, cashflows)
    
    def npv_derivative(rate: float) -> float:
        if rate == 0:
            sorted_flows = sorted(cashflows, key=lambda x: x[0])
            base_date = sorted_flows[0][0]
            deriv = 0.0
            for flow_date, flow_amount in sorted_flows:
                days_diff = (flow_date - base_date).days
                years = days_diff / 365.0
                deriv -= flow_amount * years
            return deriv
        
        sorted_flows = sorted(cashflows, key=lambda x: x[0])
        base_date = sorted_flows[0][0]
        deriv = 0.0
        for flow_date, flow_amount in sorted_flows:
            days_diff = (flow_date - base_date).days
            years = days_diff / 365.0
            deriv -= flow_amount * years / ((1 + rate) ** (years + 1))
        return deriv
    
    try:
        irr_result = newton(npv_func, guess, fprime=npv_derivative, maxiter=max_iterations)
        irr_float = float(irr_result)
        if -0.99 < irr_float < 10:
            residual = abs(npv_func(irr_float))
            return IRRResult(
                irr=irr_float,
                method='newton',
                iterations=0,
                residual=residual,
                sign_changes=sign_changes,
                warning=warning,
            )
    except (RuntimeError, ValueError):
        pass
    
    try:
        irr_result = brentq(npv_func, -0.99, 10.0, xtol=tol, maxiter=max_iterations)
        irr_float = float(irr_result[0] if isinstance(irr_result, tuple) else irr_result)
        residual = abs(npv_func(irr_float))
        return IRRResult(
            irr=irr_float,
            method='brent',
            iterations=0,
            residual=residual,
            sign_changes=sign_changes,
            warning=warning,
        )
    except ValueError:
        try:
            irr_result = brentq(npv_func, -0.999, 100.0, xtol=tol, maxiter=max_iterations)
            irr_float = float(irr_result[0] if isinstance(irr_result, tuple) else irr_result)
            residual = abs(npv_func(irr_float))
            return IRRResult(
                irr=irr_float,
                method='brent',
                iterations=0,
                residual=residual,
                sign_changes=sign_changes,
                warning=warning,
            )
        except ValueError:
            pass
    
    # Strategy 3: Bisection fallback (guaranteed convergence for bracketed roots)
    # This is slower but more robust for pathological cases
    try:
        # Use bisection with much wider bracket
        irr_result = _bisection_fallback(npv_func, -0.999, 1000.0, tol=tol, max_iter=max_iterations)
        if irr_result is not None:
            residual = abs(npv_func(irr_result))
            return IRRResult(
                irr=irr_result,
                method='bisection',
                iterations=max_iterations,
                residual=residual,
                sign_changes=sign_changes,
                warning=warning,
            )
    except Exception:
        pass
    
    return IRRResult(
        irr=None,
        method='failed',
        iterations=0,
        residual=float('inf'),
        sign_changes=sign_changes,
        warning=warning,
        convergence=False,
    )


def create_insurance_cash_flows(
    premium: float,
    payment_years: int,
    payment_timing: PaymentTiming,
    valuation_year: int,
    base_date: Optional[date] = None
) -> Tuple[List[Tuple[date, float]], date]:
    """
    Create insurance cash flows with explicit dates.
    
    Args:
        premium: Annual premium amount (positive value)
        payment_years: Number of years to pay premium
        payment_timing: "beginning" (年初/Annuity Due) or "end" (年末/Ordinary Annuity)
        valuation_year: Year to evaluate cash value (1-indexed)
        base_date: Base date for calculations (defaults to today)
    
    Returns:
        Tuple of (cashflows, cash_value_date)
        - cashflows: List of (date, cash_flow) tuples for premiums
        - cash_value_date: Date when cash value is received
        - Premium payments are negative (outflows)
        - Cash value return is positive (inflow)
    
    Timing explanation:
        - "beginning": Premiums at t=0,1,2,...,n-1 (年初支付)
        - "end": Premiums at t=1,2,3,...,n (年末支付)
        - Cash value always at end of valuation year
    """
    if base_date is None:
        base_date = date.today()
    
    cashflows: List[Tuple[date, float]] = []
    
    # Generate premium payment cash flows
    for year in range(payment_years):
        if payment_timing == "beginning":
            # 年初支付: t=0,1,2,...,n-1
            payment_date = base_date + timedelta(days=year * 365)
        else:  # "end"
            # 年末支付: t=1,2,3,...,n
            payment_date = base_date + timedelta(days=(year + 1) * 365)
        
        cashflows.append((payment_date, -premium))
    
    # Cash value is returned at end of valuation year
    # This is the terminal positive cash flow
    cash_value_date = base_date + timedelta(days=valuation_year * 365)
    
    return cashflows, cash_value_date


def calculate_irr(cash_flows: List[float]) -> Optional[float]:
    """
    Calculate IRR for regular cash flows (legacy function).
    Uses scipy.optimize.newton for compatibility with numpy 2.0+.
    
    Args:
        cash_flows: List of cash flows at regular intervals
                    (negative for payments, positive for withdrawal)
    
    Returns:
        IRR as percentage, or None if calculation fails
    """
    if not cash_flows or len(cash_flows) < 2:
        return None
    
    # Check for valid cash flow pattern
    has_positive = any(cf > 0 for cf in cash_flows)
    has_negative = any(cf < 0 for cf in cash_flows)
    
    if not has_positive or not has_negative:
        return None
    
    def npv(rate: float) -> float:
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))
    
    try:
        result = newton(npv, 0.1, maxiter=100)
        if isinstance(result, tuple):
            result = result[0]
        irr_float = float(result)
        if np.isnan(irr_float) or np.isinf(irr_float):
            return None
        return irr_float * 100
    except (ValueError, RuntimeError):
        return None


def project_cash_values(
    policy: InsurancePolicy,
    projection_years: int = 30,
    assumed_growth: float = 3.5,
    payment_timing: PaymentTiming = "beginning"
) -> List[CashValueProjection]:
    """
    Project cash values over time with explicit time alignment.
    
    Args:
        policy: Insurance policy parameters
        projection_years: Number of years to project (default 30)
        assumed_growth: Assumed annual growth rate in percentage (default 3.5%)
        payment_timing: "beginning" (年初) or "end" (年末), default "beginning"
    
    Returns:
        List of CashValueProjection for each year
    """
    projections = []
    total_premium = 0.0
    base_date = date.today()
    
    for year in range(1, projection_years + 1):
        if year <= policy.payment_years:
            total_premium += policy.premium
        
        cashflows, cash_value_date = create_insurance_cash_flows(
            premium=policy.premium,
            payment_years=min(year, policy.payment_years),
            payment_timing=payment_timing,
            valuation_year=year,
            base_date=base_date
        )
        
        cash_value = total_premium * (1 + assumed_growth / 100) ** year * 0.85
        death_benefit = total_premium * 1.5 + cash_value
        
        cashflows.append((cash_value_date, cash_value))
        irr_result = xirr_brent(cashflows)
        irr = irr_result.irr * 100 if irr_result.irr is not None else None
        
        projections.append(CashValueProjection(
            year=year,
            premium_paid=total_premium,
            cash_value=round(cash_value, 2),
            death_benefit=round(death_benefit, 2),
            irr=round(irr, 2) if irr is not None else None
        ))
    
    return projections


def find_break_even_year(projections: List[CashValueProjection]) -> Optional[int]:
    """
    Find the break-even year where cash value >= premium paid.
    
    Args:
        projections: List of cash value projections
    
    Returns:
        Break-even year number, or None if never breaks even
    """
    for p in projections:
        if p.cash_value >= p.premium_paid:
            return p.year
    return None
