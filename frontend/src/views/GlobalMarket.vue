<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Clock, Refresh } from '@element-plus/icons-vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import type { EChartsOption } from 'echarts'
import { getGlobalMarket } from '@/api/market'
import { formatPercent } from '@/utils/formatters'

// Types
interface IndexData {
  name: string
  code: string
  price: number
  change: number
  change_pct: number
  region: string
}

interface CurrencyData {
  pair: string
  rate: number
  change: number
  change_pct: number
}

interface CommodityData {
  name: string
  code: string
  price: number
  change: number
  change_pct: number
  unit: string
}

// Loading states - per-section for progressive loading
const indicesLoading = ref(true)
const currenciesLoading = ref(true)
const commoditiesLoading = ref(true)
// State
const lastUpdate = ref<string>('')
const indices = ref<IndexData[]>([])
const currencies = ref<CurrencyData[]>([])
const commodities = ref<CommodityData[]>([])

// Chart option for indices comparison
const indicesChartOption = ref<EChartsOption>({
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (params: unknown) => {
      const items = params as Array<{ axisValue: string; marker: string; value: number }>
      if (!items || items.length === 0) return ''
      let html = `<div style="font-weight:600;margin-bottom:8px;">${items[0].axisValue}</div>`
      items.forEach(item => {
        const color = item.value >= 0 ? '#E63935' : '#2E7D32'
        const sign = item.value >= 0 ? '+' : ''
        html += `<div style="display:flex;justify-content:space-between;gap:20px;">
          <span>${item.marker}</span>
          <span style="color:${color};font-weight:600;">${sign}${item.value.toFixed(2)}%</span>
        </div>`
      })
      return html
    },
  },
  grid: {
    top: 40,
    left: 60,
    right: 20,
    bottom: 60,
  },
  xAxis: {
    type: 'category',
    data: [],
    axisLabel: {
      rotate: 30,
      fontSize: 12,
      color: '#4A4A4A',
    },
    axisLine: { lineStyle: { color: '#E5E8ED' } },
    axisTick: { show: false },
  },
  yAxis: {
    type: 'value',
    name: '涨跌幅(%)',
    nameTextStyle: { color: '#999999', fontSize: 12 },
    axisLabel: {
      formatter: '{value}%',
      color: '#4A4A4A',
    },
    axisLine: { show: false },
    splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } },
  },
  series: [{
    type: 'bar',
    data: [],
    barWidth: '50%',
    itemStyle: {
      color: (params: any) => {
        return (params.value as number) >= 0 ? '#E63935' : '#2E7D32'
      },
      borderRadius: [4, 4, 0, 0],
    },
    label: {
      show: true,
      position: 'top',
      formatter: (params: any) => {
        const val = params.value as number
        const sign = val >= 0 ? '+' : ''
        return `${sign}${val.toFixed(2)}%`
      },
      fontSize: 11,
      color: '#4A4A4A',
    },
  }],
} as EChartsOption)

// Format number with sign
const formatChange = (val: number | null): string => {
  if (val === null || val === undefined) return '-'
  const sign = val >= 0 ? '+' : ''
  return `${sign}${val.toFixed(2)}`
}

// Get value class for styling
const getValueClass = (val: number | null): string => {
  if (val === null || val === undefined) return 'text-flat'
  if (val > 0) return 'text-up'
  if (val < 0) return 'text-down'
  return 'text-flat'
}

// Format price
const formatPrice = (val: number | null): string => {
  if (val === null || val === undefined) return '-'
  if (val >= 10000) {
    return (val / 1000).toFixed(2) + 'K'
  }
  return val.toFixed(2)
}

// Region mapping for indices
const regionMap: Record<string, string> = {
  'DJI': '美国',
  'IXIC': '美国',
  'SPX': '美国',
  'HSI': '香港',
  'N225': '日本',
  'FTSE': '英国',
  'DAX': '德国',
  'CAC': '法国',
}

