<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import { Warning } from '@element-plus/icons-vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import JargonTooltip from '@/components/JargonTooltip.vue'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import DataConfidenceBadge from '@/components/DataConfidenceBadge.vue'
import MarketWordCloud from '@/components/MarketWordCloud.vue'
import type { EChartsOption } from 'echarts'
import { getFearGreedIndex, getERPSpread, getCrowdingAnalysis, getStyleStrength } from '@/api/analytics'
import { getMarketHeatmap, getDomesticMarket } from '@/api/market'
import { getTopFunds, type FundItem } from '@/api/fund'
import { useIndicesStore } from '@/stores/indices'
import { formatNumber, formatSign } from '@/utils/formatters'
import { useBreakpoint } from '@/composables/useBreakpoint'

// Breakpoint detection for responsive tables
const { isMobile, isXs, isTablet, isDesktop, isWide } = useBreakpoint()

// Current date for title bar
const currentDate = computed(() => {
  const now = new Date()
  const month = now.getMonth() + 1
  const day = now.getDate()
  const weekdays = ['日', '一', '二', '三', '四', '五', '六']
  return `${month}月${day}日 周${weekdays[now.getDay()]}`
})

// Responsive grid layout class
const gridLayoutClass = computed(() => {
  if (isWide.value) return 'grid-wide'
  if (isDesktop.value) return 'grid-desktop'
  if (isTablet.value) return 'grid-tablet'
  return 'grid-mobile'
})

// Loading states - per-widget for progressive loading
const fearGreedLoading = ref(true)
const erpLoading = ref(true)
const crowdingLoading = ref(true)
const styleStrengthLoading = ref(true)
const heatmapLoading = ref(true)
const sectorsLoading = ref(true)
const gainersLoading = ref(true)

// Data source states - track real/delayed/simulated data for each widget
type DataSource = 'real' | 'delayed' | 'simulated'
const fearGreedDataSource = ref<DataSource>('simulated')
const erpDataSource = ref<DataSource>('simulated')
const crowdingDataSource = ref<DataSource>('simulated')
const styleStrengthDataSource = ref<DataSource>('simulated')
const heatmapDataSource = ref<DataSource>('simulated')
const sectorsDataSource = ref<DataSource>('simulated')
const gainersDataSource = ref<DataSource>('simulated')

// Real-time data refresh interval (for other data, not indices)
let refreshInterval: ReturnType<typeof setInterval> | null = null
const REFRESH_INTERVAL = 30000

// Index quotes data - now from shared store
const indicesStore = useIndicesStore()
const { indices: indexQuotes, loading: indicesLoading } = storeToRefs(indicesStore)

// Fear/Greed data
interface FearGreedData {
  trade_date: string
  composite_score: number
  sentiment_status: string
  factor_volatility: number | null
  factor_safe_haven: number | null
  factor_margin_ratio: number | null
  factor_volume_deviation: number | null
  factor_futures_basis: number | null
  factor_stock_strength: number | null
}
const fearGreedData = ref<FearGreedData | null>(null)
const fearGreedHistory = ref<FearGreedData[]>([])

// ERP spread data
interface ERPData {
  index_code: string
  index_name: string
  trade_date: string
  pe_ttm: number
  treasury_yield_10y: number
  erp_spread: number
  percentile_rank_10y: number | null
  index_close_price: number | null
}
const erpData = ref<ERPData | null>(null)

// Crowding data
interface CrowdingData {
  asset_code: string
  trade_date: string
  category: string
  crowding_score: number
  pe_percentile: number
  close_price: number | null
}
const crowdingData = ref<CrowdingData[]>([])

// Style strength data
interface StyleStrengthData {
  trade_date: string
  index_code_num: string
  index_code_den: string
  ratio_value: number
  percentile_rank_3y: number | null
}
const styleStrengthData = ref<StyleStrengthData[]>([])

// Top gainers/losers
const topGainers = ref<FundItem[]>([])
const topLosers = ref<FundItem[]>([])

// Sector performance
interface SectorPerformance {
  name: string
  change_pct: number
  volume: number
}
const sectorPerformance = ref<SectorPerformance[]>([])
const sectorPeriod = ref('today')

// Word cloud keywords derived from sector performance
const wordCloudKeywords = computed(() => {
  if (sectorPerformance.value.length === 0) return []
  
  // Normalize weights based on absolute change percentage
  const maxAbsChange = Math.max(...sectorPerformance.value.map(s => Math.abs(s.change_pct)))
  
  return sectorPerformance.value.map(sector => ({
    name: sector.name,
    weight: maxAbsChange > 0 ? Math.abs(sector.change_pct) / maxAbsChange : 0.5,
    change: sector.change_pct,
  }))
})

// Fear/Greed chart option
const fearGreedOption = computed<EChartsOption>(() => {
  const score = fearGreedData.value?.composite_score ?? 50
  const status = fearGreedData.value?.sentiment_status ?? '中性'
  
  // Dynamic color based on score
  let color = '#003399'
  if (score >= 80) color = '#E63935' // Extreme Greed
  else if (score >= 60) color = '#FF8C00' // Greed
  else if (score >= 40) color = '#003399' // Neutral
  else if (score >= 20) color = '#2E7D32' // Fear
  else color = '#1B5E20' // Extreme Fear
  
  return {
    series: [{
      type: 'gauge',
      startAngle: 180,
      endAngle: 0,
      min: 0,
      max: 100,
      splitNumber: 5,
      itemStyle: { color },
      progress: { show: true, width: 18 },
      axisLine: { lineStyle: { width: 18, color: [[1, '#E5E8ED']] } },
      axisTick: { show: false },
      splitLine: { length: 15, lineStyle: { width: 2, color: '#999' } },
      axisLabel: { distance: 25, fontSize: 12, color: '#4A4A4A' },
      pointer: { length: '80%', width: 8 },
      detail: { 
        valueAnimation: true, 
        fontSize: 28, 
        offsetCenter: [0, '70%'],
        formatter: (value: number) => value.toFixed(2),
        color: '#1A1A1A'
      },
      title: { 
        offsetCenter: [0, '90%'], 
        fontSize: 14,
        color: '#4A4A4A'
      },
      data: [{ value: score, name: status }],
    }],
  }
})

