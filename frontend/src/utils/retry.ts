/**
 * Exponential backoff retry utility with jitter
 */

interface RetryOptions {
  maxRetries?: number
  baseDelay?: number
  maxDelay?: number
  jitter?: number
}

export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const {
    maxRetries = 5,
    baseDelay = 1000,
    maxDelay = 30000,
    jitter = 500
  } = options

  let lastError: Error | undefined

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error as Error
      
      if (attempt === maxRetries - 1) {
        break
      }

      const delay = Math.min(
        baseDelay * Math.pow(2, attempt) + Math.random() * jitter,
        maxDelay
      )

      await new Promise(resolve => setTimeout(resolve, delay))
    }
  }

  throw lastError
}

export function createRetryWrapper<T extends (...args: any[]) => Promise<any>>(
  fn: T,
  options: RetryOptions = {}
): T {
  return (async (...args: Parameters<T>) => {
    return retryWithBackoff(() => fn(...args), options)
  }) as T
}
