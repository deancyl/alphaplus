/**
 * Portfolio & Backtest API endpoints
 * FOF组合回测系统API
 */
import api from './index'

// ==================== Types ====================

/**
 * Fund search result for autocomplete
 */
export interface FundSearchResult {
  fund_code: string
  fund_name: string
  fund_type: string
  company_name: string
}

/**
 * Portfolio fund item with weight allocation
 */
export interface PortfolioFundItem {
  fund_code: string
  fund_name: string
  weight: number  // Weight percentage (0-100)
}

/**
 * Portfolio creation request
 */
export interface PortfolioCreateRequest {
  name: string
  funds: PortfolioFundItem[]
}

/**
 * Portfolio item from list
 */
export interface PortfolioItem {
  id: string
  name: string
  funds: PortfolioFundItem[]
  created_at: string
  updated_at: string
}

/**
 * Backtest configuration
 */
export interface BacktestConfig {
  start_date: string    // YYYY-MM-DD
  end_date: string      // YYYY-MM-DD
  benchmark: string     // Benchmark index code (e.g., '000300', '000905', '399006')
  linking_method?: 'auto' | 'carino' | 'menchero'  // Multi-period Brinson linking method
  period_granularity?: 'daily' | 'weekly' | 'monthly'  // Period granularity for multi-period attribution
  use_adjusted_nav?: boolean  // Use adjusted NAV (复权净值) for dividend reinvestment
}

/**
 * Performance statistics
 */
export interface PerformanceStats {
  total_return: number       // Total return (%)
  annual_return: number      // Annualized return (%)
  max_drawdown: number       // Maximum drawdown (%)
  sharpe_ratio: number       // Sharpe ratio
  volatility: number         // Annualized volatility (%)
  win_rate: number | null    // Win rate (%)
  sortino_ratio: number | null  // Sortino ratio
  calmar_ratio: number | null   // Calmar ratio
}

/**
 * Brinson attribution result
 */
export interface BrinsonAttribution {
  allocation_effect: number      // 配置效应 (%)
  selection_effect: number       // 选择效应 (%)
  interaction_effect: number     // 交互效应 (%)
  total_excess_return: number    // 总超额收益 (%)
  details: BrinsonDetailItem[]   // Detailed breakdown by asset class
}

/**
 * Multi-period Brinson attribution result
 */
export interface MultiPeriodBrinsonAttribution {
  allocation_effect: number      // 累计配置效应 (%)
  selection_effect: number       // 累计选择效应 (%)
  interaction_effect: number     // 累计交互效应 (%)
  total_excess_return: number    // 总超额收益 (%)
  residual: number               // 残差 (should be < 1e-12)
  linking_method: 'carino' | 'menchero'  // Method used
  periods: PeriodAttribution[]   // Per-period breakdown
}

/**
 * Single period attribution breakdown
 */
export interface PeriodAttribution {
  period_start: string     // Period start date
  period_end: string       // Period end date
  allocation_effect: number  // Period allocation effect (%)
  selection_effect: number   // Period selection effect (%)
  interaction_effect: number // Period interaction effect (%)
  excess_return: number      // Period excess return (%)
}

/**
 * Brinson detail item by asset class
 */
export interface BrinsonDetailItem {
  asset_class: string       // Asset class name (行业/资产类别)
  portfolio_weight: number  // Portfolio weight (%)
  benchmark_weight: number  // Benchmark weight (%)
  portfolio_return: number  // Portfolio return (%)
  benchmark_return: number  // Benchmark return (%)
  allocation: number        // Allocation contribution (%)
  selection: number         // Selection contribution (%)
  interaction: number       // Interaction contribution (%)
  total: number             // Total contribution (%)
}

/**
 * NAV point for time series chart
 */
export interface NAVPoint {
  date: string    // YYYY-MM-DD
  nav: number     // Net asset value
}

/**
 * Backtest result
 */
export interface BacktestResult {
  portfolio_id: string
  portfolio_name: string
  benchmark_code: string
  benchmark_name: string
  start_date: string
  end_date: string
  performance: PerformanceStats
  portfolio_nav_series: NAVPoint[]
  benchmark_nav_series: NAVPoint[]
  brinson_attribution: BrinsonAttribution
  multi_period_brinson_attribution?: MultiPeriodBrinsonAttribution  // Multi-period attribution (optional)
  is_simulated: boolean   // Whether data is simulated (fallback)
}

// ==================== API Functions ====================

/**
 * Search funds by query (autocomplete)
 */
export const searchFunds = async (
  query: string,
  limit: number = 10
): Promise<FundSearchResult[]> => {
  const response = await api.get('/fund/search', {
    params: { q: query, limit }
  })
  return response.data ?? []
}

/**
 * Create a new portfolio
 */
export const createPortfolio = async (
  data: PortfolioCreateRequest
): Promise<PortfolioItem> => {
  const response = await api.post('/portfolio', data)
  return response.data!
}

/**
 * Get list of portfolios
 */
export const getPortfolios = async (): Promise<PortfolioItem[]> => {
  const response = await api.get('/portfolio')
  return response.data ?? []
}

/**
 * Get single portfolio by ID
 */
export const getPortfolio = async (
  id: string
): Promise<PortfolioItem> => {
  const response = await api.get(`/portfolio/${id}`)
  return response.data!
}

/**
 * Delete portfolio
 */
export const deletePortfolio = async (
  id: string
): Promise<void> => {
  const response = await api.delete(`/portfolio/${id}`)
  return response.data!
}

/**
 * Run backtest on a portfolio
 */
export const runBacktest = async (
  portfolioId: string,
  config: BacktestConfig
): Promise<BacktestResult> => {
  const response = await api.post(`/portfolio/${portfolioId}/backtest`, config)
  return response.data!
}

// ==================== Constants ====================

/**
 * Benchmark options for selector
 */
export const BENCHMARK_OPTIONS = [
  { code: '000300', name: '沪深300', fullName: '沪深300指数' },
  { code: '000905', name: '中证500', fullName: '中证500指数' },
  { code: '399006', name: '创业板指', fullName: '创业板指数' },
  { code: '000016', name: '上证50', fullName: '上证50指数' },
  { code: '000852', name: '中证1000', fullName: '中证1000指数' },
  { code: '399005', name: '中小板指', fullName: '中小板指数' },
]