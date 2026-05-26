/**
 * Market API endpoints
 */
import api from './index'

// Get index quotes (5s cache)
export const getIndices = async (): Promise<Record<string, {
  name: string
  price: number
  change: number
  change_pct: number
}>> => {
  return api.get('/market/indices')
}

// Get index valuation
export const getIndexValuation = async (
  indexCode: string
): Promise<Array<{
  trade_date: string
  pe_ttm: number
  percentile_rank_10y: number
  moving_mean_10y: number | null
  index_close_price: number | null
}>> => {
  return api.get('/market/valuation', { params: { index_code: indexCode } })
}

// Get bond yield curve
export const getBondYieldCurve = async (
  bondType = '国债',
  tradeDate?: string
): Promise<Record<string, Array<{ tenor: number; yield_ytm: number }>>> => {
  const params: Record<string, string> = { bond_type: bondType }
  if (tradeDate) params.trade_date = tradeDate
  return api.get('/market/bond/yield-curve', { params })
}

// Get money market rates
export const getMoneyMarketRates = async (): Promise<Array<{
  rate_code: string
  trade_date: string
  rate_value: number
  sparkline_data: string | null
}>> => {
  return api.get('/market/bond/money-rates')
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
  return api.get('/market/bond/rate-history', {
    params: { rate_code: rateCode, days }
  })
}

// Get market heatmap
export const getMarketHeatmap = async (): Promise<{
  rows: string[]
  cols: string[]
  cells: Array<{ row: string; col: string; value: number; color: string }>
}> => {
  return api.get('/market/heatmap')
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
  return api.get('/market/futures/quotes', { params })
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
  return api.get('/market/global')
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
  return api.get('/market/domestic')
}
