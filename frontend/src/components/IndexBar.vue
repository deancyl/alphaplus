<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { onMounted, onUnmounted } from 'vue'
import { useIndicesStore } from '@/stores/indices'

const indicesStore = useIndicesStore()

// Use store's reactive state
const { indices, loading } = storeToRefs(indicesStore)

// Format helpers
const formatPrice = (price: number): string => {
  return price.toFixed(2)
}

const formatChange = (change: number): string => {
  const sign = change >= 0 ? '+' : ''
  return `${sign}${change.toFixed(2)}`
}

const formatChangePct = (pct: number): string => {
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

// Start auto-refresh on mount (singleton - only starts once globally)
onMounted(() => {
  indicesStore.startAutoRefresh(5000)
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
        <span class="index-name">{{ quote.name }}</span>
        <span
          class="index-price"
          :class="quote.change >= 0 ? 'text-up' : 'text-down'"
        >
          {{ formatPrice(quote.price) }}
        </span>
        <span
          class="index-change"
          :class="quote.change >= 0 ? 'text-up' : 'text-down'"
        >
          {{ formatChange(quote.change) }}
          {{ formatChangePct(quote.change_pct) }}
        </span>
      </div>
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