// Fear/Greed history chart
const fearGreedHistoryOption = computed<EChartsOption>(() => {
  if (fearGreedHistory.value.length === 0) return {}
  
  const dates = fearGreedHistory.value.map(d => d.trade_date).reverse()
  const scores = fearGreedHistory.value.map(d => d.composite_score).reverse()
  
  return {
    tooltip: { trigger: 'axis' },
    grid: { top: 10, left: 40, right: 10, bottom: 30 },
    xAxis: { 
      type: 'category', 
      data: dates,
      axisLabel: { fontSize: 10, color: '#999' },
      axisLine: { lineStyle: { color: '#E5E8ED' } }
    },
    yAxis: { 
      type: 'value', 
      min: 0, 
      max: 100,
      splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } },
      axisLabel: { fontSize: 10, color: '#999' }
    },
    series: [{
      type: 'line',
      data: scores,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: '#003399' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(0, 51, 153, 0.3)' },
            { offset: 1, color: 'rgba(0, 51, 153, 0.05)' }
          ]
        }
      }
    }]
  }
})

// ERP chart option
const erpOption = computed<EChartsOption>(() => {
  if (!erpData.value) return {}
  
  const spread = erpData.value.erp_spread
  const percentile = erpData.value.percentile_rank_10y ?? 50
  
  return {
    series: [{
      type: 'gauge',
      startAngle: 180,
      endAngle: 0,
      min: 0,
      max: 100,
      radius: '90%',
      center: ['50%', '60%'],
      splitNumber: 4,
      itemStyle: { color: '#003399' },
      progress: { show: true, width: 16 },
      axisLine: { lineStyle: { width: 16, color: [[1, '#E5E8ED']] } },
      axisTick: { show: false },
      splitLine: { length: 12, lineStyle: { width: 2, color: '#999' } },
      axisLabel: {
        distance: 20,
        fontSize: 11,
        formatter: (value: number) => {
          if (value === 0) return '高估'
          if (value === 33) return ''
          if (value === 50) return '中'
          if (value === 66) return ''
          if (value === 100) return '低估'
          return ''
        }
      },
      pointer: { length: '55%', width: 6 },
      title: {
        offsetCenter: [0, '30%'],
        fontSize: 14,
        color: '#4A4A4A'
      },
      detail: {
        valueAnimation: true,
        fontSize: 20,
        offsetCenter: [0, '40%'],
        formatter: `{a|${spread.toFixed(2)}%}\n{b|历史${percentile.toFixed(0)}%分位}`,
        rich: {
          a: { fontSize: 20, color: '#1A1A1A', fontWeight: 'bold' },
          b: { fontSize: 11, color: '#999', padding: [8, 0, 0, 0] }
        }
      },
      data: [{ value: percentile }],
    }]
  }
})

// Crowding chart option (scatter plot)
const crowdingOption = computed<EChartsOption>(() => {
  if (crowdingData.value.length === 0) return {}

  const data = crowdingData.value.map(d => [d.pe_percentile, d.crowding_score, d.asset_code])

  return {
    tooltip: {
      formatter: (params: any) => {
        return `${params.data[2]}<br/>PE分位: ${params.data[0].toFixed(2)}%<br/>拥挤度: ${params.data[1].toFixed(2)}`
      }
    },
    grid: { top: 20, left: 50, right: 20, bottom: 40 },
    xAxis: {
      type: 'value',
      name: 'PE分位',
      nameLocation: 'middle',
      nameGap: 25,
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } }
    },
    yAxis: {
      type: 'value',
      name: '拥挤度',
      nameLocation: 'middle',
      nameGap: 35,
      splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } }
    },
    visualMap: {
      show: false,
      dimension: 1,
      min: -2,
      max: 2,
      inRange: {
        color: ['#2E7D32', '#FFD700', '#E63935']
      }
    },
    series: [{
      type: 'scatter',
      symbolSize: 12,
      data,
      itemStyle: { opacity: 0.8 }
    }]
  } as EChartsOption
})

// Style strength chart
const styleStrengthOption = computed<EChartsOption>(() => {
  if (styleStrengthData.value.length === 0) return {}
  
  const history = styleStrengthData.value.slice(0, 30).reverse()
  
  return {
    tooltip: { trigger: 'axis' },
    legend: { 
      data: ['大盘/小盘', '价值/成长'],
      top: 0,
      textStyle: { fontSize: 11 }
    },
    grid: { top: 30, left: 40, right: 10, bottom: 30 },
    xAxis: { 
      type: 'category', 
      data: history.map(d => d.trade_date),
      axisLabel: { fontSize: 10, color: '#999' }
    },
    yAxis: { 
      type: 'value',
      splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } }
    },
    series: [
      {
        name: '大盘/小盘',
        type: 'line',
        data: history.filter(d => d.index_code_num.includes('300')).map(d => d.ratio_value),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: '#003399' }
      },
      {
        name: '价值/成长',
        type: 'line',
        data: history.filter(d => !d.index_code_num.includes('300')).map(d => d.ratio_value),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: '#E63935' }
      }
    ]
  }
})

