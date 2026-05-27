// frontend/src/composables/useBreakpoint.ts
import { ref, onMounted, onUnmounted, computed } from 'vue'

// Breakpoints matching CSS variables in main.css
// Extended range: 320px (iPhone SE) to 3840px (4K displays)
const BREAKPOINTS = {
  xs: 320,      // iPhone SE, small Android
  mobile: 480,  // Standard mobile
  tablet: 768,  // iPad portrait
  desktop: 1024, // Small laptop
  wide: 1400,   // Standard desktop
  ultra: 1920,  // Full HD
  '2k': 2560,   // 2K monitors
  '4k': 3840,   // 4K displays
} as const

export function useBreakpoint() {
  const width = ref(typeof window !== 'undefined' ? window.innerWidth : 1024)

  // Touch device detection
  const isTouchDevice = computed(() => {
    if (typeof window === 'undefined') return false
    return navigator.maxTouchPoints > 0 || 'ontouchstart' in window
  })

  // Device pixel ratio for high-DPI detection (capped at 2 for performance)
  const devicePixelRatio = ref(1)
  if (typeof window !== 'undefined') {
    devicePixelRatio.value = Math.min(window.devicePixelRatio || 1, 2)
  }

  // Screen orientation
  const orientation = computed(() => {
    if (typeof window === 'undefined') return 'landscape'
    return width.value > window.innerHeight ? 'landscape' : 'portrait'
  })

  const updateWidth = () => {
    if (typeof window !== 'undefined') {
      width.value = window.innerWidth
      devicePixelRatio.value = Math.min(window.devicePixelRatio || 1, 2)
    }
  }

  onMounted(() => {
    if (typeof window !== 'undefined') {
      window.addEventListener('resize', updateWidth)
    }
  })

  onUnmounted(() => {
    if (typeof window !== 'undefined') {
      window.removeEventListener('resize', updateWidth)
    }
  })

  return {
    width,
    BREAKPOINTS,
    isTouchDevice,
    devicePixelRatio,
    orientation,
    // Standard breakpoint checks
    isXs: computed(() => width.value < BREAKPOINTS.mobile),
    isMobile: computed(() => width.value < BREAKPOINTS.tablet),
    isTablet: computed(() => width.value >= BREAKPOINTS.tablet && width.value < BREAKPOINTS.desktop),
    isDesktop: computed(() => width.value >= BREAKPOINTS.desktop),
    isWide: computed(() => width.value >= BREAKPOINTS.wide),
    // High-resolution breakpoint checks
    isUltra: computed(() => width.value >= BREAKPOINTS.ultra),
    is2k: computed(() => width.value >= BREAKPOINTS['2k']),
    is4k: computed(() => width.value >= BREAKPOINTS['4k']),
    currentBreakpoint: computed(() => {
      if (width.value < BREAKPOINTS.xs) return 'xs'
      if (width.value < BREAKPOINTS.mobile) return 'xs'
      if (width.value < BREAKPOINTS.tablet) return 'mobile'
      if (width.value < BREAKPOINTS.desktop) return 'tablet'
      if (width.value < BREAKPOINTS.wide) return 'desktop'
      if (width.value < BREAKPOINTS.ultra) return 'wide'
      if (width.value < BREAKPOINTS['2k']) return 'ultra'
      if (width.value < BREAKPOINTS['4k']) return '2k'
      return '4k'
    }),
  }
}
