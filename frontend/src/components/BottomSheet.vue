<!-- frontend/src/components/BottomSheet.vue -->
<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useBreakpoint } from '@/composables/useBreakpoint'

interface Props {
  isOpen: boolean
  title?: string
  snapPoints?: ('closed' | 'half' | 'full')[]
  showBackdrop?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isOpen: false,
  title: '',
  snapPoints: () => ['closed', 'half', 'full'],
  showBackdrop: true,
})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'update:isOpen', value: boolean): void
  (e: 'snapPointChange', point: string): void
}>()

const { isMobile } = useBreakpoint()

// Sheet state
const sheetHeight = ref(0) // 0 = closed, 50 = half, 100 = full
const isDragging = ref(false)
const dragStartY = ref(0)
const dragStartHeight = ref(0)

// Computed sheet position
const sheetStyle = computed(() => ({
  height: `${sheetHeight.value}%`,
  transition: isDragging.value ? 'none' : 'height 300ms cubic-bezier(0.4, 0, 0.2, 1)',
}))

// Snap point management
const SNAP_HEIGHTS = {
  closed: 0,
  half: 50,
  full: 100,
}

const currentSnapPoint = computed(() => {
  if (sheetHeight.value <= 10) return 'closed'
  if (sheetHeight.value <= 60) return 'half'
  return 'full'
})

// Watch isOpen prop to sync sheet state
watch(
  () => props.isOpen,
  (newVal) => {
    if (newVal && sheetHeight.value === 0) {
      openSheet('half')
    } else if (!newVal && sheetHeight.value > 0) {
      closeSheet()
    }
  }
)

// Open sheet at default snap point
const openSheet = (snapPoint: 'half' | 'full' = 'half') => {
  sheetHeight.value = SNAP_HEIGHTS[snapPoint]
  emit('update:isOpen', true)
  emit('snapPointChange', snapPoint)
}

// Close sheet
const closeSheet = () => {
  sheetHeight.value = 0
  emit('update:isOpen', false)
  emit('close')
  emit('snapPointChange', 'closed')
}

// Touch handlers
const handleTouchStart = (e: TouchEvent) => {
  isDragging.value = true
  dragStartY.value = e.touches[0].clientY
  dragStartHeight.value = sheetHeight.value
}

const handleTouchMove = (e: TouchEvent) => {
  if (!isDragging.value) return

  const deltaY = e.touches[0].clientY - dragStartY.value
  const windowHeight = window.innerHeight
  const heightDelta = (deltaY / windowHeight) * 100

  sheetHeight.value = Math.max(0, Math.min(100, dragStartHeight.value - heightDelta))
}

const handleTouchEnd = () => {
  isDragging.value = false

  // Snap to closest point
  const closestPoint = props.snapPoints.reduce((closest, point) => {
    const distance = Math.abs(sheetHeight.value - SNAP_HEIGHTS[point])
    const closestDistance = Math.abs(sheetHeight.value - SNAP_HEIGHTS[closest])
    return distance < closestDistance ? point : closest
  }, props.snapPoints[0])

  if (closestPoint === 'closed') {
    closeSheet()
  } else {
    sheetHeight.value = SNAP_HEIGHTS[closestPoint]
    emit('snapPointChange', closestPoint)
  }
}

// Backdrop click
const handleBackdropClick = () => {
  if (props.showBackdrop) {
    closeSheet()
  }
}

// Keyboard handler
const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && props.isOpen) {
    closeSheet()
  }
}

// Expose methods
defineExpose({
  openSheet,
  closeSheet,
  currentSnapPoint,
})

// Lifecycle
onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<template>
  <div class="bottom-sheet-container" :class="{ 'is-open': isOpen }">
    <!-- Backdrop -->
    <div
      v-if="showBackdrop && isOpen"
      class="bottom-sheet-backdrop"
      @click="handleBackdropClick"
    />

    <!-- Sheet -->
    <div
      class="bottom-sheet"
      :style="sheetStyle"
      @touchstart="handleTouchStart"
      @touchmove="handleTouchMove"
      @touchend="handleTouchEnd"
    >
      <!-- Drag handle -->
      <div class="bottom-sheet-handle" />

      <!-- Header -->
      <div v-if="title" class="bottom-sheet-header">
        <h3 class="bottom-sheet-title">{{ title }}</h3>
        <button
          class="bottom-sheet-close"
          @click="closeSheet"
          aria-label="关闭"
        >
          ✕
        </button>
      </div>

      <!-- Content -->
      <div class="bottom-sheet-content">
        <slot />
      </div>
    </div>
  </div>
</template>

<style scoped>
.bottom-sheet-container {
  position: fixed;
  inset: 0;
  z-index: 100;
  pointer-events: none;
}

.bottom-sheet-container.is-open {
  pointer-events: auto;
}

.bottom-sheet-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  animation: fade-in 200ms ease-out;
}

@keyframes fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.bottom-sheet {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--bg-card);
  border-radius: var(--spacing-md) var(--spacing-md) 0 0;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
  overflow: hidden;
  touch-action: none;
  display: flex;
  flex-direction: column;
}

.bottom-sheet-handle {
  width: 36px;
  height: 4px;
  background: var(--border-line);
  border-radius: 2px;
  margin: var(--spacing-sm) auto;
  cursor: grab;
  flex-shrink: 0;
}

.bottom-sheet-handle:active {
  cursor: grabbing;
}

.bottom-sheet-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--border-line);
  flex-shrink: 0;
}

.bottom-sheet-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.bottom-sheet-close {
  width: var(--touch-target-min);
  height: var(--touch-target-min);
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  font-size: 20px;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.2s, color 0.2s;
}

.bottom-sheet-close:hover {
  background: var(--bg-system);
  color: var(--text-primary);
}

.bottom-sheet-close:active {
  background: var(--border-line);
}

.bottom-sheet-content {
  padding: var(--spacing-md);
  overflow-y: auto;
  flex: 1;
  -webkit-overflow-scrolling: touch;
}

/* Desktop: Limit max height for better UX */
@media (min-width: 768px) {
  .bottom-sheet {
    max-width: 480px;
    left: 50%;
    transform: translateX(-50%);
    border-radius: var(--spacing-md);
    bottom: var(--spacing-lg);
    max-height: 80vh;
  }

  .bottom-sheet-backdrop {
    background: rgba(0, 0, 0, 0.3);
  }
}

/* Mobile: Full width */
@media (max-width: 768px) {
  .bottom-sheet-content {
    max-height: calc(100vh - 120px);
  }
}
</style>
