<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import type { EChartsOption } from 'echarts'
import { getFearGreedIndex, getERPSpread, getCrowdingAnalysis, getStyleStrength } from '@/api/analytics'
import { getIndices, getMarketHeatmap } from '@/api/market'
import { filterFunds, type FundItem, type FundFilterParams } from '@/api/fund'

// Loading states
const loading = ref(true)
const indicesLoading = ref(false)
const gainersLoading = ref(false)

// Real-time data refresh interval
let refreshInterval: ReturnType<typeof setInterval> | null = null
const REFRESH_INTERVAL = 30000 // 30 seconds

// Index quotes data
interface IndexQuote {
  name: string
  price: number
  change: number
  change_pct: number
}
const indexQuotes = ref<Record<string, IndexQuote>>({})

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
        formatter: '{value}',
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
      pointer: { length: '70%', width: 6 },
      detail: { 
        valueAnimation: true, 
        fontSize: 20, 
        offsetCenter: [0, '65%'],
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
      formatter: (params: { data: number[] }) => {
        return `${params.data[2]}<br/>PE分位: ${params.data[0].toFixed(1)}%<br/>拥挤度: ${params.data[1].toFixed(2)}`
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
  }
})

// Style strength chart
const styleStrengthOption = computed<EChartsOption>(() => {
  if (styleStrengthData.value.length === 0) return {}
  
  const latest = styleStrengthData.value[0]
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
  tooltip: { position: 'top' },
  grid: { top: 10, left: 100, right: 10, bottom: 30 },
  xAxis: { type: 'category', data: [], splitArea: { show: true } },
  yAxis: { type: 'category', data: [], splitArea: { show: true } },
  visualMap: {
    min: -10,
    max: 10,
    calculable: true,
    orient: 'horizontal',
    left: 'center',
    bottom: 0,
    inRange: {
      color: ['#2E7D32', '#FFFFFF', '#E63935'],
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
})

// Fetch all data
const fetchAllData = async () => {
  loading.value = true
  try {
    await Promise.all([
      fetchIndices(),
      fetchFearGreed(),
      fetchERP(),
      fetchCrowding(),
      fetchStyleStrength(),
      fetchHeatmap(),
      fetchTopFunds()
    ])
  } catch (error) {
    console.error('Dashboard load error:', error)
    ElMessage.error('数据加载失败，请刷新重试')
  } finally {
    loading.value = false
  }
}

// Fetch index quotes
const fetchIndices = async () => {
  indicesLoading.value = true
  try {
    indexQuotes.value = await getIndices()
  } catch (error) {
    console.error('Failed to fetch indices:', error)
  } finally {
    indicesLoading.value = false
  }
}

// Fetch fear/greed data
const fetchFearGreed = async () => {
  try {
    const data = await getFearGreedIndex()
    if (data.length > 0) {
      fearGreedData.value = data[0]
      fearGreedHistory.value = data.slice(0, 30)
    }
  } catch (error) {
    console.error('Failed to fetch fear/greed:', error)
  }
}

// Fetch ERP spread
const fetchERP = async () => {
  try {
    const data = await getERPSpread()
    if (data.length > 0) {
      erpData.value = data[0]
    }
  } catch (error) {
    console.error('Failed to fetch ERP:', error)
  }
}

// Fetch crowding analysis
const fetchCrowding = async () => {
  try {
    crowdingData.value = await getCrowdingAnalysis()
  } catch (error) {
    console.error('Failed to fetch crowding:', error)
  }
}

// Fetch style strength
const fetchStyleStrength = async () => {
  try {
    styleStrengthData.value = await getStyleStrength()
  } catch (error) {
    console.error('Failed to fetch style strength:', error)
  }
}

// Fetch heatmap
const fetchHeatmap = async () => {
  try {
    const heatmap = await getMarketHeatmap()
    if (heatmap.rows && heatmap.cols) {
      heatmapOption.value.xAxis!.data = heatmap.cols
      heatmapOption.value.yAxis!.data = heatmap.rows
      heatmapOption.value.series![0].data = heatmap.cells.map(c => [c.col, c.row, c.value])
    }
  } catch (error) {
    console.error('Failed to fetch heatmap:', error)
  }
}

// Fetch top gainers/losers
const fetchTopFunds = async () => {
  gainersLoading.value = true
  try {
    const [gainers, losers] = await Promise.all([
      filterFunds({ page: 1, page_size: 10, sort_by: 'return_1y', sort_order: 'desc' } as FundFilterParams),
      filterFunds({ page: 1, page_size: 10, sort_by: 'return_1y', sort_order: 'asc' } as FundFilterParams)
    ])
    topGainers.value = gainers.funds
    topLosers.value = losers.funds
  } catch (error) {
    console.error('Failed to fetch top funds:', error)
  } finally {
    gainersLoading.value = false
  }
}

// Format helpers
const formatNumber = (val: number | null, suffix = ''): string => {
  if (val === null || val === undefined) return '-'
  return `${val.toFixed(2)}${suffix}`
}

const formatChange = (val: number): string => {
  const sign = val >= 0 ? '+' : ''
  return `${sign}${val.toFixed(2)}%`
}

const getValueClass = (val: number | null): string => {
  if (val === null) return ''
  return val >= 0 ? 'text-up' : 'text-down'
}

// Quick actions
const handleQuickAction = (action: string) => {
  ElMessage.info(`执行快捷操作: ${action}`)
}

// Lifecycle
onMounted(() => {
  fetchAllData()
  
  // Set up real-time refresh
  refreshInterval = setInterval(() => {
    fetchIndices()
  }, REFRESH_INTERVAL)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
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
        
        <!-- Actual data when loaded -->
        <template v-else>
          <div 
            v-for="(quote, code) in indexQuotes" 
            :key="code" 
            class="index-item"
          >
            <div class="index-name">{{ quote.name }}</div>
            <div class="index-price">{{ quote.price.toFixed(2) }}</div>
            <div class="index-change" :class="getValueClass(quote.change)">
              {{ formatChange(quote.change_pct) }}
            </div>
          </div>
          <div v-if="Object.keys(indexQuotes).length === 0" class="index-empty">
            暂无行情数据
          </div>
        </template>
      </div>
    </div>

    <!-- Page Title -->
    <h1 class="page-title">首页宏观复盘看板</h1>

    <!-- Quick Actions -->
    <div class="quick-actions">
      <el-button size="small" @click="handleQuickAction('refresh')">
        刷新数据
      </el-button>
      <el-button size="small" @click="handleQuickAction('export')">
        导出报告
      </el-button>
      <el-button size="small" @click="handleQuickAction('settings')">
        看板设置
      </el-button>
    </div>

    <!-- Main Grid -->
    <div class="dashboard-grid">
      <!-- Fear/Greed Index Widget -->
      <div class="card widget-fear-greed">
        <div class="card-header">
          <div class="card-title">恐惧贪婪指数</div>
          <div class="card-subtitle" v-if="fearGreedData && !loading">
            {{ fearGreedData.trade_date }}
          </div>
        </div>
        
        <!-- Skeleton when loading -->
        <template v-if="loading">
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
              <span class="factor-label">波动率</span>
              <span class="factor-value">{{ formatNumber(fearGreedData.factor_volatility) }}</span>
            </div>
            <div class="factor-item">
              <span class="factor-label">避险情绪</span>
              <span class="factor-value">{{ formatNumber(fearGreedData.factor_safe_haven) }}</span>
            </div>
            <div class="factor-item">
              <span class="factor-label">杠杆水平</span>
              <span class="factor-value">{{ formatNumber(fearGreedData.factor_margin_ratio) }}</span>
            </div>
          </div>
        </template>
      </div>

      <!-- ERP Spread Widget -->
      <div class="card widget-erp">
        <div class="card-header">
          <div class="card-title">股债性价比 (ERP)</div>
          <div class="card-subtitle" v-if="erpData && !loading">
            {{ erpData.index_name }} | {{ erpData.trade_date }}
          </div>
        </div>
        
        <!-- Skeleton when loading -->
        <template v-if="loading">
          <div class="widget-content">
            <SkeletonLoader variant="gauge" height="220px" />
          </div>
        </template>
        
        <!-- Actual content when loaded -->
        <template v-else>
          <div class="widget-content">
            <EChartsWrapper
              :option="erpOption"
              height="220px"
            />
          </div>
          <div class="erp-details" v-if="erpData">
            <div class="detail-row">
              <span class="detail-label">PE(TTM)</span>
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
        </template>
      </div>

      <!-- Market Crowding Widget -->
      <div class="card widget-crowding">
        <div class="card-header">
          <div class="card-title">市场拥挤度</div>
          <div class="card-subtitle">行业/板块拥挤度分布</div>
        </div>
        
        <!-- Skeleton when loading -->
        <template v-if="loading">
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
      </div>

      <!-- Style Strength Widget -->
      <div class="card widget-style">
        <div class="card-header">
          <div class="card-title">风格强度</div>
          <div class="card-subtitle">大小盘/价值成长轮动</div>
        </div>
        
        <!-- Skeleton when loading -->
        <template v-if="loading">
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
      </div>

      <!-- Top Gainers Table -->
      <div class="card widget-gainers">
        <div class="card-header">
          <div class="card-title">涨幅榜 TOP10</div>
          <el-tag size="small" type="danger">近1年</el-tag>
        </div>
        
        <!-- Skeleton when loading -->
        <SkeletonLoader
          v-if="gainersLoading"
          variant="table"
          :rows="10"
          :columns="4"
        />
        
        <!-- Actual table when loaded -->
        <el-table
          v-else
          :data="topGainers"
          size="small"
          max-height="300"
        >
          <el-table-column prop="fund_code" label="代码" width="80" />
          <el-table-column prop="fund_name" label="名称" min-width="120" show-overflow-tooltip />
          <el-table-column prop="fund_type" label="类型" width="80" />
          <el-table-column prop="return_1y" label="收益%" width="90" sortable>
            <template #default="{ row }">
              <span class="text-up">{{ formatNumber(row.return_1y) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- Top Losers Table -->
      <div class="card widget-losers">
        <div class="card-header">
          <div class="card-title">跌幅榜 TOP10</div>
          <el-tag size="small" type="success">近1年</el-tag>
        </div>
        
        <!-- Skeleton when loading -->
        <SkeletonLoader
          v-if="gainersLoading"
          variant="table"
          :rows="10"
          :columns="4"
        />
        
        <!-- Actual table when loaded -->
        <el-table
          v-else
          :data="topLosers"
          size="small"
          max-height="300"
        >
          <el-table-column prop="fund_code" label="代码" width="80" />
          <el-table-column prop="fund_name" label="名称" min-width="120" show-overflow-tooltip />
          <el-table-column prop="fund_type" label="类型" width="80" />
          <el-table-column prop="return_1y" label="收益%" width="90" sortable>
            <template #default="{ row }">
              <span class="text-down">{{ formatNumber(row.return_1y) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- Heatmap Section -->
    <div class="card heatmap-card">
      <div class="card-header">
        <div class="card-title">多周期热力矩阵</div>
        <div class="card-subtitle">行业/指数多周期涨跌分布</div>
      </div>
      
      <!-- Skeleton when loading -->
      <SkeletonLoader
        v-if="loading"
        variant="heatmap"
        height="400px"
      />
      
      <!-- Actual chart when loaded -->
      <EChartsWrapper
        v-else
        :option="heatmapOption"
        height="400px"
      />
    </div>

    <!-- Sector Performance Overview -->
    <div class="card sector-card">
      <div class="card-header">
        <div class="card-title">板块表现概览</div>
        <div class="card-actions">
          <el-radio-group size="small">
            <el-radio-button label="今日" />
            <el-radio-button label="近5日" />
            <el-radio-button label="近20日" />
          </el-radio-group>
        </div>
      </div>
      <div class="sector-grid">
        <div 
          v-for="sector in sectorPerformance" 
          :key="sector.name"
          class="sector-item"
          :class="getValueClass(sector.change_pct)"
        >
          <div class="sector-name">{{ sector.name }}</div>
          <div class="sector-change">{{ formatChange(sector.change_pct) }}</div>
        </div>
        <div v-if="sectorPerformance.length === 0" class="sector-empty">
          暂无板块数据
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  padding: 0;
}

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

/* Page Title */
.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
}

/* Quick Actions */
.quick-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

/* Dashboard Grid */
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

@media (max-width: 1400px) {
  .dashboard-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

/* Card Styles */
.card {
  background-color: var(--bg-card);
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  padding: 16px;
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
  grid-column: span 2;
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
  grid-column: span 1;
}

/* Heatmap Card */
.heatmap-card {
  margin-bottom: 16px;
}

/* Sector Card */
.sector-card {
  margin-bottom: 16px;
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
</style>