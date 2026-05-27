<script setup lang="ts">
/**
 * SkeletonLoader Component
 * 
 * Provides loading placeholder UI with shimmer animation.
 * Integrates with design system CSS variables.
 * 
 * @example
 * <SkeletonLoader variant="text" />
 * <SkeletonLoader variant="card" />
 * <SkeletonLoader variant="table" :rows="5" :columns="6" />
 */

interface Props {
  /**
   * Skeleton variant type
   * - text: Single text line
   * - image: Image placeholder (16:9)
   * - card: Card with header + content
   * - table: Table with rows
   * - gauge: Semi-circular gauge
   * - heatmap: Grid heatmap
   * - valuation-card: PE valuation card
   * - widget: Dashboard widget
   * - index-item: Index quote item
   */
  variant?: 'text' | 'image' | 'card' | 'table' | 'gauge' | 'heatmap' | 'valuation-card' | 'widget' | 'index-item'
  
  /** Number of rows for table variant */
  rows?: number
  
  /** Number of columns for table variant */
  columns?: number
  
  /** Width override (CSS value) */
  width?: string
  
  /** Height override (CSS value) */
  height?: string
  
  /** Text size variant for text skeleton */
  textSize?: 'sm' | 'md' | 'lg' | 'title'
  
  /** Image aspect ratio */
  aspectRatio?: '16:9' | '4:3' | '1:1' | 'square'
  
  /** Additional CSS classes */
  class?: string
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'text',
  rows: 5,
  columns: 6,
  width: undefined,
  height: undefined,
  textSize: 'md',
  aspectRatio: '16:9',
  class: '',
})

// Generate array for v-for
const getRowsArray = () => Array.from({ length: props.rows }, (_, i) => i)
const getColumnsArray = () => Array.from({ length: props.columns }, (_, i) => i)

// Dynamic style binding
const styleBindings = {
  width: props.width,
  height: props.height,
}
</script>

<template>
  <div :class="['skeleton-loader', props.class]" :style="styleBindings">
    <!-- Text variant -->
    <div
      v-if="variant === 'text'"
      :class="[
        'skeleton',
        'skeleton-text',
        textSize === 'sm' ? 'skeleton-text--sm' : '',
        textSize === 'lg' ? 'skeleton-text--lg' : '',
        textSize === 'title' ? 'skeleton-text--title' : '',
      ]"
    />
    
    <!-- Image variant -->
    <div
      v-else-if="variant === 'image'"
      :class="[
        'skeleton',
        'skeleton-image',
        aspectRatio === '1:1' || aspectRatio === 'square' ? 'skeleton-image--square' : '',
      ]"
    />
    
    <!-- Card variant -->
    <div v-else-if="variant === 'card'" class="skeleton-card">
      <div class="skeleton-card__header">
        <div class="skeleton skeleton-card__title" />
        <div class="skeleton skeleton-card__badge" />
      </div>
      <div class="skeleton-card__content">
        <div class="skeleton skeleton-text" />
        <div class="skeleton skeleton-text" />
        <div class="skeleton skeleton-text skeleton-text--sm" />
      </div>
    </div>
    
    <!-- Table variant -->
    <div v-else-if="variant === 'table'" class="skeleton-table">
      <!-- Header -->
      <div class="skeleton-table__header">
        <div
          v-for="col in getColumnsArray()"
          :key="`header-${col}`"
          :class="['skeleton', 'skeleton-table__header-cell', col < 2 ? 'skeleton-table__header-cell--fixed' : '']"
        />
      </div>
      <!-- Rows -->
      <div
        v-for="row in getRowsArray()"
        :key="`row-${row}`"
        class="skeleton-table__row"
      >
        <div
          v-for="col in getColumnsArray()"
          :key="`cell-${row}-${col}`"
          :class="[
            'skeleton',
            'skeleton-table__cell',
            col < 2 ? 'skeleton-table__cell--fixed' : '',
            col >= columns - 2 ? 'skeleton-table__cell--narrow' : '',
          ]"
        />
      </div>
    </div>
    
    <!-- Gauge variant -->
    <div v-else-if="variant === 'gauge'" class="skeleton-gauge">
      <div class="skeleton-gauge__arc">
        <div class="skeleton skeleton-gauge__needle" />
      </div>
    </div>
    
    <!-- Heatmap variant -->
    <div v-else-if="variant === 'heatmap'" class="skeleton-heatmap">
      <div
        v-for="i in 25"
        :key="`heatmap-${i}`"
        class="skeleton skeleton-heatmap__cell"
      />
    </div>
    
    <!-- Valuation Card variant -->
    <div v-else-if="variant === 'valuation-card'" class="skeleton-valuation-card">
      <div class="skeleton-valuation-card__header">
        <div class="skeleton skeleton-valuation-card__name" />
        <div class="skeleton skeleton-card__badge" />
      </div>
      <div class="skeleton skeleton-valuation-card__pe" />
      <div class="skeleton skeleton-valuation-card__bar" />
      <div class="skeleton skeleton-valuation-card__percentile" />
      <div class="skeleton skeleton-valuation-card__zone" />
      <div class="skeleton-valuation-card__metrics">
        <div class="skeleton-valuation-card__metric">
          <div class="skeleton skeleton-valuation-card__metric-label" />
          <div class="skeleton skeleton-valuation-card__metric-value" />
        </div>
        <div class="skeleton-valuation-card__metric">
          <div class="skeleton skeleton-valuation-card__metric-label" />
          <div class="skeleton skeleton-valuation-card__metric-value" />
        </div>
      </div>
    </div>
    
    <!-- Widget variant -->
    <div v-else-if="variant === 'widget'" class="skeleton-widget">
      <div class="skeleton-widget__header">
        <div>
          <div class="skeleton skeleton-widget__title" />
          <div class="skeleton skeleton-widget__subtitle" style="margin-top: 4px;" />
        </div>
        <div class="skeleton skeleton-card__badge" />
      </div>
      <div class="skeleton skeleton-widget__chart" />
    </div>
    
    <!-- Index Item variant -->
    <div v-else-if="variant === 'index-item'" class="skeleton-index-item">
      <div class="skeleton skeleton-index-item__name" />
      <div class="skeleton skeleton-index-item__price" />
      <div class="skeleton skeleton-index-item__change" />
    </div>
  </div>
</template>

<style scoped>
@import '@/assets/styles/skeleton.css';

.skeleton-loader {
  display: contents;
}

/* Ensure skeleton elements have proper display */
.skeleton-loader > * {
  display: block;
}
</style>