// Heatmap chart option
const heatmapOption = ref<EChartsOption>({
  tooltip: {
    position: 'top',
    formatter: (params: any) => {
      if (params.data) {
        const [colIdx, rowIdx, value] = params.data
        const cols = (heatmapOption.value.xAxis as any)?.data as string[]
        const rows = (heatmapOption.value.yAxis as any)?.data as string[]
        return `${rows[rowIdx]} - ${cols[colIdx]}<br/>收益率: ${value.toFixed(2)}%`
      }
      return ''
    }
  },
  grid: { top: 10, left: 100, right: 10, bottom: 50 },
  xAxis: { type: 'category', data: [], splitArea: { show: true }, axisLabel: { rotate: 45 } },
  yAxis: { type: 'category', data: [], splitArea: { show: true } },
  visualMap: {
    min: -50,
    max: 150,
    calculable: true,
    orient: 'horizontal',
    left: 'center',
    bottom: 0,
    inRange: {
      color: ['#E63935', '#FFFFFF', '#2E7D32'],
    },
  },
  series: [{
    type: 'heatmap',
    data: [],
    label: { show: false },
    emphasis: {
      itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' },
    },
  }],
} as EChartsOption)

// Fetch all data (indices handled by store)
// Progressive widget loaders - each widget loads independently
const fetchFearGreedWidget = async () => {
  fearGreedLoading.value = true
  try {
    const data = await getFearGreedIndex()
    if (data && Array.isArray(data) && data.length > 0) {
      fearGreedData.value = data[0]
      fearGreedHistory.value = data.slice(0, 30)
      fearGreedDataSource.value = 'real'
    }
  } catch {
    // Fallback: neutral state
    fearGreedData.value = {
      trade_date: new Date().toISOString().split('T')[0],
      composite_score: 50,
      sentiment_status: '中性',
      factor_volatility: null,
      factor_safe_haven: null,
      factor_margin_ratio: null,
      factor_volume_deviation: null,
      factor_futures_basis: null,
      factor_stock_strength: null
    }
    fearGreedDataSource.value = 'simulated'
  } finally {
    fearGreedLoading.value = false
  }
}

const fetchERPWidget = async () => {
  erpLoading.value = true
  try {
    const data = await getERPSpread()
    if (data && Array.isArray(data) && data.length > 0) {
      erpData.value = data[0]
      erpDataSource.value = 'real'
    }
  } catch {
    // Fallback: placeholder data
    erpData.value = {
      index_code: '000300',
      index_name: '沪深300',
      trade_date: new Date().toISOString().split('T')[0],
      pe_ttm: 12.0,
      treasury_yield_10y: 2.5,
      erp_spread: 5.5,
      percentile_rank_10y: 50,
      index_close_price: null
    }
    erpDataSource.value = 'simulated'
  } finally {
    erpLoading.value = false
  }
}

const fetchCrowdingWidget = async () => {
  crowdingLoading.value = true
  try {
    const data = await getCrowdingAnalysis()
    if (data && Array.isArray(data)) {
      crowdingData.value = data
      crowdingDataSource.value = 'real'
    }
  } catch {
    // Fallback: empty array - widget will show empty state
    crowdingData.value = []
    crowdingDataSource.value = 'simulated'
  } finally {
    crowdingLoading.value = false
  }
}

const fetchStyleStrengthWidget = async () => {
  styleStrengthLoading.value = true
  try {
    const data = await getStyleStrength()
    if (data && Array.isArray(data)) {
      styleStrengthData.value = data
      styleStrengthDataSource.value = 'real'
    }
  } catch {
    // Fallback: empty array
    styleStrengthData.value = []
    styleStrengthDataSource.value = 'simulated'
  } finally {
    styleStrengthLoading.value = false
  }
}

const fetchHeatmapWidget = async () => {
  heatmapLoading.value = true
  try {
    const heatmap = await getMarketHeatmap()
    if (heatmap && heatmap.rows && heatmap.cols && heatmap.cells) {
      ;(heatmapOption.value.xAxis as any).data = heatmap.cols
      ;(heatmapOption.value.yAxis as any).data = heatmap.rows

      const rowIndexMap = new Map(heatmap.rows.map((r, i) => [r, i]))
      const colIndexMap = new Map(heatmap.cols.map((c, i) => [c, i]))

      ;(heatmapOption.value.series as any)[0].data = heatmap.cells.map(c => [
        colIndexMap.get(c.col) ?? 0,
        rowIndexMap.get(c.row) ?? 0,
        c.value
      ])
      heatmapDataSource.value = 'real'
    }
  } catch {
    heatmapDataSource.value = 'simulated'
  } finally {
    heatmapLoading.value = false
  }
}

const fetchSectorsWidget = async () => {
  sectorsLoading.value = true
  try {
    const data = await getDomesticMarket()
    if (data && data.sectors && data.sectors.length > 0) {
      sectorPerformance.value = data.sectors.map(sector => ({
        name: sector.name,
        change_pct: sector.change_pct,
        volume: 0
      }))
      sectorsDataSource.value = 'real'
    }
  } catch {
    // Fallback: empty array
    sectorPerformance.value = []
    sectorsDataSource.value = 'simulated'
  } finally {
    sectorsLoading.value = false
  }
}

const fetchTopFundsWidget = async () => {
  gainersLoading.value = true
  try {
    const data = await getTopFunds(10)
    if (data) {
      topGainers.value = data.gainers as FundItem[]
      topLosers.value = data.losers as FundItem[]
      gainersDataSource.value = 'real'
    }
  } catch {
    // Fallback: empty arrays
    topGainers.value = []
    topLosers.value = []
    gainersDataSource.value = 'simulated'
  } finally {
    gainersLoading.value = false
  }
}

// Format helpers
const formatChange = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return '--%'
  return formatSign(val, '%')
}

const getValueClass = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return ''
  return val >= 0 ? 'text-up' : 'text-down'
}

// Handle word cloud keyword click
const handleKeywordClick = (keyword: { name: string; weight: number; change?: number }) => {
  ElMessage.info(`${keyword.name}: ${keyword.change !== undefined ? formatChange(keyword.change) : '无涨跌数据'}`)
}

// Mobile carousel: Group indices into slides (3 per slide on mobile, 2 on XS)
const indexSlides = computed(() => {
  const indicesPerSlide = isXs.value ? 2 : 3
  const entries = Object.entries(indexQuotes.value)
  const slides: Array<Array<[string, typeof indexQuotes.value[string]]>> = []
  
  for (let i = 0; i < entries.length; i += indicesPerSlide) {
    slides.push(entries.slice(i, i + indicesPerSlide))
  }
  
  return slides
})