// Fetch global market data - progressive loading for each section
const fetchGlobalMarketData = async () => {
  // Fetch indices independently
  indicesLoading.value = true
  try {
    const response = await getGlobalMarket()
    
    indices.value = response.indices.map(idx => ({
      code: idx.code,
      name: idx.name,
      price: idx.price,
      change: idx.price * idx.change_pct / 100,
      change_pct: idx.change_pct,
      region: regionMap[idx.code] || '其他',
    }))
    
    // Update chart
    updateIndicesChart()
  } catch {
    ElMessage.error('获取全球指数数据失败')
  } finally {
    indicesLoading.value = false
  }
  
  // Fetch currencies independently
  currenciesLoading.value = true
  try {
    const response = await getGlobalMarket()
    currencies.value = response.currencies.map(curr => ({
      pair: curr.name,
      rate: curr.price,
      change: curr.price * curr.change_pct / 100,
      change_pct: curr.change_pct,
    }))
  } catch {
    ElMessage.error('获取汇率数据失败')
  } finally {
    currenciesLoading.value = false
  }
  
  // Fetch commodities independently
  commoditiesLoading.value = true
  try {
    const response = await getGlobalMarket()
    commodities.value = response.commodities.map(comm => ({
      name: comm.name,
      code: comm.code,
      price: comm.price,
      change: comm.price * comm.change_pct / 100,
      change_pct: comm.change_pct,
      unit: '',
    }))
    
    // Set last update time
    lastUpdate.value = response.update_time || new Date().toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    ElMessage.error('获取大宗商品数据失败')
  } finally {
    commoditiesLoading.value = false
  }
}

// Update indices chart
const updateIndicesChart = () => {
  const chartData = indices.value.map(idx => ({
    name: idx.name,
    value: idx.change_pct,
  }))

  // @ts-expect-error - ECharts type inference issue with dynamic data assignment
  indicesChartOption.value.xAxis.data = chartData.map(d => d.name)
  // @ts-expect-error - ECharts type inference issue with series data assignment
  indicesChartOption.value.series[0].data = chartData.map(d => d.value)
}

// Auto refresh timer
let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchGlobalMarketData()
  
  // Auto refresh every 30 seconds
  refreshTimer = setInterval(() => {
    fetchGlobalMarketData()
  }, 30000)
})

