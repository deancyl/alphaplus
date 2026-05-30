/**
 * Indices Store - Singleton Pinia store for shared index data
 * Eliminates duplicate API requests across IndexBar.vue and Dashboard.vue
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getIndices } from '@/api/market'

export interface IndexQuote {
  name: string
  price: number
  change: number
  change_pct: number
}

export interface IndexMeta {
  is_fallback?: boolean
  source?: string
  timestamp?: string
}

export const useIndicesStore = defineStore('indices', () => {
  // State
  const indices = ref<Record<string, IndexQuote>>({})
  const meta = ref<IndexMeta | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastFetchTime = ref<number>(0)
  
  // Singleton interval - only one active at a time
  let refreshInterval: ReturnType<typeof setInterval> | null = null
  
  // Check if data is stale (older than 5 seconds)
  const isStale = computed(() => {
    return Date.now() - lastFetchTime.value > 5000
  })
  
  /**
   * Fetch indices data from API
   * Prevents duplicate fetches when already loading
   * Filters out _meta key and stores it separately
   */
  async function fetchIndices() {
    if (loading.value) return // Prevent duplicate fetches
    
    loading.value = true
    error.value = null
    
    try {
      const data = await getIndices()
      
      // Extract and store _meta separately
      if (data && '_meta' in data) {
        meta.value = data._meta as IndexMeta
        // Filter out _meta key from indices
        const indexData = Object.fromEntries(
          Object.entries(data).filter(([key]) => key !== '_meta')
        )
        indices.value = indexData
      } else {
        meta.value = null
        indices.value = data || {}
      }
      
      lastFetchTime.value = Date.now()
    } catch (err: any) {
      error.value = err.message || 'Failed to fetch indices'
      // Don't throw - allow graceful degradation
    } finally {
      loading.value = false
    }
  }
  
  /**
   * Start auto-refresh interval
   * Only starts if not already running (singleton pattern)
   * Includes visibility detection to pause when tab is hidden
   */
  function startAutoRefresh(intervalMs = 30000) {
    if (refreshInterval) return
    
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchIndices()
        if (!refreshInterval) {
          refreshInterval = setInterval(fetchIndices, intervalMs)
        }
      } else {
        if (refreshInterval) {
          clearInterval(refreshInterval)
          refreshInterval = null
        }
      }
    }
    
    document.addEventListener('visibilitychange', handleVisibilityChange)
    fetchIndices()
    if (document.visibilityState === 'visible') {
      refreshInterval = setInterval(fetchIndices, intervalMs)
    }
  }
  
  /**
   * Stop auto-refresh interval
   * Safe to call multiple times
   */
  function stopAutoRefresh() {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
  }
  
  return {
    // State
    indices,
    meta,
    loading,
    error,
    isStale,
    // Actions
    fetchIndices,
    startAutoRefresh,
    stopAutoRefresh
  }
})
