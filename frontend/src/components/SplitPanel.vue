<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

interface Props {
  direction?: 'horizontal' | 'vertical'
  initialLeftSize?: number
  minLeftSize?: number
  maxLeftSize?: number
  collapsedSize?: number
  storageKey?: string
}

const props = withDefaults(defineProps<Props>(), {
  direction: 'horizontal',
  initialLeftSize: 320,
  minLeftSize: 200,
  maxLeftSize: 600,
  collapsedSize: 40,
  storageKey: 'splitpanel-left-size',
})

const emit = defineEmits<{
  resize: [size: number]
}>()

// State
const leftSize = ref(props.initialLeftSize)
const isCollapsed = ref(false)
const isDragging = ref(false)
const containerRef = ref<HTMLDivElement | null>(null)

// Debounce helper
let resizeDebounceTimer: ReturnType<typeof setTimeout> | null = null
const debounceEmit = (size: number) => {
  if (resizeDebounceTimer) {
    clearTimeout(resizeDebounceTimer)
  }
  resizeDebounceTimer = setTimeout(() => {
    emit('resize', size)
  }, 16)
}

// Load persisted size from localStorage
const loadPersistedSize = () => {
  if (props.storageKey && typeof window !== 'undefined') {
    const stored = localStorage.getItem(props.storageKey)
    if (stored) {
      const parsed = parseFloat(stored)
      if (!isNaN(parsed) && parsed >= props.minLeftSize && parsed <= props.maxLeftSize) {
        leftSize.value = parsed
      }
    }
  }
}

// Persist size to localStorage
const persistSize = (size: number) => {
  if (props.storageKey && typeof window !== 'undefined') {
    localStorage.setItem(props.storageKey, size.toString())
  }
}

// Computed styles
const leftPanelStyle = computed(() => {
  const size = isCollapsed.value ? props.collapsedSize : leftSize.value
  if (props.direction === 'horizontal') {
    return { width: `${size}px`, minWidth: `${size}px` }
  }
  return { height: `${size}px`, minHeight: `${size}px` }
})

const rightPanelStyle = computed(() => {
  if (props.direction === 'horizontal') {
    return { flex: '1', minWidth: '0' }
  }
  return { flex: '1', minHeight: '0' }
})

const dividerCursor = computed(() => {
  if (isCollapsed.value) return 'pointer'
  return props.direction === 'horizontal' ? 'col-resize' : 'row-resize'
})

// Toggle collapse
const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
  if (!isCollapsed.value) {
    // Restore previous size
    loadPersistedSize()
  }
}

// Drag handling
const getEventPosition = (e: MouseEvent | TouchEvent): number => {
  if ('touches' in e) {
    return props.direction === 'horizontal' ? e.touches[0].clientX : e.touches[0].clientY
  }
  return props.direction === 'horizontal' ? e.clientX : e.clientY
}

const getContainerOffset = (): number => {
  if (!containerRef.value) return 0
  const rect = containerRef.value.getBoundingClientRect()
  return props.direction === 'horizontal' ? rect.left : rect.top
}

const handleDragStart = (e: MouseEvent | TouchEvent) => {
  if (isCollapsed.value) return
  e.preventDefault()
  isDragging.value = true
  document.body.style.cursor = dividerCursor.value
  document.body.style.userSelect = 'none'
}

const handleDragMove = (e: MouseEvent | TouchEvent) => {
  if (!isDragging.value) return
  e.preventDefault()
  
  const position = getEventPosition(e)
  const offset = getContainerOffset()
  const containerSize = props.direction === 'horizontal'
    ? containerRef.value?.offsetWidth || 0
    : containerRef.value?.offsetHeight || 0
  
  let newSize = position - offset
  
  // Clamp to min/max
  newSize = Math.max(props.minLeftSize, Math.min(props.maxLeftSize, newSize))
  
  // Ensure right panel has at least some space
  const minRightSize = 100
  if (newSize > containerSize - minRightSize) {
    newSize = containerSize - minRightSize
  }
  
  leftSize.value = newSize
  debounceEmit(newSize)
}

