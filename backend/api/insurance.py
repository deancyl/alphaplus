"""
Insurance product API endpoints.
Provides insurance cash value projection and IRR calculation.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.services.insurance_calculator import (
    InsurancePolicy,
    CashValueProjection,
    project_cash_values,
    find_break_even_year
)

router = APIRouter()


class InsurancePolicyRequest(BaseModel):
    """Request schema for insurance calculation."""
    premium: float = Field(..., gt=0, description="Annual premium amount in yuan")
    payment_years: int = Field(..., ge=1, le=30, description="Payment period in years")
    age: int = Field(..., ge=18, le=70, description="Current age of policyholder")
    gender: str = Field(..., pattern="^[MF]$", description="Gender: 'M' or 'F'")
    projection_years: Optional[int] = Field(default=30, ge=1, le=50, description="Projection years")
    assumed_growth: Optional[float] = Field(default=3.5, ge=0, le=10, description="Assumed annual growth rate (%)")
    
    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v: str) -> str:
        if v not in ('M', 'F'):
            raise ValueError("Gender must be 'M' or 'F'")
        return v


class CashValueProjectionResponse(BaseModel):
    """Response schema for cash value projection."""
    year: int
    premium_paid: float
    cash_value: float
    death_benefit: float
    irr: Optional[float]


class InsuranceCalculateResponse(BaseModel):
    """Response schema for insurance calculation."""
    projections: List[CashValueProjectionResponse]
    break_even_year: Optional[int]
    policy: InsurancePolicyRequest


@router.post("/calculate", response_model=InsuranceCalculateResponse)
async def calculate_insurance(policy: InsurancePolicyRequest):
    """
    Calculate insurance cash value projection.
    
    Returns projected cash values, death benefits, and IRR for each year.
    Also identifies the break-even year when cash value >= premium paid.
    
    Args:
        policy: Insurance policy parameters including premium, payment years, age, gender
    
    Returns:
        InsuranceCalculateResponse with projections and break-even year
    """
    try:
        # Create policy object
        insurance_policy = InsurancePolicy(
            premium=policy.premium,
            payment_years=policy.payment_years,
            age=policy.age,
            gender=policy.gender
        )
        
        # Project cash values
        projections = project_cash_values(
            policy=insurance_policy,
            projection_years=policy.projection_years or 30,
            assumed_growth=policy.assumed_growth or 3.5
        )
        
        # Find break-even year
        break_even = find_break_even_year(projections)
        
        # Convert to response format
        projection_responses = [
            CashValueProjectionResponse(
                year=p.year,
                premium_paid=p.premium_paid,
                cash_value=p.cash_value,
                death_benefit=p.death_benefit,
                irr=p.irr
            )
            for p in projections
        ]
        
        return InsuranceCalculateResponse(
            projections=projection_responses,
            break_even_year=break_even,
            policy=policy
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)}")