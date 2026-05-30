<script setup lang="ts">
import { ref, onErrorCaptured, type ComponentPublicInstance } from 'vue'
import { Warning } from '@element-plus/icons-vue'
import { ElButton } from 'element-plus'

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
 * Vue 3 error capture lifecycle hook
 * Returns false to prevent the error from propagating to parent components
 */
onErrorCaptured((error: Error, instance: ComponentPublicInstance | null, info: string) => {
  hasError.value = true
  capturedError.value = error
  
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
