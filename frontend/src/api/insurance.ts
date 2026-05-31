/**
 * Insurance API endpoints
 */
import api from './index'

// Types
export interface InsurancePolicyRequest {
  premium: number
  payment_years: number
  age: number
  gender: 'M' | 'F'
  projection_years?: number
  assumed_growth?: number
}

export interface CashValueProjection {
  year: number
  premium_paid: number
  cash_value: number
  death_benefit: number
  irr: number | null
}

export interface InsuranceCalculateResponse {
  projections: CashValueProjection[]
  break_even_year: number | null
  policy: InsurancePolicyRequest
}

// Calculate insurance cash value projection
export const calculateInsurance = async (
  data: InsurancePolicyRequest
): Promise<InsuranceCalculateResponse> => {
  const response = await api.post('/insurance/calculate', data)
  return response.data!
}
