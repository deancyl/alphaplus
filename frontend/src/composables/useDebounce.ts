/**
 * useDebounce composable
 * Provides debounced function execution with Vue 3 composition API
 * 
 * @description
 * Creates a debounced version of a function that delays execution
 * until after the specified wait time has elapsed since the last call.
 * 
 * @example
 * const debouncedSearch = useDebounce((query: string) => {
 *   searchAPI(query)
 * }, 250)
 * 
 * debouncedSearch('test') // Will execute after 250ms if no more calls
 * debouncedSearch.cancel() // Cancel pending execution
 * debouncedSearch.flush() // Immediately execute pending call
 */

import { ref, onUnmounted } from 'vue'

export interface DebouncedFunction<T extends (...args: any[]) => any> {
  (...args: Parameters<T>): void
  cancel: () => void
  flush: () => void
  pending: () => boolean
}

/**
 * Creates a debounced function with cancel/flush capabilities
 * 
 * @param fn - The function to debounce
 * @param wait - Number of milliseconds to delay (default: 300ms)
 * @param options - Configuration options
 * @param options.leading - Execute on the leading edge of the timeout
 * @param options.maxWait - Maximum time the function is allowed to be delayed
 * @returns Debounced function with cancel/flush methods
 */
export function useDebounce<T extends (...args: any[]) => any>(
  fn: T,
  wait: number = 300,
  options: {
    leading?: boolean
    maxWait?: number
  } = {}
): DebouncedFunction<T> {
  const { leading = false, maxWait } = options

  let timeoutId: ReturnType<typeof setTimeout> | null = null
  let lastCallTime = 0
  let lastArgs: Parameters<T> | null = null
  let lastThis: any = null
  let result: ReturnType<T> | undefined

  const isPending = ref(false)

  const invokeFunc = (time: number) => {
    const args = lastArgs
    const thisArg = lastThis

    lastArgs = null
    lastThis = null
    lastCallTime = time
    isPending.value = false

    if (args) {
      result = fn.apply(thisArg, args)
    }
    return result
  }

  const startTimer = (pendingFunc: () => void, waitTime: number) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    timeoutId = setTimeout(pendingFunc, waitTime)
  }

  const shouldInvoke = (time: number) => {
    const timeSinceLastCall = time - lastCallTime

    // First call or enough time has passed
    return lastCallTime === 0 || timeSinceLastCall >= wait
  }

  const trailingEdge = (time: number) => {
    timeoutId = null

    // Only invoke if we have pending args
    if (lastArgs) {
      return invokeFunc(time)
    }

    isPending.value = false
    return result
  }

  const timerExpired = () => {
    const currentTime = Date.now()
    if (shouldInvoke(currentTime)) {
      return trailingEdge(currentTime)
    }

    // Calculate remaining wait time
    const timeSinceLastCall = currentTime - lastCallTime
    const remainingWait = wait - timeSinceLastCall

    // Check maxWait constraint
    if (maxWait !== undefined) {
      const timeSinceLastInvoke = currentTime - lastCallTime
      const remainingMaxWait = maxWait - timeSinceLastInvoke
      if (remainingMaxWait <= 0) {
        return trailingEdge(currentTime)
      }
      startTimer(timerExpired, Math.min(remainingWait, remainingMaxWait))
    } else {
      startTimer(timerExpired, remainingWait)
    }
  }

  const leadingEdge = (time: number) => {
    // Reset any previous timer
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    lastCallTime = time

    // Start the timer for trailing edge
    startTimer(timerExpired, wait)

    // Invoke if leading option is true
    if (leading) {
      return invokeFunc(time)
    }

    isPending.value = true
    return result
  }

  const debounced = function (this: any, ...args: Parameters<T>) {
    const time = Date.now()
    const isInvoking = shouldInvoke(time)

    lastArgs = args
    lastThis = this

    if (isInvoking) {
      if (timeoutId === null) {
        return leadingEdge(time)
      }

      if (maxWait !== undefined) {
        // Handle maxWait constraint
        startTimer(timerExpired, wait)
        return invokeFunc(time)
      }
    }

    if (timeoutId === null) {
      startTimer(timerExpired, wait)
    }

    isPending.value = true
    return result
  } as DebouncedFunction<T>

  debounced.cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    timeoutId = null
    lastArgs = null
    lastThis = null
    lastCallTime = 0
    isPending.value = false
  }

  debounced.flush = () => {
    if (timeoutId && lastArgs) {
      const time = Date.now()
      clearTimeout(timeoutId)
      return trailingEdge(time)
    }
    return result
  }

  debounced.pending = () => {
    return isPending.value
  }

  // Cleanup on component unmount
  onUnmounted(() => {
    debounced.cancel()
  })

  return debounced
}

/**
 * Simplified debounce for common use cases
 * Returns a reactive debounced value that updates after delay
 * 
 * @param value - Reactive ref to debounce
 * @param wait - Delay in milliseconds (default: 300ms)
 * @returns Debounced ref
 * 
 * @example
 * const searchTerm = ref('')
 * const debouncedSearch = useDebouncedRef(searchTerm, 250)
 * // debouncedSearch.value will update 250ms after searchTerm stops changing
 */
export function useDebouncedRef<T>(value: T, wait: number = 300) {
  const debouncedValue = ref(value) as import('vue').Ref<T>
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  const update = (newValue: T) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    timeoutId = setTimeout(() => {
      debouncedValue.value = newValue
    }, wait)
  }

  onUnmounted(() => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
  })

  return {
    debouncedValue,
    update,
  }
}
