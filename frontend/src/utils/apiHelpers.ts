/**
 * Ensures API response is an array.
 * Use when expecting array data from API.
 */
export function ensureArray<T>(response: unknown): T[] {
  // Handle normalized response shape { data, _error, _meta }
  if (response && typeof response === 'object') {
    if ('data' in response && Array.isArray(response.data)) {
      return response.data
    }
    if ('_error' in response && response._error) {
      if (import.meta.env.DEV) {
        console.warn('[API] Error response:', response._error)
      }
      return []
    }
  }
  
  // Handle direct array response (legacy support)
  if (Array.isArray(response)) {
    return response
  }
  
  // Fallback - unexpected shape
  if (import.meta.env.DEV) {
    console.warn('[API] Unexpected response shape:', response)
  }
  return []
}

/**
 * Check if response is an error.
 */
export function isErrorResponse(response: unknown): response is { data: null; _error: object } {
  return (
    response !== null &&
    typeof response === 'object' &&
    'data' in response &&
    response.data === null &&
    '_error' in response
  )
}

/**
 * Extract data from normalized API response.
 * Returns null for error responses.
 */
export function extractData<T>(response: unknown): T | null {
  if (response && typeof response === 'object' && 'data' in response) {
    return (response as { data: T }).data
  }
  return null
}

/**
 * Get error message from API response.
 * Returns null if no error.
 */
export function getErrorMessage(response: unknown): string | null {
  if (response && typeof response === 'object' && '_error' in response) {
    const error = (response as { _error: { message?: string } | null })._error
    return error?.message || null
  }
  return null
}