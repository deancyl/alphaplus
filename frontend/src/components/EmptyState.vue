<script setup lang="ts">
import { computed } from 'vue'
/**
 * EmptyState Component
 * Displays a placeholder when no data is available
 * 
 * Design System Compliance:
 * - Uses CSS variables for all colors/spacing
 * - WCAG 44px touch target for action button
 * - Supports custom content via slots
 */

interface Props {
  icon?: string
  title?: string
  description?: string
  actionText?: string
  actionHandler?: () => void
}

const props = withDefaults(defineProps<Props>(), {
  icon: 'empty',
  title: '暂无数据',
  description: '',
  actionText: '',
  actionHandler: undefined,
})

const emit = defineEmits<{
  (e: 'action'): void
}>()

// Icon mapping for common empty states
const iconMap: Record<string, string> = {
  empty: '📭',
  search: '🔍',
  favorites: '⭐',
  error: '⚠️',
  chart: '📊',
  fund: '📈',
}

const displayIcon = computed(() => iconMap[props.icon] || props.icon || iconMap.empty)

// Handle action click - support both handler prop and event
const handleAction = () => {
  if (props.actionHandler) {
    props.actionHandler()
  }
  emit('action')
}
</script>

<template>
  <div class="empty-state">
    <div class="empty-state-icon">
      {{ displayIcon }}
    </div>
    
    <h3 class="empty-state-title">{{ title }}</h3>
    
    <p v-if="description" class="empty-state-description">
      {{ description }}
    </p>
    
    <!-- Default slot for custom content -->
    <slot />
    
    <button
      v-if="actionText"
      class="empty-state-action touch-target"
      @click="handleAction"
    >
      {{ actionText }}
    </button>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  text-align: center;
  min-height: 200px;
}

.empty-state-icon {
  font-size: 64px;
  margin-bottom: var(--spacing-md);
  opacity: 0.5;
  line-height: 1;
}

.empty-state-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-sm) 0;
}

.empty-state-description {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0 0 var(--spacing-md) 0;
  max-width: 280px;
}

.empty-state-action {
  min-height: var(--touch-target-min);
  min-width: var(--touch-target-min);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--brand-navy-dark);
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  touch-action: manipulation;
  transition: background-color 0.2s, transform 0.1s;
}

.empty-state-action:hover {
  background: var(--brand-navy-active);
}

.empty-state-action:active {
  transform: scale(0.98);
}

/* Mobile adjustments */
@media (max-width: 480px) {
  .empty-state {
    padding: var(--spacing-lg);
  }
  
  .empty-state-icon {
    font-size: 48px;
  }
  
  .empty-state-title {
    font-size: 14px;
  }
  
  .empty-state-description {
    font-size: 13px;
  }
}
</style>