// Lifecycle
onMounted(() => {
  // Fire all widget loaders simultaneously - they'll render independently
  fetchFearGreedWidget()
  fetchERPWidget()
  fetchCrowdingWidget()
  fetchStyleStrengthWidget()
  fetchHeatmapWidget()
  fetchSectorsWidget()
  fetchTopFundsWidget()
  
  // Auto-refresh every 30s (only when tab is visible)
  refreshInterval = setInterval(() => {
    if (document.visibilityState === 'visible') {
      fetchFearGreedWidget()
      fetchERPWidget()
      fetchCrowdingWidget()
      fetchStyleStrengthWidget()
      fetchHeatmapWidget()
      fetchSectorsWidget()
      fetchTopFundsWidget()
    }
  }, REFRESH_INTERVAL)
  
  // Index Bar uses shared Pinia store - loads instantly
  indicesStore.startAutoRefresh(30000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
  // Stop the shared store auto-refresh
  indicesStore.stopAutoRefresh()
})
</script>

<template>
  <div class="dashboard">
    <!-- Index Bar -->
    <div class="index-bar">
      <div class="index-bar-header">
        <h2 class="index-bar-title">实时行情</h2>
        <span class="refresh-hint">每30秒自动刷新</span>
      </div>
      <div class="index-bar-content" v-loading="indicesLoading">
        <!-- Skeleton when loading -->
        <template v-if="indicesLoading || Object.keys(indexQuotes).length === 0">
          <SkeletonLoader
            v-for="i in 6"
            :key="`index-skeleton-${i}`"
            variant="index-item"
          />
        </template>
        
        <!-- Desktop: Horizontal scroll layout -->
        <template v-else-if="!isMobile">
          <div 
            v-for="(quote, code) in indexQuotes" 
            :key="code" 
            class="index-item"
          >
            <div class="index-name">{{ quote?.name || code }}</div>
            <div class="index-price">{{ (quote?.price ?? 0).toFixed(2) }}</div>
            <div class="index-change" :class="getValueClass(quote?.change ?? null)">
              {{ formatChange(quote?.change_pct ?? null) }}
            </div>
          </div>
          <div v-if="Object.keys(indexQuotes).length === 0" class="index-empty">
            暂无行情数据
          </div>
        </template>
        
        <!-- Mobile: Carousel layout -->
        <el-carousel 
          v-else
          :interval="5000" 
          :loop="true" 
          :autoplay="true"
          indicator-position="outside"
          height="80px"
          class="index-carousel"
        >
          <el-carousel-item 
            v-for="(slide, slideIndex) in indexSlides" 
            :key="slideIndex"
          >
            <div class="index-slide">
              <div 
                v-for="[code, quote] in slide" 
                :key="code" 
                class="index-item-mobile"
              >
                <div class="index-name">{{ quote?.name || code }}</div>
                <div class="index-price">{{ (quote?.price ?? 0).toFixed(2) }}</div>
                <div class="index-change" :class="getValueClass(quote?.change ?? null)">
                  {{ formatChange(quote?.change_pct ?? null) }}
                </div>
              </div>
            </div>
          </el-carousel-item>
        </el-carousel>
      </div>
    </div>

    <!-- Compact Title Bar -->
    <div class="title-bar">
      <span class="title-bar-text">宏观复盘看板</span>
      <span class="title-bar-date">{{ currentDate }}</span>
    </div>

    <!-- Main Grid -->
    <div class="dashboard-grid" :class="gridLayoutClass">
      <!-- Fear/Greed Index Widget -->
      <div class="card widget-fear-greed" role="region" aria-label="恐惧贪婪指数仪表盘" aria-live="polite">
        <div class="card-header">
          <div class="card-title">恐惧贪婪指数</div>
          <DataConfidenceBadge 
            :source="fearGreedDataSource" 
            :timestamp="fearGreedData?.trade_date" 
          />
        </div>
        
        <ErrorBoundary>
          <!-- Skeleton when loading -->
          <template v-if="fearGreedLoading">
            <div class="widget-content">
              <SkeletonLoader variant="gauge" height="200px" />
            </div>
            <div class="factor-breakdown">
              <div class="factor-item" v-for="i in 3" :key="`factor-${i}`">
                <span class="skeleton skeleton-text" style="width: 40px; height: 11px;"></span>
                <span class="skeleton skeleton-text" style="width: 60px; height: 14px;"></span>
              </div>
            </div>
          </template>
          
          <!-- Actual content when loaded -->
          <template v-else>
            <div class="widget-content">
              <div class="gauge-container">
                <EChartsWrapper
                  :option="fearGreedOption"
                  height="200px"
                />
              </div>
              <div class="history-chart">
                <EChartsWrapper
                  :option="fearGreedHistoryOption"
                  height="100px"
                />
              </div>
            </div>
            <div class="factor-breakdown" v-if="fearGreedData">
              <div class="factor-item">
                <JargonTooltip term="波动率" definition="衡量价格波动幅度的统计指标，反映风险水平" />
                <span class="factor-value">{{ formatNumber(fearGreedData.factor_volatility) }}</span>
              </div>
              <div class="factor-item">
                <JargonTooltip term="避险情绪" definition="市场恐慌时资金流向安全资产(如黄金、国债)的倾向" />
                <span class="factor-value">{{ formatNumber(fearGreedData.factor_safe_haven) }}</span>
              </div>
              <div class="factor-item">
                <JargonTooltip term="杠杆水平" definition="融资交易占总交易的比例，反映市场风险偏好" />
                <span class="factor-value">{{ formatNumber(fearGreedData.factor_margin_ratio) }}</span>
              </div>
            </div>
            <div class="risk-warning" v-if="!fearGreedLoading">
              <el-icon><Warning /></el-icon>
              <span>投资有风险，决策需谨慎</span>
            </div>
          </template>
        </ErrorBoundary>
      </div>

      <!-- ERP Spread Widget -->
      <div class="card widget-erp" role="region" aria-label="股债性价比ERP分析" aria-live="polite">
        <div class="card-header">
          <div class="card-title">股债性价比 (ERP)</div>
          <DataConfidenceBadge 
            :source="erpDataSource" 
            :timestamp="erpData?.trade_date" 
          />
        </div>
        
        <ErrorBoundary>
          <!-- Skeleton when loading -->
          <template v-if="erpLoading">
            <div class="widget-content">
              <SkeletonLoader variant="gauge" height="220px" />
            </div>
          </template>
          
          <!-- Actual content when loaded -->
          <template v-else>
            <div class="widget-content">
              <EChartsWrapper
                :option="erpOption"
                height="300px"
              />
            </div>
            <div class="erp-details" v-if="erpData">
              <div class="detail-row">
                <JargonTooltip term="PE(TTM)" definition="滚动市盈率，当前股价/过去12个月每股收益" />
                <span class="detail-value">{{ erpData.pe_ttm.toFixed(2) }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">10Y国债收益率</span>
                <span class="detail-value">{{ erpData.treasury_yield_10y.toFixed(2) }}%</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">指数收盘</span>
                <span class="detail-value">{{ erpData.index_close_price?.toFixed(2) ?? '-' }}</span>
              </div>
            </div>
            <div class="risk-warning" v-if="!erpLoading">
              <el-icon><Warning /></el-icon>
              <span>仅供参考，不构成投资建议。投资有风险，决策需谨慎</span>
            </div>
          </template>
        </ErrorBoundary>
      </div>

      <!-- Market Crowding Widget -->
      <div class="card widget-crowding" role="region" aria-label="市场拥挤度分析" aria-live="polite">
        <div class="card-header">
          <div class="card-title">市场拥挤度</div>
          <DataConfidenceBadge :source="crowdingDataSource" />
        </div>
        
        <ErrorBoundary>
          <!-- Skeleton when loading -->
          <template v-if="crowdingLoading">
            <div class="widget-content">
              <SkeletonLoader variant="heatmap" height="280px" />
            </div>
          </template>
          
          <!-- Actual content when loaded -->
          <template v-else>
            <div class="widget-content">
              <EChartsWrapper
                :option="crowdingOption"
                height="280px"
              />
            </div>
            <div class="crowding-legend">
              <span class="legend-item">
                <span class="legend-dot low"></span>低拥挤
              </span>
              <span class="legend-item">
                <span class="legend-dot mid"></span>中等
              </span>
              <span class="legend-item">
                <span class="legend-dot high"></span>高拥挤
              </span>
            </div>
          </template>
        </ErrorBoundary>
      </div>

      <!-- Style Strength Widget -->
      <div class="card widget-style" role="region" aria-label="市场风格强度分析" aria-live="polite">
        <div class="card-header">
          <div class="card-title">风格强度</div>
          <DataConfidenceBadge :source="styleStrengthDataSource" />
        </div>
        
        <ErrorBoundary>
          <!-- Skeleton when loading -->
          <template v-if="styleStrengthLoading">
            <div class="widget-content">
              <SkeletonLoader variant="image" height="280px" />
            </div>
          </template>
          
          <!-- Actual content when loaded -->
          <template v-else>
            <div class="widget-content">
              <EChartsWrapper
                :option="styleStrengthOption"
                height="280px"
              />
            </div>
          </template>
        </ErrorBoundary>
      </div>

      <!-- Top Gainers Table -->
      <div class="card widget-gainers">
        <div class="card-header">
          <div class="card-title">涨幅榜 TOP10</div>
          <DataConfidenceBadge :source="gainersDataSource" />
        </div>
        
        <ErrorBoundary>
          <!-- Skeleton when loading -->
          <SkeletonLoader
            v-if="gainersLoading"
            variant="table"
            :rows="10"
            :columns="4"
          />
          
          <!-- Desktop: Table with sticky first column -->
          <div v-else-if="!isMobile" class="table-container">
            <el-table
              :data="topGainers"
              size="small"
              max-height="300"
            >
              <el-table-column prop="fund_code" label="代码" width="80" class-name="sticky-column" />
              <el-table-column prop="fund_name" label="名称" min-width="120" show-overflow-tooltip />
              <el-table-column prop="fund_type" label="类型" width="80" />
              <el-table-column prop="return_1y" label="收益%" width="90" sortable>
                <template #default="{ row }">
                  <span class="text-up">{{ formatNumber(row.return_1y) }}</span>
                </template>
              </el-table-column>
            </el-table>
            <div class="scroll-indicator scroll-indicator-left"></div>
            <div class="scroll-indicator scroll-indicator-right"></div>
          </div>
          
          <!-- Mobile/XS: Card layout -->
          <div v-else class="fund-cards-mobile">
            <div v-for="fund in topGainers" :key="fund.fund_code" class="fund-card">
              <div class="fund-header">
                <span class="fund-code">{{ fund.fund_code }}</span>
                <span class="fund-return text-up">{{ formatNumber(fund.return_1y) }}%</span>
              </div>
              <div class="fund-name">{{ fund.fund_name }}</div>
              <div v-if="!isXs" class="fund-type">{{ fund.fund_type }}</div>
            </div>
          </div>
        </ErrorBoundary>
      </div>

      <!-- Top Losers Table -->
      <div class="card widget-losers">
        <div class="card-header">
          <div class="card-title">跌幅榜 TOP10</div>
          <DataConfidenceBadge :source="gainersDataSource" />
        </div>
        
        <ErrorBoundary>
          <!-- Skeleton when loading -->
          <SkeletonLoader
            v-if="gainersLoading"
            variant="table"
            :rows="10"
            :columns="4"
          />
          
          <!-- Desktop: Table with sticky first column -->
          <div v-else-if="!isMobile" class="table-container">
            <el-table
              :data="topLosers"
              size="small"
              max-height="300"
            >
              <el-table-column prop="fund_code" label="代码" width="80" class-name="sticky-column" />
              <el-table-column prop="fund_name" label="名称" min-width="120" show-overflow-tooltip />
              <el-table-column prop="fund_type" label="类型" width="80" />
              <el-table-column prop="return_1y" label="收益%" width="90" sortable>
                <template #default="{ row }">
                  <span class="text-down">{{ formatNumber(row.return_1y) }}</span>
                </template>
              </el-table-column>
            </el-table>
            <div class="scroll-indicator scroll-indicator-left"></div>
            <div class="scroll-indicator scroll-indicator-right"></div>
          </div>
          
          <!-- Mobile/XS: Card layout -->
          <div v-else class="fund-cards-mobile">
            <div v-for="fund in topLosers" :key="fund.fund_code" class="fund-card">
              <div class="fund-header">
                <span class="fund-code">{{ fund.fund_code }}</span>
                <span class="fund-return text-down">{{ formatNumber(fund.return_1y) }}%</span>
              </div>
              <div class="fund-name">{{ fund.fund_name }}</div>
              <div v-if="!isXs" class="fund-type">{{ fund.fund_type }}</div>
            </div>
          </div>
        </ErrorBoundary>
      </div>
    </div>

    <!-- Heatmap Section -->
    <div class="card heatmap-card">
      <div class="card-header">
        <div class="card-title">多周期热力矩阵</div>
        <DataConfidenceBadge :source="heatmapDataSource" />
      </div>
      
      <ErrorBoundary>
        <!-- Skeleton when loading -->
        <SkeletonLoader
          v-if="heatmapLoading"
          variant="heatmap"
          :height="isMobile ? '250px' : '300px'"
        />
        
        <!-- Actual chart when loaded -->
        <EChartsWrapper
          v-else
          :option="heatmapOption"
          :height="isMobile ? '250px' : '300px'"
        />
      </ErrorBoundary>
    </div>

    <!-- Sector Performance Overview -->
    <div class="card sector-card">
      <div class="card-header">
        <div class="card-title">板块表现概览</div>
        <div class="card-actions">
          <DataConfidenceBadge :source="sectorsDataSource" />
          <el-radio-group v-model="sectorPeriod" size="small">
            <el-radio-button value="today">今日</el-radio-button>
            <el-radio-button value="5d">近5日</el-radio-button>
            <el-radio-button value="20d">近20日</el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <ErrorBoundary>
        <!-- Desktop: Grid layout -->
        <div v-if="!isMobile" class="sector-grid">
          <div
            v-for="sector in sectorPerformance"
            :key="sector.name"
            class="sector-item"
            :class="getValueClass(sector.change_pct)"
          >
            <div class="sector-name">{{ sector.name }}</div>
            <div class="sector-change">{{ formatChange(sector.change_pct) }}</div>
          </div>
        </div>

        <!-- Mobile: Accordion layout -->
        <el-collapse v-else class="sector-collapse" accordion>
          <el-collapse-item
            v-for="sector in sectorPerformance"
            :key="sector.name"
            :name="sector.name"
          >
            <template #title>
              <div class="sector-collapse-title" :class="getValueClass(sector.change_pct)">
                <span class="sector-name">{{ sector.name }}</span>
                <span class="sector-change">{{ formatChange(sector.change_pct) }}</span>
              </div>
            </template>
            <div class="sector-collapse-content">
              <div class="sector-detail">
                <span class="detail-label">涨跌幅</span>
                <span class="detail-value" :class="getValueClass(sector.change_pct)">
                  {{ formatChange(sector.change_pct) }}
                </span>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>

        <div v-if="sectorsLoading" class="sector-loading">
          <SkeletonLoader variant="table" :rows="4" :columns="3" />
        </div>
      </ErrorBoundary>
    </div>

    <!-- Market Sentiment Word Cloud -->
    <div class="card word-cloud-card" :class="{ 'mobile-hidden': isMobile }">
      <div class="card-header">
        <div class="card-title">市场热点词云</div>
        <DataConfidenceBadge :source="sectorsDataSource" />
      </div>
      
      <ErrorBoundary>
        <MarketWordCloud
          :keywords="wordCloudKeywords"
          :loading="sectorsLoading"
          empty-message="暂无板块热点数据"
          @keyword-click="handleKeywordClick"
        />
      </ErrorBoundary>
    </div>
  </div>
</template>

<style scoped>
/* Index Bar */
.index-bar {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 12px 16px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.index-bar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.index-bar-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.refresh-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.index-bar-content {
  display: flex;
  gap: 24px;
  overflow-x: auto;
  padding: 4px 0;
}

.index-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: var(--bg-system);
  border-radius: 4px;
  min-width: 180px;
}

.index-name {
  font-size: 13px;
  color: var(--text-regular);
  white-space: nowrap;
}

.index-price {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.index-change {
  font-size: 13px;
  font-weight: 500;
}

.index-empty {
  color: var(--text-muted);
  font-size: 13px;
  padding: 20px;
}

/* Mobile Index Carousel */
.index-carousel {
  width: 100%;
}

.index-slide {
  display: flex;
  gap: 12px;
  padding: 4px 0;
}

.index-item-mobile {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px;
  background: var(--bg-system);
  border-radius: 4px;
  flex: 1;
  min-width: 0;
}

.index-item-mobile .index-name {
  font-size: 12px;
  text-align: center;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.index-item-mobile .index-price {
  font-size: 14px;
  font-weight: 600;
}

.index-item-mobile .index-change {
  font-size: 12px;
  font-weight: 500;
}

/* Carousel controls - WCAG 44px touch targets */
:deep(.index-carousel .el-carousel__button) {
  width: 44px;
  height: 44px;
  min-width: 44px;
  min-height: 44px;
}

:deep(.index-carousel .el-carousel__indicators) {
  padding: 8px 0;
}

:deep(.index-carousel .el-carousel__indicator) {
  padding: 4px;
}

:deep(.index-carousel .el-carousel__arrow) {
  width: 44px;
  height: 44px;
  min-width: 44px;
  min-height: 44px;
}

@media (max-width: 375px) {
  .index-slide {
    gap: 8px;
  }
  
  .index-item-mobile {
    padding: 8px;
  }
  
  .index-item-mobile .index-name {
    font-size: 11px;
  }
  
  .index-item-mobile .index-price {
    font-size: 13px;
  }
  
  .index-item-mobile .index-change {
    font-size: 11px;
  }
}

/* Dashboard Container - Max-width constraint */
.dashboard {
  padding: 0;
  max-width: 1600px;
  margin: 0 auto;
}

/* Compact Title Bar */
.title-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--bg-card);
  border-radius: 4px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.title-bar-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.title-bar-date {
  font-size: 13px;
  color: var(--text-muted);
}

@media (max-width: 768px) {
  .title-bar {
    padding: 10px 12px;
  }
  
  .title-bar-text {
    font-size: 15px;
  }
  
  .title-bar-date {
    font-size: 12px;
  }
}

/* Dashboard Grid - 12-column responsive system */
.dashboard-grid {
  display: grid;
  gap: 16px;
  margin-bottom: 16px;
}

/* Mobile (<768px): Single column, all widgets full-width */
.dashboard-grid.grid-mobile {
  grid-template-columns: 1fr;
}

.dashboard-grid.grid-mobile .widget-fear-greed,
.dashboard-grid.grid-mobile .widget-erp,
.dashboard-grid.grid-mobile .widget-crowding,
.dashboard-grid.grid-mobile .widget-style,
.dashboard-grid.grid-mobile .widget-gainers,
.dashboard-grid.grid-mobile .widget-losers {
  grid-column: span 1;
}

/* Tablet (768-1024px): 2-column layout */
.dashboard-grid.grid-tablet {
  grid-template-columns: repeat(2, 1fr);
}

.dashboard-grid.grid-tablet .widget-fear-greed,
.dashboard-grid.grid-tablet .widget-erp {
  grid-column: span 2;
}

.dashboard-grid.grid-tablet .widget-crowding,
.dashboard-grid.grid-tablet .widget-style,
.dashboard-grid.grid-tablet .widget-gainers,
.dashboard-grid.grid-tablet .widget-losers {
  grid-column: span 1;
}

/* Desktop (1024-1400px): 2-column layout with proper spans */
.dashboard-grid.grid-desktop {
  grid-template-columns: repeat(2, 1fr);
}

.dashboard-grid.grid-desktop .widget-fear-greed,
.dashboard-grid.grid-desktop .widget-erp {
  grid-column: span 2;
}

.dashboard-grid.grid-desktop .widget-crowding,
.dashboard-grid.grid-desktop .widget-style,
.dashboard-grid.grid-desktop .widget-gainers,
.dashboard-grid.grid-desktop .widget-losers {
  grid-column: span 1;
}

/* Wide (>1400px): 12-column grid with custom spans */
.dashboard-grid.grid-wide {
  grid-template-columns: repeat(12, 1fr);
}

/* Row 1: Fear/Greed (5 cols) + ERP (3 cols) + Crowding (4 cols) */
.dashboard-grid.grid-wide .widget-fear-greed {
  grid-column: span 5;
}

.dashboard-grid.grid-wide .widget-erp {
  grid-column: span 3;
}

.dashboard-grid.grid-wide .widget-crowding {
  grid-column: span 4;
}

/* Row 2: Style Strength (6 cols) + Gainers (3 cols) + Losers (3 cols) */
.dashboard-grid.grid-wide .widget-style {
  grid-column: span 6;
}

.dashboard-grid.grid-wide .widget-gainers {
  grid-column: span 3;
}

.dashboard-grid.grid-wide .widget-losers {
  grid-column: span 3;
}

/* Card Styles */
.card {
  background-color: var(--bg-card);
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  padding: 16px;
  transition: all 0.25s ease;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 51, 153, 0.12);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.card-subtitle {
  font-size: 12px;
  color: var(--text-muted);
}

.card-actions {
  display: flex;
  gap: 8px;
}

/* Widget Specific Styles */
.widget-fear-greed {
  border: 2px solid var(--brand-navy-dark);
  transition: all 0.25s ease;
}

.widget-erp {
  border: 2px solid var(--brand-navy-dark);
  transition: all 0.25s ease;
}

.widget-fear-greed:hover,
.widget-erp:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 51, 153, 0.12);
}

.widget-content {
  margin-bottom: 12px;
}

.gauge-container {
  display: flex;
  justify-content: center;
}

.history-chart {
  margin-top: 8px;
}

.factor-breakdown {
  display: flex;
  justify-content: space-around;
  padding-top: 12px;
  border-top: 1px solid var(--border-line);
}

.factor-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.factor-label {
  font-size: 11px;
  color: var(--text-muted);
}

.factor-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

/* Risk Warning */
.risk-warning {
  font-size: 11px;
  color: var(--text-muted);
  padding: 8px;
  background: var(--bg-system);
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
}

/* ERP Details */
.erp-details {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--border-line);
}

