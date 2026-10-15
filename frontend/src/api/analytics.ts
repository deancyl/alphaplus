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
  const response = await api.get('/analytics/fear-greed')
  return response.data ?? []
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
  const response = await api.get('/analytics/erp', { 
    params: { 
      index_code: indexCode,
      risk_free_type: riskFreeType
    } 
  })
  return response.data ?? []
}

// Get style strength
export const getStyleStrength = async (): Promise<Array<{
  trade_date: string
  index_code_num: string
  index_code_den: string
  ratio_value: number
  percentile_rank_3y: number | null
}>> => {
  const response = await api.get('/analytics/style-strength')
  return response.data ?? []
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
  const response = await api.get('/analytics/crowding', { params })
  return response.data ?? []
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
  const response = await api.get('/analytics/rotation-vector', {
    params: {
      t0_date: t0Date,
      t1_date: t1Date,
      category,
    },
  })
  return response.data ?? []
}

// --- Forecast (AI / economic-model trend analysis) -------------------------

export interface ForecastLLM {
  enabled: boolean
  available: boolean
  api_style: string
  model: string | null
  text: string | null
  error: string | null
  usage?: Record<string, unknown> | null
  note?: string
}

export interface ForecastMetrics {
  annualised_drift: number
  annualised_volatility: number
  max_drawdown: number
  hurst: number | null
  valuation_z: number | null
  valuation_percentile: number | null
  regime: string
}

export interface ForecastComponent {
  name: string
  weight: number
  daily_drift: number
  annualised_drift: number
  rationale: string
}

export interface ForecastData {
  index_code: string
  index_name: string
  as_of: string
  last_close: number
  observations: number
  horizon_days: number
  metrics: ForecastMetrics
  model: {
    kind: string
    components: ForecastComponent[]
    blended_daily_drift: number
  }
  projection: {
    dates: string[]
    quantiles: {
      p10: number[]
      p25: number[]
      p50: number[]
      p75: number[]
      p90: number[]
    }
  }
  expected_band: {
    median_return: number
    p10_return: number
    p90_return: number
    prob_up: number
  }
  basis: string[]
  limits: string[]
  available: Record<string, unknown>
  is_simulated: boolean
  llm: ForecastLLM
}

/**
 * Get a trend forecast for an index.
 * Note: the backend returns the unified envelope, so we read `response.data.data`.
 */
export const getForecast = async (
  indexCode: string,
  horizon = 20,
  lookback = 500,
  withLlm = false
): Promise<ForecastData | null> => {
  const response = await api.get(`/analytics/forecast/${indexCode}`, {
    params: { horizon, lookback, with_llm: withLlm },
  })
  const body = response.data as { ok?: boolean; data?: ForecastData }
  if (body && body.ok === false) return null
  return body?.data ?? null
}
