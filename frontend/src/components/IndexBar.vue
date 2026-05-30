<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { onMounted, onUnmounted } from 'vue'
import { useIndicesStore } from '@/stores/indices'
import DataConfidenceBadge from '@/components/DataConfidenceBadge.vue'

const indicesStore = useIndicesStore()

// Use store's reactive state
const { indices, loading, meta } = storeToRefs(indicesStore)

// Format helpers with null safety
const formatPrice = (price: number | undefined | null): string => {
  if (price === undefined || price === null) return '--'
  return price.toFixed(2)
}

const formatChange = (change: number | undefined | null): string => {
  if (change === undefined || change === null) return '--'
  const sign = change >= 0 ? '+' : ''
  return `${sign}${change.toFixed(2)}`
}

const formatChangePct = (pct: number | undefined | null): string => {
  if (pct === undefined || pct === null) return '--%'
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

// Start auto-refresh on mount (singleton - only starts once globally)
// Note: Using 30s interval to match Dashboard.vue, avoiding race condition
onMounted(() => {
  indicesStore.startAutoRefresh(30000)
})

// Stop on unmount
onUnmounted(() => {
  indicesStore.stopAutoRefresh()
})
</script>

<template>
  <div class="index-bar">
    <div
      v-if="loading"
      class="loading-placeholder"
    >
      加载中...
    </div>
    
    <div
      v-else
      class="index-list"
    >
      <div
        v-for="(quote, code) in indices"
        :key="code"
        class="index-item"
      >
        <span class="index-name">{{ quote?.name || code }}</span>
        <span
          class="index-price"
          :class="(quote?.change ?? 0) >= 0 ? 'text-up' : 'text-down'"
        >
          {{ formatPrice(quote?.price) }}
        </span>
        <span
          class="index-change"
          :class="(quote?.change ?? 0) >= 0 ? 'text-up' : 'text-down'"
        >
          {{ formatChange(quote?.change) }}
          {{ formatChangePct(quote?.change_pct) }}
        </span>
      </div>
      
      <!-- Data Confidence Badge -->
      <DataConfidenceBadge 
        v-if="meta?.is_fallback" 
        source="simulated" 
        :timestamp="meta?.timestamp"
      />
      <DataConfidenceBadge 
        v-else-if="Object.keys(indices).length > 0" 
        source="real" 
        :timestamp="meta?.timestamp"
      />
    </div>
  </div>
</template>

<style scoped>
.index-bar {
  height: 32px;
  background-color: rgba(0, 0, 0, 0.2);
  padding: 0 24px;
  display: flex;
  align-items: center;
  overflow-x: auto;
}

.loading-placeholder {
  color: rgba(255, 255, 255, 0.6);
  font-size: 12px;
}

.index-list {
  display: flex;
  gap: 24px;
}

.index-item {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.index-name {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
}

.index-price {
  font-size: 13px;
  font-weight: 600;
}

.index-change {
  font-size: 12px;
}
</style>
