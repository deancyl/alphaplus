/**
 * Market API endpoints
 */
import axios from './index'
const api = axios

// Index Valuation Item
export interface IndexValuationItem {
  index_code: string
  index_name: string
  pe_ttm: number
  pb: number
  dividend_yield: number
  pe_percentile: number
  pb_percentile: number
  zone: string  // "低估", "正常", "高估"
  is_simulated: boolean
}

// Index PE History Item
export interface IndexPEHistoryItem {
  trade_date: string
  pe_ttm: number
  percentile: number
}

// Get index valuation list
export const getIndexValuation = async (): Promise<{ items: IndexValuationItem[], total: number }> => {
  const response = await api.get('/market/index-valuation')
  return response.data ?? { items: [], total: 0 }
}

export const getIndexPEHistory = async (indexCode: string, days: number = 365): Promise<IndexPEHistoryItem[]> => {
  const response = await api.get(`/market/index-valuation/${indexCode}/history`, { params: { days } })
  return response.data ?? []
}

// Get index quotes (5s cache)
export const getIndices = async (): Promise<Record<string, {
  name: string
  price: number
  change: number
  change_pct: number
}>> => {
  const response = await api.get('/market/indices')
  return response.data ?? {}
}

// Dashboard aggregated metrics
export interface DashboardMetrics {
  fear_greed: Array<{
    trade_date: string
    composite_score: number
    sentiment_status: string
    factor_volatility: number | null
    factor_safe_haven: number | null
    factor_margin_ratio: number | null
    factor_volume_deviation: number | null
    factor_futures_basis: number | null
    factor_stock_strength: number | null
  }>
  erp: Array<{
    index_code: string
    index_name: string
    trade_date: string
    pe_ttm: number
    treasury_yield_10y: number
    erp_spread: number
    percentile_rank_10y: number | null
    index_close_price: number | null
  }>
  style_strength: Array<{
    trade_date: string
    index_code_num: string
    index_code_den: string
    ratio_value: number
    percentile_rank_3y: number | null
  }>
  crowding: Array<{
    asset_code: string
    trade_date: string
    category: string
    crowding_score: number
    pe_percentile: number
    close_price: number | null
  }>
  timestamp: string
  data_quality: {
    partial: boolean
    errors: Record<string, string | null>
  }
}

export const getDashboardMetrics = async (): Promise<DashboardMetrics> => {
  const response = await api.get('/market/dashboard')
  return response.data ?? {
    fear_greed: [],
    erp: [],
    style_strength: [],
    crowding: [],
    timestamp: '',
    data_quality: { partial: true, errors: {} }
  }
}

// Get index valuation
export const getIndexValuationHistory = async (
  indexCode: string
): Promise<Array<{
  trade_date: string
  pe_ttm: number
  percentile_rank_10y: number
  moving_mean_10y: number | null
  index_close_price: number | null
}>> => {
  const response = await api.get('/market/valuation', { params: { index_code: indexCode } })
  return response.data ?? []
}

// Get bond yield curve
export const getBondYieldCurve = async (
  bondType = '国债',
  tradeDate?: string
): Promise<Record<string, Array<{ tenor: number; yield_ytm: number }>>> => {
  const params: Record<string, string> = { bond_type: bondType }
  if (tradeDate) params.trade_date = tradeDate
  const response = await api.get('/market/bond/yield-curve', { params })
  return response.data ?? {}
}

// Get money market rates
export const getMoneyMarketRates = async (): Promise<Array<{
  rate_code: string
  trade_date: string
  rate_value: number
  sparkline_data: string | null
}>> => {
  const response = await api.get('/market/bond/money-rates')
  return response.data ?? []
}

// Get rate history for sparkline
export const getRateHistory = async (
  rateCode: string,
  days: number = 30
): Promise<{
  values: number[]
  dates: string[]
  is_simulated: boolean
}> => {
  const response = await api.get('/market/bond/rate-history', {
    params: { rate_code: rateCode, days }
  })
  return response.data ?? { values: [], dates: [], is_simulated: true }
}

// Get market heatmap
export const getMarketHeatmap = async (): Promise<{
  rows: string[]
  cols: string[]
  cells: Array<{ row: string; col: string; value: number; color: string }>
}> => {
  const response = await api.get('/market/heatmap')
  return response.data ?? { rows: [], cols: [], cells: [] }
}

// Get futures quotes
export interface FuturesQuote {
  code: string
  name: string
  exchange: string
  category: string
  price: number
  change: number
  change_pct: number
  volume: number
  open_interest: number
  spot_price: number
  basis: number
  basis_pct: number
  update_time: string
}

export const getFuturesQuotes = async (
  category?: string
): Promise<FuturesQuote[]> => {
  const params: Record<string, string> = {}
  if (category) params.category = category
  const response = await api.get('/market/futures/quotes', { params })
  return response.data ?? []
}

// Get global market overview
export const getGlobalMarket = async (): Promise<{
  indices: Array<{
    code: string
    name: string
    price: number
    change_pct: number
  }>
  currencies: Array<{
    code: string
    name: string
    price: number
    change_pct: number
  }>
  commodities: Array<{
    code: string
    name: string
    price: number
    change_pct: number
  }>
  update_time: string
}> => {
  const response = await api.get('/market/global')
  return response.data ?? { indices: [], currencies: [], commodities: [], update_time: '' }
}

// Get domestic market overview
export const getDomesticMarket = async (): Promise<{
  indices: Array<{
    code: string
    name: string
    price: number
    change_pct: number
  }>
  market_breadth: {
    total: number
    advancing: number
    declining: number
    unchanged: number
    advance_ratio: number
    limit_up: number
    limit_down: number
  }
  volume: {
    total_volume: number
    total_turnover: number
    turnover_rate: number
  }
  sectors: Array<{
    name: string
    change_pct: number
  }>
  north_bound: {
    net_inflow: number
    shanghai_inflow: number
    shenzhen_inflow: number
  }
  update_time: string
}> => {
  const response = await api.get('/market/domestic')
  return response.data ?? {
    indices: [],
    market_breadth: { total: 0, advancing: 0, declining: 0, unchanged: 0, advance_ratio: 0, limit_up: 0, limit_down: 0 },
    volume: { total_volume: 0, total_turnover: 0, turnover_rate: 0 },
    sectors: [],
    north_bound: { net_inflow: 0, shanghai_inflow: 0, shenzhen_inflow: 0 },
    update_time: ''
  }
}