const handleDragEnd = () => {
  if (!isDragging.value) return
  isDragging.value = false
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  persistSize(leftSize.value)
}

// Keyboard support for accessibility
const handleKeyDown = (e: KeyboardEvent) => {
  if (isCollapsed.value) return
  
  const step = e.shiftKey ? 50 : 10
  let newSize = leftSize.value
  
  if (props.direction === 'horizontal') {
    if (e.key === 'ArrowLeft') newSize -= step
    if (e.key === 'ArrowRight') newSize += step
  } else {
    if (e.key === 'ArrowUp') newSize -= step
    if (e.key === 'ArrowDown') newSize += step
  }
  
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight' || e.key === 'ArrowUp' || e.key === 'ArrowDown') {
    e.preventDefault()
    newSize = Math.max(props.minLeftSize, Math.min(props.maxLeftSize, newSize))
    leftSize.value = newSize
    debounceEmit(newSize)
    persistSize(newSize)
  }
  
  if (e.key === 'Home') {
    e.preventDefault()
    leftSize.value = props.minLeftSize
    debounceEmit(props.minLeftSize)
    persistSize(props.minLeftSize)
  }
  
  if (e.key === 'End') {
    e.preventDefault()
    leftSize.value = props.maxLeftSize
    debounceEmit(props.maxLeftSize)
    persistSize(props.maxLeftSize)
  }
}

// Lifecycle
onMounted(() => {
  loadPersistedSize()
  
  // Mouse events
  document.addEventListener('mousemove', handleDragMove)
  document.addEventListener('mouseup', handleDragEnd)
  
  // Touch events
  document.addEventListener('touchmove', handleDragMove, { passive: false })
  document.addEventListener('touchend', handleDragEnd)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', handleDragMove)
  document.removeEventListener('mouseup', handleDragEnd)
  document.removeEventListener('touchmove', handleDragMove)
  document.removeEventListener('touchend', handleDragEnd)
  
  if (resizeDebounceTimer) {
    clearTimeout(resizeDebounceTimer)
  }
})

// Expose for parent component
defineExpose({
  toggleCollapse,
  isCollapsed,
  leftSize,
})
</script>

<template>
  <div
    ref="containerRef"
    class="split-panel"
    :class="[`split-panel--${direction}`, { 'split-panel--collapsed': isCollapsed }]"
  >
    <!-- Left Panel -->
    <div
      class="split-panel__left"
      :style="leftPanelStyle"
    >
      <slot name="left" :collapsed="isCollapsed" :size="leftSize" />
    </div>
    
    <!-- Divider -->
    <div
      class="split-panel__divider"
      :class="{ 'split-panel__divider--dragging': isDragging }"
      :style="{ cursor: dividerCursor }"
      @mousedown="handleDragStart"
      @touchstart="handleDragStart"
      @keydown="handleKeyDown"
      tabindex="0"
      role="separator"
      :aria-valuenow="Math.round(leftSize)"
      :aria-valuemin="minLeftSize"
      :aria-valuemax="maxLeftSize"
      aria-label="Panel resizer"
    >
      <!-- Collapse Button -->
      <button
        class="split-panel__collapse-btn"
        :class="{ 'split-panel__collapse-btn--collapsed': isCollapsed }"
        @click.stop="toggleCollapse"
        :aria-label="isCollapsed ? 'Expand panel' : 'Collapse panel'"
        :aria-expanded="!isCollapsed"
      >
        <svg
          class="split-panel__collapse-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <polyline
            v-if="direction === 'horizontal'"
            :points="isCollapsed ? '9 18 15 12 9 6' : '15 18 9 12 15 6'"
          />
          <polyline
            v-else
            :points="isCollapsed ? '6 9 12 15 18 9' : '18 15 12 9 6 15'"
          />
        </svg>
      </button>
      
      <!-- Divider Line -->
      <div class="split-panel__divider-line" />
    </div>
    
    <!-- Right Panel -->
    <div
      class="split-panel__right"
      :style="rightPanelStyle"
    >
      <slot name="right" />
    </div>
  </div>
