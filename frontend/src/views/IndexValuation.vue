<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import type { EChartsOption } from 'echarts'
import { getIndexValuation, getIndexPEHistory, type IndexValuationItem, type IndexPEHistoryItem } from '@/api/market'

const loading = ref(false)
const valuationData = ref<IndexValuationItem[]>([])
const selectedIndex = ref<IndexValuationItem | null>(null)
const historyData = ref<IndexPEHistoryItem[]>([])
const historyLoading = ref(false)
const historyDays = ref(365)
const autoRefresh = ref(false)
let refreshInterval: ReturnType<typeof setInterval> | null = null

const REFRESH_INTERVAL = 30000

const fetchValuation = async () => {
  loading.value = true
  try {
    const response = await getIndexValuation()
    valuationData.value = response.items
    if (!selectedIndex.value && valuationData.value.length > 0) {
      selectedIndex.value = valuationData.value[0]
      fetchHistory()
    }
  } catch (error) {
    console.error('Failed to fetch index valuation:', error)
    ElMessage.error('获取指数估值数据失败')
  } finally {
    loading.value = false
  }
}

const fetchHistory = async () => {
  if (!selectedIndex.value) return
  
  historyLoading.value = true
  try {
    historyData.value = await getIndexPEHistory(selectedIndex.value.index_code, historyDays.value)
  } catch (error) {
    console.error('Failed to fetch PE history:', error)
    ElMessage.error('获取PE历史数据失败')
  } finally {
    historyLoading.value = false
  }
}

const handleCardClick = (item: IndexValuationItem) => {
  selectedIndex.value = item
  fetchHistory()
}

const handleDaysChange = () => {
  fetchHistory()
}

const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    refreshInterval = setInterval(fetchValuation, REFRESH_INTERVAL)
    ElMessage.success('已开启自动刷新 (30秒)')
  } else {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
    ElMessage.info('已关闭自动刷新')
  }
}

const getZoneBgClass = (zone: string): string => {
  if (zone === '低估') return 'zone-undervalued'
  if (zone === '高估') return 'zone-overvalued'
  return 'zone-normal'
}

const getPercentileColor = (percentile: number): string => {
  if (percentile <= 25) return 'var(--market-down)'
  if (percentile >= 75) return 'var(--market-up)'
  return '#1565C0'
}

const historyChartOption = computed<EChartsOption>(() => {
  if (historyData.value.length === 0 || !selectedIndex.value) return {}

  const dates = historyData.value.map(d => formatDate(d.trade_date)).reverse()
  const peValues = historyData.value.map(d => d.pe_ttm).reverse()

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: 'var(--border-line)',
      borderWidth: 1,
      textStyle: { color: 'var(--text-primary)' },
      formatter: (params: unknown) => {
        const p = params as Array<{ axisValue: string; value: number; marker: string }>
        if (!p || p.length === 0) return ''
        const data = p[0]
        return `
          <div style="padding: 8px;">
            <div style="font-weight: 600; margin-bottom: 4px;">${data.axisValue}</div>
            <div>${data.marker} PE(TTM): <strong>${data.value.toFixed(2)}</strong></div>
          </div>
        `
      }
    },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'var(--border-line)' } },
      axisLabel: { color: 'var(--text-muted)', fontSize: 11, rotate: 45 },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'var(--border-line)', type: 'dashed' } },
      axisLine: { show: false },
      axisLabel: { color: 'var(--text-muted)', fontSize: 11 }
    },
    series: [{
      type: 'line',
      data: peValues,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2.5, color: 'var(--brand-navy-dark)' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(0, 51, 153, 0.2)' },
            { offset: 1, color: 'rgba(0, 51, 153, 0.02)' }
          ]
        }
      },
      markArea: {
        silent: true,
        data: [
          [
            { yAxis: 0, itemStyle: { color: 'var(--mark-area-oversold)' } },
            { yAxis: 25 }
          ],
          [
            { yAxis: 75, itemStyle: { color: 'var(--mark-area-overheat)' } },
            { yAxis: 100 }
          ]
        ]
      }
    }]
  }
})

