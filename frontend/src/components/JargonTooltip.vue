<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

/**
 * JargonTooltip Component
 * Displays financial term definitions on hover (desktop) or click (mobile)
 * 
 * Design System Compliance:
 * - Touch target >= 44px (WCAG 2.5.5)
 * - CSS variables for all colors/spacing
 * - Position-aware tooltip placement
 */

type TooltipPosition = 'top' | 'bottom' | 'left' | 'right'

interface Props {
  term: string
  definition: string
  position?: TooltipPosition
}

const props = withDefaults(defineProps<Props>(), {
  position: 'top',
})

// Tooltip visibility state
const isVisible = ref(false)
const triggerRef = ref<HTMLElement | null>(null)

// Detect touch device for interaction mode
const isTouchDevice = ref(false)

onMounted(() => {
  // Check if device supports touch
  isTouchDevice.value = 'ontouchstart' in window || navigator.maxTouchPoints > 0
})

// Toggle tooltip (for click/mobile interaction)
const toggleTooltip = () => {
  if (isTouchDevice.value) {
    isVisible.value = !isVisible.value
  }
}

// Show tooltip (for hover/desktop interaction)
const showTooltip = () => {
  if (!isTouchDevice.value) {
    isVisible.value = true
  }
}

// Hide tooltip (for hover/desktop interaction)
const hideTooltip = () => {
  if (!isTouchDevice.value) {
    isVisible.value = false
  }
}

// Close on outside click (for mobile)
const handleOutsideClick = (e: MouseEvent | TouchEvent) => {
  if (triggerRef.value && !triggerRef.value.contains(e.target as Node)) {
    isVisible.value = false
  }
}

// Add/remove document click listener when tooltip is visible
watch(isVisible, (newVal) => {
  if (newVal && isTouchDevice.value) {
    document.addEventListener('click', handleOutsideClick)
    document.addEventListener('touchstart', handleOutsideClick)
  } else {
    document.removeEventListener('click', handleOutsideClick)
    document.removeEventListener('touchstart', handleOutsideClick)
  }
})

// Cleanup on unmount
onUnmounted(() => {
  document.removeEventListener('click', handleOutsideClick)
  document.removeEventListener('touchstart', handleOutsideClick)
})

// Computed tooltip position classes
const tooltipClasses = computed(() => [
  `tooltip--${props.position}`,
  { 'tooltip--visible': isVisible.value },
])
</script>

<template>
  <span
    ref="triggerRef"
    class="jargon-tooltip-trigger touch-target"
    @mouseenter="showTooltip"
    @mouseleave="hideTooltip"
    @click="toggleTooltip"
  >
    <span class="jargon-term">{{ term }}</span>
    <span class="jargon-indicator" aria-hidden="true">?</span>
    
    <!-- Tooltip content -->
    <span
      v-if="isVisible"
      class="jargon-tooltip"
      :class="tooltipClasses"
      role="tooltip"
    >
      {{ definition }}
    </span>
  </span>
</template>

<style scoped>
.jargon-tooltip-trigger {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  cursor: help;
  touch-action: manipulation;
  /* Ensure minimum touch target of 44px */
  min-height: var(--touch-target-min);
  padding: var(--spacing-xs) var(--spacing-sm);
  margin: calc(-1 * var(--spacing-xs)) calc(-1 * var(--spacing-sm));
  border-radius: 4px;
  transition: background-color 0.2s;
}

.jargon-tooltip-trigger:hover {
  background: var(--bg-system);
}

.jargon-term {
  color: var(--text-primary);
  font-weight: 500;
  text-decoration: underline;
  text-decoration-style: dotted;
  text-underline-offset: 3px;
}

.jargon-indicator {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  background: var(--bg-system);
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  line-height: 1;
}

.jargon-tooltip {
  position: absolute;
  z-index: 1000;
  max-width: 280px;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--text-primary);
  color: white;
  font-size: 13px;
  line-height: 1.5;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.2s, visibility 0.2s;
  pointer-events: none;
}

.jargon-tooltip.tooltip--visible {
  opacity: 1;
  visibility: visible;
}

/* Position variants */
.jargon-tooltip.tooltip--top {
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-bottom: var(--spacing-sm);
}

.jargon-tooltip.tooltip--bottom {
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-top: var(--spacing-sm);
}

.jargon-tooltip.tooltip--left {
  right: 100%;
  top: 50%;
  transform: translateY(-50%);
  margin-right: var(--spacing-sm);
}

.jargon-tooltip.tooltip--right {
  left: 100%;
  top: 50%;
  transform: translateY(-50%);
  margin-left: var(--spacing-sm);
}

/* Arrow indicator */
.jargon-tooltip::after {
  content: '';
  position: absolute;
  border: 6px solid transparent;
}

.tooltip--top::after {
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border-top-color: var(--text-primary);
}

.tooltip--bottom::after {
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  border-bottom-color: var(--text-primary);
}

.tooltip--left::after {
  left: 100%;
  top: 50%;
  transform: translateY(-50%);
  border-left-color: var(--text-primary);
}

.tooltip--right::after {
  right: 100%;
  top: 50%;
  transform: translateY(-50%);
  border-right-color: var(--text-primary);
}

/* Mobile adjustments */
@media (max-width: 768px) {
  .jargon-tooltip {
    max-width: 220px;
    font-size: 12px;
  }
  
  /* On mobile, prefer bottom position to avoid viewport overflow */
  .jargon-tooltip.tooltip--top {
    bottom: auto;
    top: 100%;
    margin-top: var(--spacing-sm);
    margin-bottom: 0;
  }
}
</style>