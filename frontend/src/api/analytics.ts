/**
 * Analytics API endpoints
 */
import api from './index'

// Get fear/greed index
export const getFearGreedIndex = async (): Promise<Array<{
  trade_date: string
  composite_score: number
  sentiment_status: string
  factor_volatility: number | null
  factor_safe_haven: number | null
  factor_margin_ratio: number | null
  factor_volume_deviation: number | null
  factor_futures_basis: number | null
  factor_stock_strength: number | null
}>> => {
  return api.get('/analytics/fear-greed')
}

// Get ERP spread
export const getERPSpread = async (
  indexCode = '000300',
  riskFreeType = 'treasury_10y'
): Promise<Array<{
  index_code: string
  index_name: string
  trade_date: string
  pe_ttm: number
  treasury_yield_10y: number
  erp_spread: number
  percentile_rank_10y: number | null
  index_close_price: number | null
  risk_free_rate?: number
  risk_free_type?: string
}>> => {
  return api.get('/analytics/erp', { 
    params: { 
      index_code: indexCode,
      risk_free_type: riskFreeType
    } 
  })
}

// Get style strength
export const getStyleStrength = async (): Promise<Array<{
  trade_date: string
  index_code_num: string
  index_code_den: string
  ratio_value: number
  percentile_rank_3y: number | null
}>> => {
  return api.get('/analytics/style-strength')
}

// Get crowding analysis
export const getCrowdingAnalysis = async (
  category?: string
): Promise<Array<{
  asset_code: string
  trade_date: string
  category: string
  crowding_score: number
  pe_percentile: number
  close_price: number | null
}>> => {
  const params: Record<string, string> = {}
  if (category) params.category = category
  return api.get('/analytics/crowding', { params })
}

// Get rotation vectors
export const getRotationVectors = async (
  t0Date: string,
  t1Date: string,
  category = 'sector'
): Promise<Array<{
  asset_code: string
  asset_name: string
  t0_date: string
  t1_date: string
  t0_crowding: number
  t1_crowding: number
  t0_pe_percentile: number
  t1_pe_percentile: number
}>> => {
  return api.get('/analytics/rotation-vector', {
    params: {
      t0_date: t0Date,
      t1_date: t1Date,
      category,
    },
  })
}