.detail-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.detail-label {
  font-size: 11px;
  color: var(--text-muted);
}

.detail-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

/* Crowding Legend */
.crowding-legend {
  display: flex;
  justify-content: center;
  gap: 16px;
  padding-top: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.legend-dot.low {
  background: var(--market-down);
}

.legend-dot.mid {
  background: #FFD700;
}

.legend-dot.high {
  background: var(--market-up);
}

/* Gainers/Losers Tables */
.widget-gainers,
.widget-losers {
  /* Grid span handled by responsive grid classes */
}

/* Heatmap Card */
.heatmap-card {
  margin-bottom: 16px;
}

/* Sector Card */
.sector-card {
  margin-bottom: 16px;
}

/* Word Cloud Card */
.word-cloud-card {
  margin-bottom: 16px;
}

/* Mobile: Hide word cloud to save vertical space */
.mobile-hidden {
  display: none;
}

.sector-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}

.sector-item {
  padding: 12px;
  background: var(--bg-system);
  border-radius: 4px;
  text-align: center;
  transition: transform 0.2s;
}

.sector-item:hover {
  transform: translateY(-2px);
}

.sector-name {
  font-size: 13px;
  color: var(--text-regular);
  margin-bottom: 4px;
}

.sector-change {
  font-size: 16px;
  font-weight: 600;
}

