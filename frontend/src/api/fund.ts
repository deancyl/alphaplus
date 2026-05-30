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
  new_high_ratio_min?: number
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
  new_high_ratio_1y?: number | null
  manager_honors?: string | null
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

// Get top gainers and losers
export const getTopFunds = async (limit = 10): Promise<{
  gainers: Array<{
    fund_code: string
    fund_name: string
    fund_type: string
    return_1y: number | null
  }>
  losers: Array<{
    fund_code: string
    fund_name: string
    fund_type: string
    return_1y: number | null
  }>
  timestamp: string
}> => {
  return api.get('/fund/top-funds', { params: { limit } })
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

// Get company distribution for treemap/bubble
export const getCompanyDistribution = async (
  companyId: string,
  distType: string = 'asset_class'
): Promise<{
  items: Array<{ item_name: string; weight: number }>
  is_simulated: boolean
}> => {
  return api.get(`/fund/company/${companyId}/distribution`, {
    params: { dist_type: distType }
  })
}

// Get fund NAV trend for sparkline
export const getFundNavTrend = async (
  fundCode: string,
  days: number = 30
): Promise<{
  nav_values: number[]
  dates: string[]
  is_simulated: boolean
}> => {
  return api.get(`/fund/${fundCode}/nav-trend`, {
    params: { days }
  })
}

// AIP (Automatic Investment Plan) Calculator Types
export interface AIPCalculateRequest {
  fund_code: string
  frequency: 'weekly' | 'biweekly' | 'monthly'
  amount: number
  start_date: string
  end_date?: string
}

export interface AIPCalculateResponse {
  fund_code: string
  fund_name: string
  frequency: string
  amount: number
  total_investment: number
  current_value: number
  return_rate: number
  max_drawdown: number
  volatility: number
  periods: number
  units_total: number
  lump_sum_comparison: { value: number; return_rate: number }
  investment_dates: string[]
  nav_history: Array<{
    date: string
    nav: number
    units: number
    value: number
    cumulative_return: number
  }>
}

// Calculate AIP
export const calculateAIP = async (
  data: AIPCalculateRequest
): Promise<AIPCalculateResponse> => {
  return api.post('/fund/aip-calculate', data)
}

// ==================== Holdings & Industry Types ====================

/**
 * Stock holding item in portfolio
 */
export interface HoldingItem {
  stock_code: string        // 股票代码
  stock_name: string        // 股票名称
  holding_ratio: number     // 持仓比例 (%)
  holding_value: number     // 持仓市值 (万元)
  change_direction: 'new' | 'increase' | 'decrease' | 'unchanged'  // 变动方向
}

/**
 * Industry allocation item
 */
export interface IndustryItem {
  industry_name: string     // 行业名称
  weight: number            // 占比 (%)
}

/**
 * Report date with holdings data
 */
export interface ReportDate {
  report_date: string       // 报告期 (YYYY-MM-DD)
  label: string             // 显示标签 (如 "2024年一季报")
}

/**
 * Holdings API response
 */
export interface HoldingsResponse {
  fund_code: string
  report_date: string
  report_dates: ReportDate[]
  holdings: HoldingItem[]
}

/**
 * Industry API response
 */
export interface IndustryResponse {
  fund_code: string
  report_date: string
  report_dates: ReportDate[]
  industries: IndustryItem[]
}

// Get fund holdings (top 10 stocks)
export const getFundHoldings = async (
  fundCode: string,
  reportDate?: string
): Promise<HoldingsResponse> => {
  const params: Record<string, string> = {}
  if (reportDate) params.report_date = reportDate
  return api.get(`/fund/${fundCode}/holdings`, { params })
}

// Get fund industry allocation
export const getFundIndustry = async (
  fundCode: string,
  reportDate?: string
): Promise<IndustryResponse> => {
  const params: Record<string, string> = {}
  if (reportDate) params.report_date = reportDate
  return api.get(`/fund/${fundCode}/industry`, { params })
}

// ==================== Stock Reverse Holding Types ====================

/**
 * Fund holding a specific stock
 */
export interface StockReverseHoldingItem {
  fund_code: string         // 基金代码
  fund_name: string         // 基金名称
  holding_ratio: number     // 持仓占净值比例
  holding_value?: number    // 持股市值 (万元)
  report_date: string       // 报告期
}

export interface StockReverseHoldingResponse {
  stock_code: string            // 股票代码
  stock_name: string            // 股票名称
  total_funds: number           // 持有该股票的基金总数
  aggregate_exposure: number    // 加总暴露度 (%)
  funds: StockReverseHoldingItem[]  // 持仓基金列表
}

export const getStockReverseHolding = async (
  stockCode: string,
  limit: number = 50
): Promise<StockReverseHoldingResponse> => {
  return api.get('/fund/stock-reverse', {
    params: { stock_code: stockCode, limit }
  })
}

export interface CrowdingAnalysisResponse {
  stock_code: string
  stock_name: string
  total_funds: number
  crowding_score: number
  hhi_index: number
  concentration_level: 'none' | 'low' | 'medium' | 'high' | 'extreme'
  overlap_coefficient: number
  avg_weight: number
  total_weight: number
  max_weight: number
  weight_std: number
  top_fund: string
  top_5_weight_pct: number
  quarter_distribution: Record<string, number>
}

export const getCrowdingAnalysis = async (
  stockCode: string
): Promise<CrowdingAnalysisResponse> => {
  return api.get(`/fund/stock-reverse/${stockCode}/crowding`)
}

export interface AggregationResponse {
  stock_code: string
  stock_name: string
  total_funds: number
  total_weight: number
  avg_weight: number
  max_weight: number
  weight_std: number
  top_fund: string
  quarter_distribution: Record<string, number>
}

export const getStockAggregation = async (
  stockCode: string
): Promise<AggregationResponse> => {
  return api.get(`/fund/stock-reverse/${stockCode}/aggregation`)
}

export const exportStockReverseHolding = async (
  stockCode: string,
  format: 'csv' | 'excel' = 'csv',
  limit: number = 100
): Promise<Blob> => {
  const response = await api.get(`/fund/stock-reverse/${stockCode}/export`, {
    params: { format, limit },
    responseType: 'blob'
  })
  return response
}
