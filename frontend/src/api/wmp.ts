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
 * WMP filter response.
 *
 * `unavailable` is set when the backend reports that no live WMP source is
 * wired (HTTP 503), so the view can say so explicitly instead of rendering an
 * empty result set that reads as "no products matched".
 */
export interface WMPFilterResponse {
  total: number                 // 总数量
  page: number                  // 当前页码
  page_size: number             // 每页数量
  products: WMPItem[]           // 产品列表
  unavailable?: boolean
  message?: string
}

/**
 * WMP statistics response
 */
export interface WMPStatistics {
  total_products: number          // 产品总数
  avg_yield_rate: number | null   // 平均收益率 (%) — null when unavailable
  avg_duration: number | null     // 平均期限 (天) — null when unavailable
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
  // Raw backend aliases. The live /wmp/statistics returns the aggregate under
  // `statistics` with total_count / avg_yield / risk_distribution / issuer_count,
  // while this view reads total_products / avg_yield_rate / avg_duration.
  // The mismatch previously made `avg_yield_rate.toFixed()` throw inside a
  // computed and the ErrorBoundary blanked the whole page.
  total_count?: number
  avg_yield?: number
  issuer_count?: number
  risk_distribution?: Record<string, number>
}

// ==================== API Functions ====================

/**
 * Filter WMP products with criteria.
 *
 * A 503 from the backend means "no live WMP source is wired" — surfaced as an
 * `unavailable` result so the view can state that plainly, rather than showing
 * an empty table as if the filters had simply matched nothing.
 */
export async function filterWMP(params: WMPFilterParams): Promise<WMPFilterResponse> {
  const response = await api.post<WMPFilterResponse>('/wmp/filter', params)
  if (response._error || response._meta.source === 'error') {
    const unavailable = response._error?.status === 503
    return {
      total: 0,
      page: params.page ?? 1,
      page_size: params.page_size ?? 50,
      products: [],
      unavailable,
      message: unavailable ? '理财产品实时数据源暂未接入' : '数据加载失败',
    }
  }
  return response.data ?? { total: 0, page: 1, page_size: 50, products: [] }
}

/**
 * Get all WMP products list
 */
export async function getWMPList(
  page: number = 1,
  pageSize: number = 50
): Promise<WMPFilterResponse> {
  const response = await api.get<WMPFilterResponse>('/wmp/list', {
    params: { page, page_size: pageSize }
  })
  if (response._error || response._meta.source === 'error') {
    return {
      total: 0,
      page,
      page_size: pageSize,
      products: [],
      unavailable: response._error?.status === 503,
      message: '数据加载失败',
    }
  }
  return response.data ?? { total: 0, page, page_size: pageSize, products: [] }
}

/**
 * Get WMP statistics.
 *
 * Normalises the live backend shape (nested under `statistics`, using
 * total_count/avg_yield/…) into the flat contract the view consumes, so a
 * backend field rename can never crash the page again.
 */
export async function getWMPStatistics(): Promise<WMPStatistics> {
  const response = await api.get('/wmp/statistics')
  const raw = (response.data?.statistics ?? response.data ?? {}) as Partial<WMPStatistics>
  const total = raw.total_products ?? raw.total_count ?? 0
  const avgYield = raw.avg_yield_rate ?? raw.avg_yield ?? null
  return {
    total_products: total,
    avg_yield_rate: avgYield,
    // 平均期限 is not published by the live aggregate: stay null (renders "-")
    // rather than inventing a number.
    avg_duration: raw.avg_duration ?? null,
    risk_level_distribution: raw.risk_level_distribution ?? (raw.risk_distribution as WMPStatistics['risk_level_distribution']) ?? { PR1: 0, PR2: 0, PR3: 0, PR4: 0, PR5: 0 },
    top_issuers: raw.top_issuers ?? [],
    total_count: raw.total_count,
    avg_yield: raw.avg_yield,
    issuer_count: raw.issuer_count,
  }
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