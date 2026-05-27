<script setup lang="ts">
import { computed } from 'vue'

interface StyleData {
  large_cap_value: number  // 0-100 weight
  large_cap_blend: number
  large_cap_growth: number
  mid_cap_value: number
  mid_cap_blend: number
  mid_cap_growth: number
  small_cap_value: number
  small_cap_blend: number
  small_cap_growth: number
}

interface Props {
  data: StyleData
  title?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: '投资风格箱',
})

// Grid labels
const rows = ['大盘', '中盘', '小盘']
const cols = ['价值', '混合', '成长']

// Map data to grid positions
const gridData = computed(() => {
  const d = props.data
  return [
    [d.large_cap_value, d.large_cap_blend, d.large_cap_growth],
    [d.mid_cap_value, d.mid_cap_blend, d.mid_cap_growth],
    [d.small_cap_value, d.small_cap_blend, d.small_cap_growth],
  ]
})

// Color intensity based on weight - using CSS classes
const getIntensity = (weight: number) => {
  if (weight >= 60) return 'high-intensity'
  if (weight >= 30) return 'medium-intensity'
  if (weight >= 10) return 'low-intensity'
  return 'minimal-intensity'
}

// Find dominant style
const dominantStyle = computed(() => {
  let maxWeight = 0
  let maxRow = 0
  let maxCol = 0
  
  gridData.value.forEach((row, ri) => {
    row.forEach((weight, ci) => {
      if (weight > maxWeight) {
        maxWeight = weight
        maxRow = ri
        maxCol = ci
      }
    })
  })
  
  return {
    style: `${rows[maxRow]}${cols[maxCol]}`,
    weight: maxWeight,
    row: maxRow,
    col: maxCol,
  }
})
</script>

<template>
  <div class="style-box">
    <h4 v-if="title" class="style-box-title">{{ title }}</h4>
    
    <!-- Column headers -->
    <div class="style-box-grid">
      <div class="style-box-header"></div>
      <div 
        v-for="col in cols" 
        :key="col" 
        class="style-box-header"
      >
        {{ col }}
      </div>
      
      <!-- Grid cells -->
      <template v-for="(row, ri) in rows" :key="row">
        <div class="style-box-row-label">{{ row }}</div>
        <div
          v-for="(weight, ci) in gridData[ri]"
          :key="`${ri}-${ci}`"
          class="style-box-cell"
          :class="[
            getIntensity(weight),
            { 'is-dominant': ri === dominantStyle.row && ci === dominantStyle.col }
          ]"
        >
          <span class="font-medium">{{ weight ? weight.toFixed(0) + '%' : '-' }}</span>
        </div>
      </template>
    </div>
    
    <!-- Legend -->
    <div class="style-box-legend">
      <span class="legend-text">
        主导风格: {{ dominantStyle.style }} ({{ dominantStyle.weight.toFixed(0) }}%)
      </span>
    </div>
  </div>
</template>

<style scoped>
.style-box {
  background: var(--bg-card);
  border-radius: 8px;
  padding: var(--spacing-md);
  border: 1px solid var(--border-line);
}

.style-box-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-sm);
}

.style-box-grid {
  display: grid;
  grid-template-columns: 60px repeat(3, 1fr);
  gap: 4px;
}

.style-box-header,
.style-box-row-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  padding: var(--spacing-xs);
  text-align: center;
}

.style-box-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-sm);
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  min-height: 44px;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

/* Intensity levels - using design system colors */
.style-box-cell.high-intensity {
  background: var(--brand-navy-dark);
  color: white;
}

.style-box-cell.medium-intensity {
  background: var(--brand-navy-active);
  color: white;
}

.style-box-cell.low-intensity {
  background: rgba(0, 51, 153, 0.15);
  color: var(--text-primary);
}

.style-box-cell.minimal-intensity {
  background: rgba(153, 153, 153, 0.08);
  color: var(--text-muted);
}

/* Dominant style highlight */
.style-box-cell.is-dominant {
  box-shadow: 0 0 0 2px var(--brand-navy-dark);
  position: relative;
}

.style-box-cell.is-dominant::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 6px;
  background: rgba(255, 215, 0, 0.15);
  animation: pulse-highlight 2s ease-in-out infinite;
}

@keyframes pulse-highlight {
  0%, 100% { opacity: 0.15; }
  50% { opacity: 0.25; }
}

.style-box-cell:hover {
  transform: scale(1.03);
}

.style-box-legend {
  margin-top: var(--spacing-sm);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--border-line);
}

.legend-text {
  font-size: 12px;
  color: var(--text-muted);
}

/* Responsive adjustments */
@media (max-width: 480px) {
  .style-box-grid {
    grid-template-columns: 50px repeat(3, 1fr);
    gap: 2px;
  }
  
  .style-box-cell {
    min-height: 40px;
    font-size: 12px;
  }
  
  .style-box-header,
  .style-box-row-label {
    font-size: 11px;
  }
}
</style>