</template>

<style scoped>
.split-panel {
  display: flex;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background-color: var(--bg-system);
}

.split-panel--horizontal {
  flex-direction: row;
}

.split-panel--vertical {
  flex-direction: column;
}

.split-panel__left {
  overflow: hidden;
  transition: width 300ms ease, height 300ms ease;
  will-change: width, height;
}

.split-panel--collapsed .split-panel__left {
  overflow: visible;
}

.split-panel__right {
  overflow: auto;
  flex: 1;
}

.split-panel__divider {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  z-index: var(--z-sticky);
}

.split-panel--horizontal .split-panel__divider {
  width: 12px;
  cursor: col-resize;
  flex-direction: column;
}

.split-panel--vertical .split-panel__divider {
  height: 12px;
  cursor: row-resize;
  flex-direction: row;
}

.split-panel__divider:hover .split-panel__divider-line,
.split-panel__divider--dragging .split-panel__divider-line {
  background-color: var(--brand-navy-active);
}

.split-panel__divider:focus {
  outline: none;
}

.split-panel__divider:focus-visible .split-panel__divider-line {
  background-color: var(--brand-navy-active);
  box-shadow: 0 0 0 2px rgba(11, 60, 195, 0.3);
}

.split-panel__divider-line {
  position: absolute;
  background-color: var(--border-line);
  transition: background-color 0.2s;
}

.split-panel--horizontal .split-panel__divider-line {
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  transform: translateX(-50%);
}

.split-panel--vertical .split-panel__divider-line {
  top: 50%;
  left: 0;
  right: 0;
  height: 1px;
  transform: translateY(-50%);
}

.split-panel__collapse-btn {
  position: absolute;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 44px;
  padding: 0;
  border: 1px solid var(--border-line);
  border-radius: 4px;
  background-color: var(--bg-card);
  color: var(--text-muted);
  cursor: pointer;
  z-index: 11;
  transition: all 0.2s;
}

.split-panel__collapse-btn:hover {
  background-color: var(--bg-system);
  color: var(--text-regular);
  border-color: var(--brand-navy-active);
}

.split-panel__collapse-btn:active {
  background-color: #e8eaef;
}

.split-panel--horizontal .split-panel__collapse-btn {
  right: -4px;
  top: 50%;
  transform: translateY(-50%);
}

.split-panel--vertical .split-panel__collapse-btn {
  bottom: -4px;
  left: 50%;
  transform: translateX(-50%) rotate(90deg);
}

.split-panel__collapse-icon {
  width: 12px;
  height: 12px;
  transition: transform 0.3s ease;
}

.split-panel__collapse-btn--collapsed .split-panel__collapse-icon {
  transform: rotate(180deg);
}

/* Touch-friendly adjustments */
@media (pointer: coarse) {
  .split-panel--horizontal .split-panel__divider {
    width: 16px;
  }
  
  .split-panel--vertical .split-panel__divider {
    height: 16px;
  }
  
  .split-panel__collapse-btn {
    width: 24px;
    height: 48px;
  }
  
  .split-panel__collapse-icon {
    width: 14px;
    height: 14px;
  }
}

/* Mobile: Stack panels vertically */
@media (max-width: 768px) {
  .split-panel--horizontal {
    flex-direction: column;
  }
  
  .split-panel--horizontal .split-panel__left {
    width: 100% !important;
    height: auto;
    min-height: 200px;
    max-height: 40vh;
  }
  
  .split-panel--horizontal .split-panel__divider {
    width: 100%;
    height: 12px;
    cursor: row-resize;
  }
  
  .split-panel--horizontal .split-panel__divider-line {
    left: 0;
    right: 0;
    top: 50%;
    bottom: auto;
    width: auto;
    height: 1px;
    transform: translateY(-50%);
  }
  
  .split-panel--horizontal .split-panel__collapse-btn {
    right: auto;
    top: auto;
    bottom: -4px;
    left: 50%;
    transform: translateX(-50%) rotate(90deg);
  }
}
</style>