/* Mobile Sector Collapse (Accordion) */
.sector-collapse {
  border: none;
}

.sector-collapse :deep(.el-collapse-item__header) {
  background: var(--bg-system);
  border-radius: 4px;
  margin-bottom: 8px;
  padding: 0 16px;
  height: 48px;
  line-height: 48px;
  border: 1px solid var(--border-color-light);
  font-size: 14px;
  transition: all 0.3s;
}

.sector-collapse :deep(.el-collapse-item__header:hover) {
  background: var(--bg-system-hover);
}

.sector-collapse :deep(.el-collapse-item__header.is-active) {
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
  margin-bottom: 0;
  border-bottom: none;
}

.sector-collapse :deep(.el-collapse-item__wrap) {
  background: var(--bg-system);
  border-radius: 0 0 4px 4px;
  margin-bottom: 8px;
  border: 1px solid var(--border-color-light);
  border-top: none;
}

.sector-collapse :deep(.el-collapse-item__content) {
  padding: 12px 16px;
}

.sector-collapse-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.sector-collapse-title .sector-name {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 0;
}

.sector-collapse-title .sector-change {
  font-size: 15px;
  font-weight: 600;
}

.sector-collapse-content {
  padding-top: 4px;
}

.sector-detail {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
}

.sector-detail .detail-label {
  font-size: 13px;
  color: var(--text-muted);
}

