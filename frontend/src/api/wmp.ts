/**
 * Wealth Management Product (WMP) API endpoints
 * 银行理财产品筛选 API
 */
import api from './index'

// ==================== Types ====================

/**
 * WMP product item
 */
export interface WMPItem {
  product_code: string          // 产品代码
  product_name: string          // 产品名称
  yield_rate: number            // 收益率 (%)
  risk_level: string            // 风险等级 (PR1-PR5)
  duration: number              // 产品期限 (天)
  issuer: string                // 发行机构
  min_amount: number            // 最低认购金额 (万元)
  product_type?: string         // 产品类型 (净值型/预期收益型)
  currency?: string             // 货币类型 (CNY/USD等)
}

/**
 * WMP filter parameters
 */
export interface WMPFilterParams {
  yield_min?: number            // 最低收益率 (%)
  yield_max?: number            // 最高收益率 (%)
  risk_levels?: string[]        // 风险等级数组 (PR1-PR5)
  duration_min?: number         // 最短期限 (天)
  duration_max?: number         // 最长期限 (天)
  issuer?: string               // 发行机构搜索关键词
  page?: number                 // 页码
  page_size?: number            // 每页数量
  sort_by?: 'yield_rate' | 'duration' | 'min_amount'  // 排序字段
  sort_order?: 'asc' | 'desc'  // 排序方向
}

/**
 * WMP filter response
 */
export interface WMPFilterResponse {
  total: number                 // 总数量
  page: number                  // 当前页码
  page_size: number             // 每页数量
  products: WMPItem[]           // 产品列表
}

/**
 * WMP statistics response
 */
export interface WMPStatistics {
  total_products: number        // 产品总数
  avg_yield_rate: number        // 平均收益率
  avg_duration: number          // 平均期限
  risk_level_distribution: {    // 风险等级分布
    PR1: number
    PR2: number
    PR3: number
    PR4: number
    PR5: number
  }
  top_issuers: Array<{          // Top发行机构
    issuer: string
    product_count: number
    avg_yield: number
  }>
}

// ==================== API Functions ====================

/**
 * Filter WMP products with criteria
 */
export async function filterWMP(params: WMPFilterParams): Promise<WMPFilterResponse> {
  const response = await api.post('/wmp/filter', params)
  return response.data!
}

/**
 * Get all WMP products list
 */
export async function getWMPList(
  page: number = 1,
  pageSize: number = 50
): Promise<WMPFilterResponse> {
  const response = await api.get('/wmp/list', {
    params: { page, page_size: pageSize }
  })
  return response.data!
}

/**
 * Get WMP statistics
 */
export async function getWMPStatistics(): Promise<WMPStatistics> {
  const response = await api.get('/wmp/statistics')
  return response.data!
}

/**
 * Format yield rate for display
 */
export const formatYieldRate = (rate: number | null): string => {
  if (rate === null || rate === undefined) return '-'
  return `${rate.toFixed(2)}%`
}

/**
 * Format duration for display (days)
 */
export const formatDuration = (days: number | null): string => {
  if (days === null || days === undefined) return '-'
  if (days < 30) return `${days}天`
  if (days < 365) return `${Math.floor(days / 30)}个月`
  const years = Math.floor(days / 365)
  const months = Math.floor((days % 365) / 30)
  return months > 0 ? `${years}年${months}个月` : `${years}年`
}

/**
 * Format minimum amount for display (万元)
 */
export const formatMinAmount = (amount: number | null): string => {
  if (amount === null || amount === undefined) return '-'
  if (amount < 1) return `${(amount * 10000).toFixed(0)}元`
  return `${amount.toFixed(0)}万`
}

/**
 * Get risk level color class
 */
export const getRiskLevelClass = (level: string): string => {
  const levelMap: Record<string, string> = {
    'PR1': 'risk-low',
    'PR2': 'risk-low',
    'PR3': 'risk-medium',
    'PR4': 'risk-high',
    'PR5': 'risk-high',
  }
  return levelMap[level] || ''
}

/**
 * Get risk level badge color
 */
export const getRiskLevelColor = (level: string): string => {
  const colorMap: Record<string, string> = {
    'PR1': '#2E7D32',   // 绿色 - 低风险
    'PR2': '#43A047',   // 浅绿 - 较低风险
    'PR3': '#FF9800',   // 黄色 - 中风险
    'PR4': '#F57C00',   // 橙色 - 较高风险
    'PR5': '#D32F2F',   // 红色 - 高风险
  }
  return colorMap[level] || '#999'
}