/**
 * API service layer with axios
 *
 * Contract (kept deliberately stable — every view depends on it):
 *   - Success and failure BOTH resolve. Failure is visible as
 *     `_error != null` and `_meta.source === 'error'`; never as an exception.
 *   - `_meta` carries the freshness fields the backend declares
 *     (`asOf` / `dataSource` / `degraded`) so components like
 *     FreshnessNote / DataConfidenceBadge can show 数据截至 without each
 *     view re-inventing the extraction.
 *
 * Failure copy rule (research-terminal + PRD-v0.2 §7.5):
 *   a toast may never claim a fallback that does not exist, and may never
 *   storm (one per endpoint per 60s), because auto-refresh loops re-fire it.
 */
import axios, { AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { logger } from '@/utils/logger'

export interface ApiMeta {
  status: number
  source: 'api' | 'error'
  /** 业务时点：后端 _meta.as_of / asOf（数据所属交易日），缺失为 null */
  asOf?: string | null
  /** 后端声明的数据源标签（如 database / live / eastmoney） */
  dataSource?: string | null
  /** 后端声明的降级标记（degraded / is_fallback） */
  degraded?: boolean
  requestId?: string
}

export interface ApiErrorInfo {
  message: string
  code?: string
  status?: number
  isTimeout?: boolean
}

export interface ApiResponse<T = unknown> {
  data: T | null
  _error: ApiErrorInfo | null
  _meta: ApiMeta
}

/** 同一端点同一状态码 60 秒内只提示一次，避免轮询制造弹幕。 */
const TOAST_WINDOW_MS = 60_000
const recentToasts = new Map<string, number>()

const shouldToast = (key: string): boolean => {
  const now = Date.now()
  const last = recentToasts.get(key)
  if (last && now - last < TOAST_WINDOW_MS) return false
  // 顺手清理过期记录，防止 Map 无限增长
  for (const [k, t] of recentToasts) {
    if (now - t >= TOAST_WINDOW_MS) recentToasts.delete(k)
  }
  recentToasts.set(key, now)
  return true
}

/** 从后端信封里提取新鲜度字段；裸数组/非对象响应返回空。 */
const extractBackendMeta = (body: unknown): Partial<ApiMeta> => {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return {}
  const meta = (body as Record<string, unknown>)._meta as
    | Record<string, unknown>
    | undefined
  if (!meta || typeof meta !== 'object') return {}
  const asOf =
    (typeof meta.as_of === 'string' && meta.as_of) ||
    (typeof meta.asOf === 'string' && meta.asOf) ||
    (typeof meta.trade_date === 'string' && meta.trade_date) ||
    null
  return {
    asOf: asOf ?? null,
    dataSource: typeof meta.source === 'string' ? meta.source : null,
    degraded: meta.degraded === true || meta.is_fallback === true,
  }
}

const _api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

_api.interceptors.request.use(
  (config) => {
    config.headers['X-Request-ID'] = Date.now().toString()
    return config
  },
  (error) => Promise.reject(error)
)

_api.interceptors.response.use(
  // @ts-expect-error - Axios interceptor type inference issue with custom response wrapper
  (response) => ({
    data: response.data,
    _error: null,
    _meta: {
      status: response.status,
      source: 'api' as const,
      requestId: response.config?.headers?.['X-Request-ID'] as string | undefined,
      ...extractBackendMeta(response.data),
    },
  }),
  (error) => {
    const requestId = error.config?.headers?.['X-Request-ID']
    const endpoint = error.config?.url || 'unknown'

    if (import.meta.env.DEV) {
      logger.info(`API request failed: ${endpoint}`, { requestId })
    }

    if (error.response?.status >= 500 || error.code === 'ECONNABORTED') {
      // 诚实文案：只陈述失败，不虚构“备用数据”。按端点去重。
      const key = `${endpoint}:${error.response?.status || 'timeout'}`
      if (shouldToast(key)) {
        const detail =
          error.code === 'ECONNABORTED' ? '请求超时' : '服务暂时不可用'
        ElMessage({
          message: `${detail}：${endpoint}，相关内容将显示为空`,
          type: 'warning',
          duration: 3000,
        })
      }
    }

    const errorInfo: ApiErrorInfo = {
      message: error.message,
      code: error.code,
      status: error.response?.status,
      isTimeout: error.code === 'ECONNABORTED',
    }

    return Promise.resolve({
      data: null,
      _error: errorInfo,
      _meta: {
        status: error.response?.status || 0,
        source: 'error' as const,
        requestId: requestId as string | undefined,
      },
    })
  }
)

/**
 * 客户端接口：签名与 axios 方法对齐（可带 config），但返回类型**永远**是
 * ApiResponse<T>。必须用独立 interface 完整覆盖、而不是与 AxiosInstance
 * 取交叉——交叉时 `get(url, config)` 会命中 axios 自身的重载，返回
 * `AxiosResponse<T>`，调用方读 `_error`/`_meta` 就会 TS2339。
 * 泛型默认 any 与 axios 一致，未显式标注的调用点保持既有宽松行为。
 */
export interface ApiClient {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
  post<T = any>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
  put<T = any>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
}

const api = _api as unknown as ApiClient

export default api
