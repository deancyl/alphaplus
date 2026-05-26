/**
 * Fund API endpoints
 */
import api from './index'

// Types
export interface FundFilterParams {
  fund_types?: string[]
  setup_year_min?: number
  setup_year_max?: number
  scale_min?: number
  scale_max?: number
  company_names?: string[]
  return_1y_min?: number
  return_1y_max?: number
  max_drawdown_1y_max?: number
  sharpe_1y_min?: number
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export interface FundItem {
  fund_code: string
  fund_name: string
  fund_type: string
  manager: string
  setup_date: string
  setup_year: number | null
  scale: number | null
  company_name: string
  return_1y: number | null
  volatility_1y: number | null
  max_drawdown_1y: number | null
  sharpe_1y: number | null
  heavy_sector: string | null
}

export interface FundFilterResponse {
  total: number
  page: number
  page_size: number
  funds: FundItem[]
}

// Filter funds
export const filterFunds = async (params: FundFilterParams): Promise<FundFilterResponse> => {
  return api.post('/fund/filter', params)
}

// Get fund detail
export const getFundDetail = async (fundCode: string): Promise<FundItem> => {
  return api.get(`/fund/${fundCode}`)
}

// Compare funds
export const compareFunds = async (
  fundCodes: string[],
  benchmark = '000300'
): Promise<{ fund_codes: string[]; correlation_matrix: number[][] }> => {
  return api.post('/fund/compare', {
    fund_codes: fundCodes,
    benchmark,
  })
}

// Get fund issue calendar
export const getFundIssueCalendar = async (
  status?: string
): Promise<Array<{
  fund_code: string
  fund_name: string
  company: string
  subscribe_start_date: string
  subscribe_end_date: string
  status: string
  initial_scale: number | null
  delist_scale: number | null
}>> => {
  const params: Record<string, string> = {}
  if (status) params.status = status
  return api.get('/fund/issue', { params })
}

// Get fund companies
export const getFundCompanies = async (): Promise<Array<{
  company_id: string
  company_name: string
  establish_date: string | null
  total_scale: number | null
  non_money_scale: number | null
  fund_count: number | null
  manager_count: number | null
}>> => {
  return api.get('/fund/company')
}
