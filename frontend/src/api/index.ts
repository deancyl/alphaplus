/**
 * API service layer with axios
 * Optimized error handling with graceful degradation
 */
import axios, { AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'

export interface ApiMeta {
  status: number
  source: 'api' | 'error'
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
      source: 'api' as const
    }
  }),
  (error) => {
    const requestId = error.config?.headers?.['X-Request-ID']
    const endpoint = error.config?.url
    
    if (import.meta.env.DEV) {
      console.warn(`[API Warning] ${endpoint} failed (request: ${requestId})`)
    }
    
    if (error.response?.status >= 500 || error.code === 'ECONNABORTED') {
      ElMessage({
        message: '数据加载遇到问题，正在使用备用数据',
        type: 'warning',
        duration: 3000
      })
    }
    
    const errorInfo: ApiErrorInfo = {
      message: error.message,
      code: error.code,
      status: error.response?.status,
      isTimeout: error.code === 'ECONNABORTED'
    }
    
    return Promise.resolve({ 
      data: null, 
      _error: errorInfo,
      _meta: {
        status: error.response?.status || 0,
        source: 'error' as const
      }
    })
  }
)

const api = _api as AxiosInstance & {
  get<T = unknown>(url: string): Promise<ApiResponse<T>>
  post<T = unknown>(url: string, data?: unknown): Promise<ApiResponse<T>>
  put<T = unknown>(url: string, data?: unknown): Promise<ApiResponse<T>>
  delete<T = unknown>(url: string): Promise<ApiResponse<T>>
}

export default api
