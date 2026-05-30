/**
 * Request deduplication utility
 * Prevents duplicate concurrent requests to the same endpoint
 */

const pendingRequests = new Map<string, Promise<any>>()

export async function dedupeRequest<T>(
  key: string,
  fetcher: () => Promise<T>
): Promise<T> {
  const existing = pendingRequests.get(key)
  if (existing) {
    return existing as Promise<T>
  }

  const promise = fetcher()
  pendingRequests.set(key, promise)

  try {
    const result = await promise
    return result
  } finally {
    pendingRequests.delete(key)
  }
}

export function clearPendingRequests(): void {
  pendingRequests.clear()
}

export function getPendingRequestCount(): number {
  return pendingRequests.size
}
