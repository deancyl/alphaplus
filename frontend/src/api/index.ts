/**
 * API service layer with axios
 * Optimized error handling with graceful degradation
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000, // Reduced from 30s to 15s
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - add request ID for debugging
api.interceptors.request.use(
  (config) => {
    config.headers['X-Request-ID'] = Date.now().toString()
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor - graceful error handling
api.interceptors.response.use(
  (response) => {
    // Check for fallback data indicator
    if (response.data?._meta?.is_fallback) {
      // Only warn in development, don't show user notification
      if (import.meta.env.DEV) {
        console.warn(`[API Fallback] ${response.config.url}: ${response.data._meta.error}`)
      }
    }
    return response.data
  },
  (error) => {
    const requestId = error.config?.headers?.['X-Request-ID']
    const endpoint = error.config?.url
    
    // Only log in development mode
    if (import.meta.env.DEV) {
      console.warn(`[API Warning] ${endpoint} failed (request: ${requestId})`)
    }
    
    // User-friendly notification for critical errors only
    if (error.response?.status >= 500 || error.code === 'ECONNABORTED') {
      ElMessage({
        message: '数据加载遇到问题，正在使用备用数据',
        type: 'warning',
        duration: 3000
      })
    }
    
    // Return resolved promise with error info - allows graceful degradation
    return Promise.resolve({ 
      data: null, 
      _error: { 
        message: error.message,
        code: error.code,
        isTimeout: error.code === 'ECONNABORTED'
      }
    })
  }
)

export default api
