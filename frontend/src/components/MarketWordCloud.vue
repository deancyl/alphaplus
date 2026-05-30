<script setup lang="ts">
import { computed } from 'vue'

/**
 * MarketWordCloud Component
 * CSS Flexbox-based word cloud for market sentiment visualization
 * 
 * Features:
 * - Zero npm dependencies (pure CSS Flexbox)
 * - Font size scaled by weight (min 12px, max 32px)
 * - Color based on change value (green/red/gray)
 * - Hover effects with scale transform and shadow
 * - Loading state with skeleton
 * - Empty state with message
 * - Click handler for keyword selection
 * - WCAG 44px minimum touch target
 * - Responsive mobile-friendly design
 */

// Keyword data structure
export interface KeywordItem {
  name: string
  weight: number // 0-1 normalized weight for font sizing
  change?: number // Performance metric: positive = up, negative = down, undefined = neutral
}

interface Props {
  keywords?: KeywordItem[]
  loading?: boolean
  error?: string
  emptyMessage?: string
}

const props = withDefaults(defineProps<Props>(), {
  keywords: () => [],
  loading: false,
  error: undefined,
  emptyMessage: '暂无关键词数据',
})

// Emit keyword selection event
const emit = defineEmits<{
  (e: 'keyword-click', keyword: KeywordItem): void
}>()

// Font size calculation (12px - 32px range)
const MIN_FONT_SIZE = 12
const MAX_FONT_SIZE = 32

const calculateFontSize = (weight: number): number => {
  const clampedWeight = Math.max(0, Math.min(1, weight))
  return MIN_FONT_SIZE + (MAX_FONT_SIZE - MIN_FONT_SIZE) * clampedWeight
}

// Color determination based on change value
const getKeywordColor = (change?: number): string => {
  if (change === undefined || change === null || change === 0) {
    return 'var(--text-muted)' // Gray for neutral
  }
  return change > 0 ? 'var(--market-up)' : 'var(--market-down)' // Red for up, Green for down (A-share convention)
}

// Text shadow for depth effect
const getTextShadow = (change?: number): string => {
  if (change === undefined || change === null) return 'none'
  const color = change > 0 ? 'rgba(230, 57, 53, 0.3)' : 'rgba(46, 125, 50, 0.3)'
  return `0 2px 8px ${color}`
}

// Handle keyword click
const handleKeywordClick = (keyword: KeywordItem) => {
  emit('keyword-click', keyword)
}

// Sort keywords by weight (descending) for better visual hierarchy
const sortedKeywords = computed(() => {
  return [...props.keywords].sort((a, b) => b.weight - a.weight)
})

// Check if we have data to display
const hasData = computed(() => props.keywords.length > 0)
</script>

<template>
  <div class="market-word-cloud">
    <!-- Loading State -->
    <div v-if="loading" class="word-cloud-skeleton">
      <div class="skeleton-item" v-for="i in 12" :key="i" :style="{
        width: `${Math.random() * 80 + 40}px`,
        height: `${Math.random() * 20 + 12}px`,
        opacity: 0.3 + Math.random() * 0.4
      }" />
    </div>
    
    <!-- Error State -->
    <div v-else-if="error" class="word-cloud-error">
      <svg class="error-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
        <path d="M12 8v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        <circle cx="12" cy="16" r="1" fill="currentColor"/>
      </svg>
      <p class="error-message">{{ error }}</p>
    </div>
    
    <!-- Empty State -->
    <div v-else-if="!hasData" class="word-cloud-empty">
      <svg class="empty-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="4" y="4" width="16" height="16" rx="2" stroke="currentColor" stroke-width="2"/>
        <path d="M9 9h6M9 12h6M9 15h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
      <p class="empty-message">{{ emptyMessage }}</p>
    </div>
    
    <!-- Word Cloud Container -->
    <div v-else class="word-cloud-container">
      <span
        v-for="(keyword, index) in sortedKeywords"
        :key="keyword.name"
        class="keyword-item touch-target"
        :style="{
          fontSize: `${calculateFontSize(keyword.weight)}px`,
          color: getKeywordColor(keyword.change),
          textShadow: getTextShadow(keyword.change),
          animationDelay: `${index * 50}ms`
        }"
        @click="handleKeywordClick(keyword)"
        :title="`${keyword.name}${keyword.change !== undefined ? (keyword.change > 0 ? ' +' : ' ') + keyword.change.toFixed(2) + '%' : ''}`"
        role="button"
        tabindex="0"
        @keydown.enter="handleKeywordClick(keyword)"
        @keydown.space.prevent="handleKeywordClick(keyword)"
      >
        {{ keyword.name }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.market-word-cloud {
  width: 100%;
  min-height: 200px;
  background-color: var(--bg-card);
  border-radius: 4px;
  padding: var(--spacing-md);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

/* Word Cloud Container - CSS Flexbox Layout */
.word-cloud-container {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm) var(--spacing-md);
  padding: var(--spacing-md);
  min-height: 180px;
}

/* Keyword Item */
.keyword-item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xs) var(--spacing-sm);
  cursor: pointer;
  font-weight: 500;
  letter-spacing: 0.02em;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
  border-radius: 4px;
  white-space: nowrap;
  animation: fadeInUp 0.4s ease-out backwards;
}

.keyword-item:hover {
  transform: scale(1.1) translateY(-2px);
  background-color: rgba(0, 0, 0, 0.04);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: var(--z-base);
}

.keyword-item:active {
  transform: scale(1.05);
}

.keyword-item:focus {
  outline: 2px solid var(--brand-navy-dark);
  outline-offset: 2px;
}

/* Touch Target Enhancement (WCAG 2.5.5: 44px minimum) */
.touch-target {
  min-height: 44px;
  min-width: 44px;
}

/* Fade-in Animation */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Loading Skeleton State */
.word-cloud-skeleton {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm) var(--spacing-md);
  padding: var(--spacing-md);
  min-height: 180px;
}

.skeleton-item {
  background: linear-gradient(
    90deg,
    var(--border-line) 25%,
    rgba(0, 0, 0, 0.06) 50%,
    var(--border-line) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}

@keyframes shimmer {
  0% {
    background-position: -200% 0;
  }
  100% {
    background-position: 200% 0;
  }
}

/* Error State */
.word-cloud-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  min-height: 180px;
  color: var(--text-muted);
}

.error-icon {
  width: 48px;
  height: 48px;
  margin-bottom: var(--spacing-md);
  color: var(--market-up);
}

.error-message {
  font-size: 14px;
  text-align: center;
}

/* Empty State */
.word-cloud-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  min-height: 180px;
  color: var(--text-muted);
}

.empty-icon {
  width: 48px;
  height: 48px;
  margin-bottom: var(--spacing-md);
  opacity: 0.6;
}

.empty-message {
  font-size: 14px;
  text-align: center;
}

/* Responsive Design */
@media (max-width: 768px) {
  .market-word-cloud {
    padding: var(--spacing-sm);
  }
  
  .word-cloud-container {
    gap: var(--spacing-xs) var(--spacing-sm);
    padding: var(--spacing-sm);
  }
  
  .keyword-item {
    font-size: calc(var(--font-size) * 0.9); /* Slightly smaller on mobile */
    padding: var(--spacing-xs);
  }
}

@media (max-width: 480px) {
  .word-cloud-container {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-xs);
  }
  
  .keyword-item {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