.sector-detail .detail-value {
  font-size: 15px;
  font-weight: 600;
}

.sector-empty {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
}

/* Table Overrides */
:deep(.el-table) {
  font-size: 12px;
}

:deep(.el-table th) {
  background-color: #fafafa;
  font-weight: 600;
}

:deep(.el-table .cell) {
  padding: 0 8px;
}

/* Responsive Fund Cards - Mobile Layout */
.fund-cards-mobile {
  display: grid;
  gap: 12px;
  padding: 0 8px;
  max-height: 300px;
  overflow-y: auto;
  overscroll-behavior-y: contain;
}

/* Mobile (480-768px): Show 3 fields (code, name, type, return) */
.fund-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: 16px;
  min-height: 44px; /* WCAG touch target */
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.2s ease;
}

.fund-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: var(--primary);
}

.fund-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 44px; /* WCAG touch target */
}

.fund-code {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.fund-return {
  font-size: 16px;
  font-weight: 700;
  font-family: var(--font-mono);
}

.fund-name {
  font-size: 13px;
  color: var(--text-regular);
  line-height: 1.4;
  word-break: break-word;
}

.fund-type {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: 4px 8px;
  border-radius: var(--radius-xs);
  display: inline-block;
}

/* XS (320-480px): Simplified cards - only code + name + return */
@media (max-width: 480px) {
  .fund-card {
    padding: 12px;
    gap: 6px;
  }
  
  .fund-header {
    min-height: 44px;
  }
  
  .fund-code {
    font-size: 13px;
  }
  
  .fund-return {
    font-size: 15px;
  }
  
  .fund-name {
    font-size: 12px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 320px;
  }
}

/* Desktop (>768px): Sticky first column with scroll indicators */
.table-container {
  position: relative;
  overflow-x: auto;
  overscroll-behavior-x: contain;
  max-height: 300px;
}

/* Sticky column for desktop table */
:deep(.el-table .sticky-column) {
  position: sticky !important;
  left: 0 !important;
  z-index: var(--z-sticky, 10) !important;
  background: var(--bg-card) !important;
}

/* Gradient mask on sticky column edge */
:deep(.el-table .sticky-column::before) {
  content: '';
  position: absolute;
  right: -4px;
  top: 0;
  height: 100%;
  width: 20px;
  background: linear-gradient(to left, transparent 0%, var(--bg-card) 100%);
  pointer-events: none;
  z-index: calc(var(--z-sticky, 10) - 1);
}

/* Shadow effect on sticky column */
:deep(.el-table .sticky-column::after) {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  height: 100%;
  width: 8px;
  background: transparent;
  box-shadow: 4px 0 12px rgba(0, 0, 0, 0.15);
  pointer-events: none;
}

/* Scroll indicators with gradient masks */
.scroll-indicator {
  position: absolute;
  top: 0;
  height: 100%;
  z-index: var(--z-sticky, 10);
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.scroll-indicator-left {
  left: 0;
  width: 48px;
  background: linear-gradient(to right, var(--bg-card) 0%, var(--bg-card) 20%, transparent 100%);
}

.scroll-indicator-right {
  right: 0;
  width: 48px;
  background: linear-gradient(to left, var(--bg-card) 0%, var(--bg-card) 20%, transparent 100%);
}

/* Dark mode adjustments */
:root.dark .fund-card {
  background: var(--bg-card);
  border-color: var(--border-light);
}

:root.dark .fund-card:hover {
  border-color: var(--primary);
}

:root.dark :deep(.el-table .sticky-column) {
  background: var(--bg-card) !important;
}

:root.dark :deep(.el-table .sticky-column::before) {
  background: linear-gradient(to left, transparent 0%, var(--bg-card) 100%);
}

:root.dark :deep(.el-table .sticky-column::after) {
  box-shadow: 4px 0 12px rgba(0, 0, 0, 0.4);
}

:root.dark .scroll-indicator-left,
:root.dark .scroll-indicator-right {
  background: linear-gradient(to right, var(--bg-card) 0%, var(--bg-card) 20%, transparent 100%);
}
</style>