const formatDate = (dateStr: string): string => {
  if (!dateStr || dateStr.length < 8) return dateStr
  return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`
}

onMounted(() => {
  fetchValuation()
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<template>
  <div class="index-valuation" v-loading="loading">
    <div class="page-header">
      <div class="header-left">
        <h2>主要指数估值</h2>
        <span class="total-count">共 {{ valuationData.length }} 个指数</span>
      </div>
      <div class="header-actions">
        <el-button size="small" @click="fetchValuation" :loading="loading">
          刷新
        </el-button>
        <el-button 
          size="small" 
          :type="autoRefresh ? 'primary' : 'default'"
          @click="toggleAutoRefresh"
        >
          {{ autoRefresh ? '停止刷新' : '自动刷新' }}
        </el-button>
      </div>
    </div>

    <div class="valuation-grid">
      <!-- Skeleton cards when loading -->
      <template v-if="loading">
        <SkeletonLoader
          v-for="i in 8"
          :key="`skeleton-card-${i}`"
          variant="valuation-card"
        />
      </template>
      
      <!-- Actual cards when loaded -->
      <template v-else>
        <div
          v-for="item in valuationData"
          :key="item.index_code"
          class="valuation-card"
          :class="{ 'selected': selectedIndex?.index_code === item.index_code }"
          @click="handleCardClick(item)"
        >
          <div class="card-header">
            <div class="index-name">{{ item.index_name }}</div>
            <el-tag 
              v-if="item.is_simulated" 
              size="small" 
              type="warning"
              class="simulated-tag"
            >
              模拟
            </el-tag>
          </div>
          
          <div class="pe-value" :style="{ color: getPercentileColor(item.pe_percentile) }">
            PE: {{ item.pe_ttm.toFixed(2) }}
          </div>

          <div class="percentile-section">
            <div class="percentile-bar">
              <div 
                class="percentile-fill"
                :style="{ 
                  width: `${item.pe_percentile}%`,
                  background: getPercentileColor(item.pe_percentile)
                }"
              ></div>
            </div>
            <div class="percentile-value">{{ item.pe_percentile.toFixed(1) }}%</div>
          </div>

          <div class="zone-badge" :class="getZoneBgClass(item.zone)">
            {{ item.zone }}
          </div>

          <div class="extra-metrics">
            <div class="metric">
              <span class="metric-label">PB</span>
              <span class="metric-value">{{ item.pb.toFixed(2) }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">股息率</span>
              <span class="metric-value">{{ (item.dividend_yield * 100).toFixed(2) }}%</span>
            </div>
          </div>
        </div>
      </template>
    </div>

    <div class="history-section card" v-if="selectedIndex || loading">
      <div class="card-title">
        <div class="title-left">
          <span v-if="selectedIndex">{{ selectedIndex.index_name }} 历史PE走势</span>
          <span v-else>历史PE走势</span>
          <el-tag v-if="selectedIndex" size="small" type="info">{{ selectedIndex.index_code }}</el-tag>
        </div>
        <el-radio-group v-model="historyDays" size="small" @change="handleDaysChange">
          <el-radio-button :value="30">30天</el-radio-button>
          <el-radio-button :value="90">90天</el-radio-button>
          <el-radio-button :value="365">1年</el-radio-button>
          <el-radio-button :value="1095">3年</el-radio-button>
          <el-radio-button :value="1825">5年</el-radio-button>
        </el-radio-group>
      </div>

      <div class="chart-legend">
        <span class="legend-item">
          <span class="legend-color" style="background: var(--mark-area-oversold);"></span>
          低估区 (0-25%)
        </span>
        <span class="legend-item">
          <span class="legend-color" style="background: var(--mark-area-normal);"></span>
          正常区 (25-75%)
        </span>
        <span class="legend-item">
          <span class="legend-color" style="background: var(--mark-area-overheat);"></span>
          高估区 (75-100%)
        </span>
      </div>

      <!-- Skeleton when loading -->
      <SkeletonLoader
        v-if="historyLoading"
        variant="image"
        height="400px"
      />
      
      <!-- Actual chart when loaded -->
      <EChartsWrapper
        v-else
        :option="historyChartOption"
        height="400px"
      />
    </div>

    <div class="empty-state" v-else-if="!loading && valuationData.length === 0">
      <p>暂无指数估值数据</p>
    </div>
  </div>
</template>

<style scoped>
.index-valuation {
  min-height: calc(100vh - 100px); /* Fallback for older browsers */
  min-height: calc(100dvh - 100px);
  padding: var(--spacing-md);
  background: var(--bg-system);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--border-line);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.header-left h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.total-count {
  font-size: 13px;
  color: var(--text-muted);
}

.header-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.valuation-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

@media (max-width: 1400px) {
  .valuation-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 1024px) {
  .valuation-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .valuation-grid {
    grid-template-columns: 1fr;
  }
}

.valuation-card {
  background: var(--bg-card);
  border-radius: 8px;
  padding: var(--spacing-md);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: all 0.25s ease;
  border: 2px solid transparent;
}

.valuation-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 51, 153, 0.12);
}

.valuation-card.selected {
  border-color: var(--brand-navy-dark);
  box-shadow: 0 4px 20px rgba(0, 51, 153, 0.2);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-sm);
}

.index-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.simulated-tag {
  font-size: 10px;
  padding: 0 6px;
  height: 18px;
  line-height: 16px;
}

.pe-value {
  font-size: 24px;
  font-weight: 700;
  font-family: 'DIN Alternate', -apple-system, sans-serif;
  margin-bottom: var(--spacing-sm);
}

.percentile-section {
  margin-bottom: var(--spacing-sm);
}

.percentile-bar {
  width: 100%;
  height: 6px;
  background: var(--bg-system);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 4px;
}

.percentile-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s ease-out;
}

.percentile-value {
  font-size: 12px;
  color: var(--text-muted);
  text-align: right;
}

.zone-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: var(--spacing-sm);
}

.zone-undervalued {
  background: rgba(46, 125, 50, 0.12);
  color: var(--market-down);
}

.zone-normal {
  background: rgba(21, 101, 192, 0.12);
  color: #1565C0;
}

.zone-overvalued {
  background: rgba(230, 57, 53, 0.12);
  color: var(--market-up);
}

.extra-metrics {
  display: flex;
  gap: var(--spacing-md);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--border-line);
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-label {
  font-size: 11px;
  color: var(--text-muted);
}

.metric-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: 'DIN Alternate', -apple-system, sans-serif;
}

.history-section {
  background: var(--bg-card);
  border-radius: 8px;
  padding: var(--spacing-md);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.card-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-sm);
  border-bottom: 1px solid var(--border-line);
}

.title-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.chart-legend {
  display: flex;
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-md);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.legend-color {
  width: 16px;
  height: 12px;
  border-radius: 2px;
  opacity: 0.7;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
  color: var(--text-muted);
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-md);
  }
  
  .header-actions {
    width: 100%;
    justify-content: flex-end;
  }
  
  .chart-legend {
    flex-wrap: wrap;
    gap: var(--spacing-sm);
  }
}
</style>
