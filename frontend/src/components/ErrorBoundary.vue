<script setup lang="ts">
import { ref, computed, onErrorCaptured, type ComponentPublicInstance } from 'vue'
import { Warning } from '@element-plus/icons-vue'
import { ElButton } from 'element-plus'
import { logger } from '@/utils/logger'

/**
 * ErrorBoundary Component
 * 
 * Catches errors in child components to prevent cascading failures.
 * Uses Vue 3's onErrorCaptured lifecycle hook.
 * 
 * Design System Compliance:
 * - Uses CSS variables for all colors/spacing
 * - WCAG 44px touch target for retry button
 * - Element Plus integration for UI components
 * 
 * @example
 * <ErrorBoundary>
 *   <MyComponent />
 * </ErrorBoundary>
 * 
 * <ErrorBoundary error-message="自定义错误提示">
 *   <MyComponent />
 * </ErrorBoundary>
 */

interface Props {
  /** Custom error message to display */
  errorMessage?: string
  /** Custom retry button text */
  retryText?: string
}

withDefaults(defineProps<Props>(), {
  errorMessage: '组件加载失败',
  retryText: '重试',
})

const emit = defineEmits<{
  (e: 'error', error: Error, instance: ComponentPublicInstance | null, info: string): void
  (e: 'retry'): void
}>()

// Error state
const hasError = ref(false)
const capturedError = ref<Error | null>(null)

/**
 * One-line technical summary of the captured error, shown inside the fallback
 * so the failure stays diagnosable even when nothing reaches the console
 * (production builds, or a user who only sees a blank panel).
 */
const errorSummary = computed(() => {
  const err = capturedError.value
  if (!err) return ''
  const name = err.name || 'Error'
  const message = String(err.message || err).slice(0, 300)
  return `${name}: ${message}`
})

/**
 * Vue 3 error capture lifecycle hook
 * Returns false to prevent the error from propagating to parent components
 */
onErrorCaptured((error: Error, instance: ComponentPublicInstance | null, info: string) => {
  hasError.value = true
  capturedError.value = error

  // Surface the captured error: silently swallowing it made a blank panel
  // impossible to diagnose from the browser console.
  logger.info('captured error', { error, info, instance })

  // Emit error event for logging or analytics
  emit('error', error, instance, info)

  // Prevent error from propagating (stop cascading failures)
  return false
})

/**
 * Reset error state and retry rendering child components
 */
const handleRetry = () => {
  hasError.value = false
  capturedError.value = null
  emit('retry')
}
</script>

<template>
  <div class="error-boundary">
    <!-- Normal content slot -->
    <slot v-if="!hasError" />
    
    <!-- Fallback UI when error is captured -->
    <div v-else class="error-fallback">
      <div class="error-fallback__icon">
        <el-icon :size="48">
          <Warning />
        </el-icon>
      </div>
      
      <h3 class="error-fallback__title">
        {{ errorMessage }}
      </h3>
      
      <p class="error-fallback__description">
        请检查数据或刷新页面重试
      </p>

      <!-- The captured error itself: never swallow it silently. -->
      <details v-if="errorSummary" class="error-fallback__details">
        <summary class="error-fallback__summary">技术详情</summary>
        <p class="error-fallback__message">{{ errorSummary }}</p>
      </details>
      
      <!-- Retry button with WCAG touch target compliance -->
      <el-button
        type="primary"
        class="error-fallback__retry touch-target"
        @click="handleRetry"
      >
        {{ retryText }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.error-boundary {
  width: 100%;
  min-height: inherit;
}

.error-fallback {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  min-height: 200px;
  text-align: center;
  background-color: var(--bg-card);
  border-radius: 4px;
}

.error-fallback__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--spacing-md);
  color: var(--market-up);
  opacity: 0.8;
}

.error-fallback__title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-sm) 0;
}

.error-fallback__description {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0 0 var(--spacing-md) 0;
  max-width: 280px;
}

.error-fallback__retry {
  min-height: var(--touch-target-min);
  min-width: var(--touch-target-min);
  touch-action: manipulation;
}

.error-fallback__details {
  margin-top: var(--spacing-sm);
  max-width: 100%;
  font-size: 12px;
  color: var(--text-muted);
  text-align: left;
}

.error-fallback__summary {
  cursor: pointer;
  min-height: 32px;
  display: flex;
  align-items: center;
}

.error-fallback__message {
  margin: var(--spacing-xs, 4px) 0 0;
  padding: var(--spacing-sm);
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
  font-family: var(--font-mono, monospace);
  background-color: var(--bg-secondary, #f5f6f7);
  border-radius: 4px;
  color: var(--text-secondary);
}

/* Mobile adjustments */
@media (max-width: 480px) {
  .error-fallback {
    padding: var(--spacing-lg);
  }
  
  .error-fallback__icon {
    margin-bottom: var(--spacing-sm);
  }
  
  .error-fallback__title {
    font-size: 14px;
  }
  
  .error-fallback__description {
    font-size: 13px;
  }
}
</style>