// Cleanup on unmount
onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<template>
  <ErrorBoundary>
    <div class="global-market">
      <!-- Header -->
      <div class="page-header">
        <h1 class="page-title">全球市场总览</h1>
        <div class="header-info">
          <span class="update-time" v-if="lastUpdate">
            <el-icon><Clock /></el-icon>
            最后更新: {{ lastUpdate }}
          </span>
          <el-button 
            type="primary" 
            size="small" 
            :loading="indicesLoading || currenciesLoading || commoditiesLoading"
            @click="fetchGlobalMarketData"
          >
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </div>
      
      <!-- Major Indices Section -->
      <div class="section">
        <div class="section-header">
          <h2 class="section-title">全球主要指数</h2>
          <span class="section-subtitle">实时行情</span>
        </div>
        
        <ErrorBoundary>
          <!-- Skeleton when loading -->
          <template v-if="indicesLoading">
            <div class="indices-grid">
              <SkeletonLoader
                v-for="i in 8"
                :key="`index-skeleton-${i}`"
                variant="card"
                height="160px"
              />
            </div>
          </template>
          
          <!-- Indices Grid -->
          <template v-else>
            <div class="indices-grid">
              <el-card 
                v-for="idx in indices" 
                :key="idx.code"
                class="index-card"
                :class="getValueClass(idx.change_pct)"
                shadow="hover"
              >
                <div class="index-header">
                  <span class="index-name">{{ idx.name }}</span>
                  <span class="index-region">{{ idx.region }}</span>
                </div>
                <div class="index-price">{{ formatPrice(idx.price) }}</div>
                <div class="index-change" :class="getValueClass(idx.change_pct)">
                  <span class="change-value">{{ formatChange(idx.change) }}</span>
                  <span class="change-percent">{{ formatPercent(idx.change_pct) }}</span>
                </div>
              </el-card>
            </div>
            
            <!-- Indices Comparison Chart -->
            <el-card class="chart-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>指数涨跌幅对比</span>
                </div>
              </template>
              <EChartsWrapper
                :option="indicesChartOption"
                height="320px"
              />
            </el-card>
          </template>
        </ErrorBoundary>
      </div>
      
      <!-- Currency & Commodity Section -->
      <div class="section dual-section">
        <!-- Currency Exchange Rates -->
        <div class="sub-section">
          <div class="section-header">
            <h2 class="section-title">外汇汇率</h2>
          </div>
          
          <ErrorBoundary>
            <!-- Skeleton when loading -->
            <SkeletonLoader
              v-if="currenciesLoading"
              variant="table"
              :rows="5"
              :columns="3"
            />
            
            <!-- Actual content when loaded -->
            <el-card v-else shadow="never" class="data-card">
              <el-table :data="currencies" stripe size="small">
                <el-table-column prop="pair" label="货币对" width="100" />
                <el-table-column prop="rate" label="汇率" width="100">
                  <template #default="{ row }">
                    <span class="rate-value">{{ row.rate.toFixed(4) }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="change_pct" label="涨跌幅">
                  <template #default="{ row }">
                    <span :class="getValueClass(row.change_pct)" class="change-cell">
                      {{ formatPercent(row.change_pct) }}
                    </span>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </ErrorBoundary>
        </div>
        
        <!-- Commodity Prices -->
        <div class="sub-section">
          <div class="section-header">
            <h2 class="section-title">大宗商品</h2>
          </div>
          
          <ErrorBoundary>
            <!-- Skeleton when loading -->
            <SkeletonLoader
              v-if="commoditiesLoading"
              variant="table"
              :rows="5"
              :columns="3"
            />
            
            <!-- Actual content when loaded -->
            <el-card v-else shadow="never" class="data-card">
              <el-table :data="commodities" stripe size="small">
                <el-table-column prop="name" label="品种" width="90" />
                <el-table-column prop="price" label="价格" width="100">
                  <template #default="{ row }">
                    <span class="price-value">{{ row.price.toFixed(2) }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="change_pct" label="涨跌幅">
                  <template #default="{ row }">
                    <span :class="getValueClass(row.change_pct)" class="change-cell">
                      {{ formatPercent(row.change_pct) }}
                    </span>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </ErrorBoundary>
        </div>
      </div>
      
      <!-- Market Summary -->
      <div class="section summary-section">
        <el-card shadow="never" class="summary-card">
          <template #header>
            <div class="card-header">
              <span>市场概况</span>
            </div>
          </template>
          
          <ErrorBoundary>
            <!-- Skeleton when loading -->
            <SkeletonLoader
              v-if="indicesLoading"
              variant="card"
              height="80px"
            />
            
            <!-- Actual content when loaded -->
            <div v-else class="summary-grid">
              <div class="summary-item">
                <div class="summary-label">上涨指数</div>
                <div class="summary-value text-up">
                  {{ indices.filter(i => i.change_pct > 0).length }}
                </div>
              </div>
              <div class="summary-item">
                <div class="summary-label">下跌指数</div>
                <div class="summary-value text-down">
                  {{ indices.filter(i => i.change_pct < 0).length }}
                </div>
              </div>
              <div class="summary-item">
                <div class="summary-label">平盘指数</div>
                <div class="summary-value text-flat">
                  {{ indices.filter(i => i.change_pct === 0).length }}
                </div>
              </div>
              <div class="summary-item">
                <div class="summary-label">平均涨跌</div>
                <div 
                  class="summary-value" 
                  :class="getValueClass(indices.reduce((sum, i) => sum + i.change_pct, 0) / indices.length)"
                >
                  {{ formatPercent(indices.reduce((sum, i) => sum + i.change_pct, 0) / indices.length) }}
                </div>
              </div>
            </div>
          </ErrorBoundary>
        </el-card>
      </div>
    </div>
  </ErrorBoundary>
</template>

<style scoped>
.global-market {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.update-time {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-muted);
}

.section {
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.section-subtitle {
  font-size: 13px;
  color: var(--text-muted);
}

/* Indices Grid */
.indices-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

@media (max-width: 1200px) {
  .indices-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .indices-grid {
    grid-template-columns: 1fr;
  }
}

.index-card {
  border-radius: 8px;
  transition: all 0.3s ease;
}

.index-card:hover {
  transform: translateY(-2px);
}

.index-card :deep(.el-card__body) {
  padding: 16px;
}

.index-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.index-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.index-region {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-system);
  padding: 2px 8px;
  border-radius: 4px;
}

.index-price {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
}

.index-change {
  display: flex;
  gap: 12px;
  font-size: 14px;
  font-weight: 500;
}

.change-value {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
}

.change-percent {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
}

/* Chart Card */
.chart-card {
  border-radius: 8px;
}

.chart-card :deep(.el-card__header) {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-line);
}

.card-header {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

/* Dual Section */
.dual-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

@media (max-width: 992px) {
  .dual-section {
    grid-template-columns: 1fr;
  }
}

.sub-section {
  min-width: 0;
}

.data-card {
  border-radius: 8px;
}

.data-card :deep(.el-card__body) {
  padding: 0;
}

.data-card :deep(.el-table) {
  --el-table-border-color: var(--border-line);
}

.data-card :deep(.el-table th) {
  background-color: #fafafa;
  font-weight: 600;
  color: var(--text-primary);
}

.rate-value,
.price-value {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
  font-weight: 500;
}

.change-cell {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
  font-weight: 600;
}

/* Summary Section */
.summary-card {
  border-radius: 8px;
}

.summary-card :deep(.el-card__header) {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-line);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
}

@media (max-width: 768px) {
  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.summary-item {
  text-align: center;
}

.summary-label {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.summary-value {
  font-size: 32px;
  font-weight: 700;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
}

/* Text Colors */
.text-up {
  color: var(--market-up);
}

.text-down {
  color: var(--market-down);
}

.text-flat {
  color: var(--market-flat);
}
</style>
