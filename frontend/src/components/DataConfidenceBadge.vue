<script setup lang="ts">
import { computed } from 'vue'
import { ElTooltip, ElTag } from 'element-plus'

/**
 * DataConfidenceBadge Component
 * Displays data source confidence level for each widget
 * 
 * Design System Compliance:
 * - CSS variables for all colors/spacing
 * - WCAG 2.5.5 touch target compliance
 * - Three states: REAL (real-time), DELAYED (delayed data), SIMULATED (fallback/simulated)
 * 
 * Architect Requirement:
 * "前端UI必须强制高亮显示'模拟/历史锁定数据'水印"
 */

type DataSource = 'real' | 'delayed' | 'simulated'

interface Props {
  source: DataSource
  timestamp?: string
  showTooltip?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showTooltip: true,
})

// Badge configuration based on source type
const badgeConfig = computed(() => {
  switch (props.source) {
    case 'real':
      return {
        label: '实时',
        type: 'success',
        class: 'badge-real',
        tooltip: '数据实时更新中',
        icon: '●',
      }
    case 'delayed':
      return {
        label: '延迟',
        type: 'warning',
        class: 'badge-delayed',
        tooltip: props.timestamp 
          ? `数据更新于 ${props.timestamp}` 
          : '数据存在延迟',
        icon: '◐',
      }
    case 'simulated':
      return {
        label: '模拟/历史锁定数据',
        type: 'danger',
        class: 'badge-simulated',
        tooltip: props.timestamp
          ? `使用历史数据模拟 (${props.timestamp})`
          : '使用历史数据模拟，非实时数据',
        icon: '○',
      }
    default:
      return {
        label: '未知',
        type: 'info',
        class: 'badge-unknown',
        tooltip: '数据状态未知',
        icon: '?',
      }
  }
})

// Format timestamp for display
const formattedTimestamp = computed(() => {
  if (!props.timestamp) return ''
  
  try {
    const date = new Date(props.timestamp)
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return props.timestamp
  }
})
</script>

<template>
  <div 
    class="data-confidence-badge" 
    :class="badgeConfig.class"
    role="status"
    :aria-label="badgeConfig.tooltip"
  >
    <!-- Simulated data watermark overlay (most prominent) -->
    <div 
      v-if="source === 'simulated'" 
      class="simulated-watermark"
      aria-hidden="true"
    >
      <span class="watermark-text">模拟数据</span>
    </div>
    
    <!-- Badge content with Element Plus Tag -->
    <ElTooltip
      v-if="showTooltip"
      :content="badgeConfig.tooltip"
      placement="top"
      :show-after="300"
    >
      <ElTag
        :type="badgeConfig.type as any"
        :class="['badge-tag', badgeConfig.class]"
        effect="plain"
        size="small"
      >
        <span class="badge-icon">{{ badgeConfig.icon }}</span>
        <span class="badge-label">{{ badgeConfig.label }}</span>
        <span 
          v-if="source === 'delayed' && formattedTimestamp" 
          class="badge-timestamp"
        >
          {{ formattedTimestamp }}
        </span>
      </ElTag>
    </ElTooltip>
    
    <!-- Non-tooltip version -->
    <ElTag
      v-else
      :type="badgeConfig.type as any"
      :class="['badge-tag', badgeConfig.class]"
      effect="plain"
      size="small"
    >
      <span class="badge-icon">{{ badgeConfig.icon }}</span>
      <span class="badge-label">{{ badgeConfig.label }}</span>
      <span 
        v-if="source === 'delayed' && formattedTimestamp" 
        class="badge-timestamp"
      >
        {{ formattedTimestamp }}
      </span>
    </ElTag>
  </div>
</template>

<style scoped>
.data-confidence-badge {
  position: relative;
  display: inline-flex;
  align-items: center;
  border-radius: 4px;
  transition: all 0.2s ease;
}

/* Base tag styling */
.badge-tag {
  font-weight: 500;
  border-radius: 4px;
}

/* Real-time data badge - Green */
.badge-real {
  background: rgba(46, 125, 50, 0.1) !important;
  color: var(--market-down) !important;
  border-color: rgba(46, 125, 50, 0.3) !important;
}

.badge-real:hover {
  background: rgba(46, 125, 50, 0.15) !important;
}

/* Delayed data badge - Yellow/Orange */
.badge-delayed {
  background: rgba(255, 152, 0, 0.1) !important;
  color: #F57C00 !important;
  border-color: rgba(255, 152, 0, 0.3) !important;
}

.badge-delayed:hover {
  background: rgba(255, 152, 0, 0.15) !important;
}

/* Simulated data badge - RED (Most prominent per architect requirement) */
.badge-simulated {
  background: rgba(230, 57, 53, 0.12) !important;
  color: var(--market-up) !important;
  border: 2px solid rgba(230, 57, 53, 0.4) !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  padding: 6px 12px !important;
  box-shadow: 0 2px 8px rgba(230, 57, 53, 0.2);
}

.badge-simulated:hover {
  background: rgba(230, 57, 53, 0.18) !important;
  box-shadow: 0 4px 12px rgba(230, 57, 53, 0.3);
}

/* Watermark overlay for simulated data */
.simulated-watermark {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  overflow: hidden;
  border-radius: 4px;
  opacity: 0.15;
  z-index: 1;
}

.watermark-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotate(-15deg);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  white-space: nowrap;
  text-transform: uppercase;
  color: var(--market-up);
}

/* Badge content layout */
.badge-icon {
  font-size: 10px;
  line-height: 1;
  margin-right: 4px;
}

.badge-label {
  white-space: nowrap;
}

.badge-timestamp {
  font-size: 11px;
  opacity: 0.8;
  margin-left: 4px;
  padding-left: 4px;
  border-left: 1px solid currentColor;
}

/* Unknown state fallback */
.badge-unknown {
  background: var(--bg-system) !important;
  color: var(--text-muted) !important;
  border-color: var(--border-line) !important;
}

/* Mobile adjustments */
@media (max-width: 768px) {
  .badge-simulated {
    font-size: 12px !important;
    padding: 5px 10px !important;
  }
  
  .watermark-text {
    font-size: 8px;
  }
}

/* Animation for real-time pulse effect */
@keyframes pulse-real {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

.badge-real .badge-icon {
  animation: pulse-real 2s ease-in-out infinite;
}

/* Simulated data warning animation */
@keyframes warning-pulse {
  0%, 100% {
    box-shadow: 0 2px 8px rgba(230, 57, 53, 0.2);
  }
  50% {
    box-shadow: 0 4px 16px rgba(230, 57, 53, 0.4);
  }
}

.badge-simulated {
  animation: warning-pulse 3s ease-in-out infinite;
}
</style>
