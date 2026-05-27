// frontend/src/composables/useBreakpoint.ts
import { ref, onMounted, onUnmounted, computed } from 'vue'

// Breakpoints matching CSS variables in main.css
const BREAKPOINTS = {
  mobile: 480,
  tablet: 768,
  desktop: 1024,
  wide: 1400,
} as const

export function useBreakpoint() {
  const width = ref(window.innerWidth)

  const updateWidth = () => {
    width.value = window.innerWidth
  }

  onMounted(() => {
    window.addEventListener('resize', updateWidth)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', updateWidth)
  })

  return {
    width,
    isMobile: computed(() => width.value < BREAKPOINTS.tablet),
    isTablet: computed(() => width.value >= BREAKPOINTS.tablet && width.value < BREAKPOINTS.desktop),
    isDesktop: computed(() => width.value >= BREAKPOINTS.desktop),
    isWide: computed(() => width.value >= BREAKPOINTS.wide),
    currentBreakpoint: computed(() => {
      if (width.value < BREAKPOINTS.mobile) return 'xs'
      if (width.value < BREAKPOINTS.tablet) return 'mobile'
      if (width.value < BREAKPOINTS.desktop) return 'tablet'
      if (width.value < BREAKPOINTS.wide) return 'desktop'
      return 'wide'
    }),
  }
}
