<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import type { EChartsOption } from 'echarts'
import { getDomesticMarket } from '@/api/market'

// Types
interface IndexData {
  code: string
  name: string
  price: number
  change: number
  change_pct: number
  volume: number
  amount: number
  pe: number
  pb: number
}

interface MarketBreadth {
  advancing: number
  declining: number
  unchanged: number
  limit_up: number
  limit_down: number
  total_amount: number
  turnover_rate: number
}

interface SectorData {
  name: string
  code: string
  change_pct: number
  leading_stock: string
  leading_change: number
}

interface CapitalFlow {
  date: string
  north_inflow: number
  south_inflow: number
  north_accumulated: number
  south_accumulated: number
}

// State
const loading = ref(true)
const lastUpdate = ref<string>('')
const indices = ref<IndexData[]>([])
const marketBreadth = ref<MarketBreadth | null>(null)
const sectors = ref<SectorData[]>([])
const capitalFlow = ref<CapitalFlow[]>([])

// Major A-share indices configuration
const majorIndices = [
  { code: '000001', name: '上证指数' },
  { code: '399001', name: '深证成指' },
  { code: '399006', name: '创业板指' },
  { code: '000688', name: '科创50' },
  { code: '000300', name: '沪深300' },
  { code: '000905', name: '中证500' },
  { code: '000852', name: '中证1000' },
]

// 30 Industry sectors (SW Level 1)
const industrySectors = [
  '银行', '非银金融', '房地产', '建筑装饰', '建筑材料',
  '钢铁', '采掘', '有色金属', '化工', '石油石化',
  '机械设备', '电气设备', '国防军工', '汽车', '家用电器',
  '轻工制造', '纺织服饰', '商贸零售', '消费者服务', '食品饮料',
  '农林牧渔', '医药生物', '电子', '计算机', '通信',
  '传媒', '公用事业', '交通运输', '环保', '综合',
]

// Sector heatmap chart option
const heatmapOption = ref<EChartsOption>({
  tooltip: {
    position: 'top',
    formatter: (params: unknown) => {
      const p = params as { data: [string, string, number] }
      if (!p || !p.data) return ''
      const [sector, , value] = p.data
      const sign = value >= 0 ? '+' : ''
      return `<div style="font-weight:600;">${sector}</div>
              <div style="color:${value >= 0 ? '#E63935' : '#2E7D32'};">
                涨跌幅: ${sign}${value.toFixed(2)}%
              </div>`
    },
  },
  grid: {
    top: 10,
    left: 10,
    right: 10,
    bottom: 10,
    containLabel: true,
  },
  xAxis: {
    type: 'category',
    data: ['1', '2', '3', '4', '5', '6'],
    splitArea: { show: true },
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { show: false },
  },
  yAxis: {
    type: 'category',
    data: ['1', '2', '3', '4', '5'],
    splitArea: { show: true },
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { show: false },
  },
  visualMap: {
    min: -5,
    max: 5,
    calculable: false,
    orient: 'horizontal',
    left: 'center',
    bottom: 0,
    show: false,
    inRange: {
      color: ['#2E7D32', '#4CAF50', '#81C784', '#E8F5E9', 
              '#FFFFFF', '#FFEBEE', '#EF9A9A', '#E57373', '#E63935'],
    },
  },
  series: [{
    type: 'heatmap',
    data: [],
    label: {
      show: true,
      formatter: (params: unknown) => {
        const p = params as { data: [string, string, number, string] }
        if (!p || !p.data) return ''
        const [sector, , value] = p.data
        const sign = value >= 0 ? '+' : ''
        return `{name|${sector}}\n{value|${sign}${value.toFixed(2)}%}`
      },
      rich: {
        name: {
          fontSize: 12,
          color: '#1A1A1A',
          fontWeight: 500,
          lineHeight: 18,
        },
        value: {
          fontSize: 14,
          fontWeight: 700,
          lineHeight: 20,
        },
      },
    },
    itemStyle: {
      borderColor: '#fff',
      borderWidth: 2,
      borderRadius: 4,
    },
    emphasis: {
      itemStyle: {
        shadowBlur: 10,
        shadowColor: 'rgba(0, 0, 0, 0.3)',
      },
    },
  }],
})

// North/South bound capital flow chart option
const capitalFlowOption = ref<EChartsOption>({
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (params: unknown) => {
      const items = params as Array<{ axisValue: string; seriesName: string; value: number; color: string }>
      if (!items || items.length === 0) return ''
      let html = `<div style="font-weight:600;margin-bottom:8px;">${items[0].axisValue}</div>`
      items.forEach(item => {
        const sign = item.value >= 0 ? '+' : ''
        html += `<div style="display:flex;justify-content:space-between;gap:20px;">
          <span>${item.seriesName}</span>
          <span style="color:${item.color};font-weight:600;">${sign}${(item.value / 100).toFixed(2)}亿</span>
        </div>`
      })
      return html
    },
  },
  legend: {
    data: ['北向资金', '南向资金'],
    top: 0,
    textStyle: { color: '#4A4A4A' },
  },
  grid: {
    top: 40,
    left: 60,
    right: 20,
    bottom: 40,
  },
  xAxis: {
    type: 'category',
    data: [],
    axisLabel: {
      fontSize: 11,
      color: '#4A4A4A',
      rotate: 30,
    },
    axisLine: { lineStyle: { color: '#E5E8ED' } },
    axisTick: { show: false },
  },
  yAxis: {
    type: 'value',
    name: '亿元',
    nameTextStyle: { color: '#999999', fontSize: 12 },
    axisLabel: {
      formatter: (val: number) => (val / 100).toFixed(0),
      color: '#4A4A4A',
    },
    axisLine: { show: false },
    splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } },
  },
  series: [
    {
      name: '北向资金',
      type: 'bar',
      data: [],
      barWidth: '35%',
      itemStyle: {
        color: (params: { value: number }) => params.value >= 0 ? '#E63935' : '#2E7D32',
        borderRadius: [4, 4, 0, 0],
      },
    },
    {
      name: '南向资金',
      type: 'bar',
      data: [],
      barWidth: '35%',
      itemStyle: {
        color: (params: { value: number }) => params.value >= 0 ? '#E63935' : '#2E7D32',
        borderRadius: [4, 4, 0, 0],
      },
    },
  ],
})

// Format helpers
const formatNumber = (val: number | null | undefined, decimals = 2): string => {
  if (val === null || val === undefined) return '-'
  return val.toFixed(decimals)
}

const formatChange = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return '-'
  const sign = val >= 0 ? '+' : ''
  return `${sign}${val.toFixed(2)}`
}

const formatPercent = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return '-'
  const sign = val >= 0 ? '+' : ''
  return `${sign}${val.toFixed(2)}%`
}

const formatAmount = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return '-'
  if (val >= 100000000) {
    return (val / 100000000).toFixed(2) + '万亿'
  }
  if (val >= 10000) {
    return (val / 10000).toFixed(2) + '亿'
  }
  return val.toFixed(2) + '万'
}

const getValueClass = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return 'text-flat'
  if (val > 0) return 'text-up'
  if (val < 0) return 'text-down'
  return 'text-flat'
}

// Computed: advancing/declining ratio
const advanceDeclineRatio = computed(() => {
  if (!marketBreadth.value) return '-'
  const { advancing, declining } = marketBreadth.value
  if (declining === 0) return advancing > 0 ? '∞' : '-'
  return (advancing / declining).toFixed(2)
})

// Computed: market sentiment
const marketSentiment = computed(() => {
  if (!marketBreadth.value) return { text: '-', class: 'text-flat' }
  const { advancing, declining, total_amount } = marketBreadth.value
  const ratio = declining > 0 ? advancing / declining : (advancing > 0 ? 10 : 0)
  
  if (ratio >= 2 && total_amount > 800000000000) {
    return { text: '强势', class: 'text-up' }
  } else if (ratio >= 1.5) {
    return { text: '偏强', class: 'text-up' }
  } else if (ratio <= 0.5) {
    return { text: '弱势', class: 'text-down' }
  } else if (ratio <= 0.67) {
    return { text: '偏弱', class: 'text-down' }
  }
  return { text: '均衡', class: 'text-flat' }
})

// Fetch market data
const fetchMarketData = async () => {
  loading.value = true
  try {
    const response = await getDomesticMarket()
    
    // Map indices data - API returns limited fields, add defaults for pe/pb/volume/amount
    indices.value = response.indices.map(idx => ({
      code: idx.code,
      name: idx.name,
      price: idx.price,
      change: idx.price * idx.change_pct / 100, // Calculate absolute change
      change_pct: idx.change_pct,
      volume: 0, // Not provided by API
      amount: 0, // Not provided by API
      pe: 0, // Not provided by API
      pb: 0, // Not provided by API
    }))
    
    // Map market breadth data
    marketBreadth.value = {
      advancing: response.market_breadth.advancing,
      declining: response.market_breadth.declining,
      unchanged: response.market_breadth.unchanged,
      limit_up: response.market_breadth.limit_up,
      limit_down: response.market_breadth.limit_down,
      total_amount: response.volume.total_turnover,
      turnover_rate: response.volume.turnover_rate,
    }
    
    // Map sector data - API returns limited fields, add defaults for code/leading_stock/leading_change
    sectors.value = response.sectors.map((sector, idx) => ({
      name: sector.name,
      code: `SW${idx.toString().padStart(2, '0')}`,
      change_pct: sector.change_pct,
      leading_stock: '-', // Not provided by API
      leading_change: 0, // Not provided by API
    }))
    
    // Map capital flow data - API returns single day, use empty array for chart
    capitalFlow.value = []
    
    // Update charts
    updateHeatmapChart()
    updateCapitalFlowChart()
    
    // Set last update time from API
    lastUpdate.value = response.update_time
    
  } catch (error) {
    ElMessage.error('获取市场数据失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// Update heatmap chart
const updateHeatmapChart = () => {
  const data: [string, string, number, string][] = []
  const sortedSectors = [...sectors.value].sort((a, b) => b.change_pct - a.change_pct)
  
  sortedSectors.forEach((sector, idx) => {
    const col = idx % 6
    const row = Math.floor(idx / 6)
    data.push([col.toString(), row.toString(), sector.change_pct, sector.name])
  })
  
  heatmapOption.value.series![0].data = data
  
  // Update visual map range based on data
  const changes = sectors.value.map(s => s.change_pct)
  const minVal = Math.min(...changes, -3)
  const maxVal = Math.max(...changes, 3)
  heatmapOption.value.visualMap!.min = minVal
  heatmapOption.value.visualMap!.max = maxVal
}

// Update capital flow chart
const updateCapitalFlowChart = () => {
  capitalFlowOption.value.xAxis!.data = capitalFlow.value.map(d => d.date)
  capitalFlowOption.value.series![0].data = capitalFlow.value.map(d => d.north_inflow)
  capitalFlowOption.value.series![1].data = capitalFlow.value.map(d => d.south_inflow)
}

// Auto refresh timer
let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchMarketData()
  
  // Auto refresh every 60 seconds
  refreshTimer = setInterval(() => {
    fetchMarketData()
  }, 60000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<template>
  <div class="domestic-stock-market">
    <!-- Header -->
    <div class="page-header">
      <h1 class="page-title">国内股票市场总览</h1>
      <div class="header-info">
        <span class="update-time" v-if="lastUpdate">
          <el-icon><i-ep-Clock /></el-icon>
          最后更新: {{ lastUpdate }}
        </span>
        <el-button 
          type="primary" 
          size="small" 
          :loading="loading"
          @click="fetchMarketData"
        >
          <el-icon><i-ep-Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>
    
    <!-- Major Indices Section -->
    <div class="section">
      <div class="section-header">
        <h2 class="section-title">主要指数</h2>
        <span class="section-subtitle">实时行情</span>
      </div>
      
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
            <span class="index-code">{{ idx.code }}</span>
          </div>
          <div class="index-price">{{ formatNumber(idx.price) }}</div>
          <div class="index-change" :class="getValueClass(idx.change_pct)">
            <span class="change-value">{{ formatChange(idx.change) }}</span>
            <span class="change-percent">{{ formatPercent(idx.change_pct) }}</span>
          </div>
          <div class="index-meta">
            <div class="meta-item">
              <span class="meta-label">PE</span>
              <span class="meta-value">{{ formatNumber(idx.pe) }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">PB</span>
              <span class="meta-value">{{ formatNumber(idx.pb) }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">成交额</span>
              <span class="meta-value">{{ formatAmount(idx.amount) }}</span>
            </div>
          </div>
        </el-card>
      </div>
    </div>
    
    <!-- Market Breadth Section -->
    <div class="section">
      <div class="section-header">
        <h2 class="section-title">市场广度</h2>
        <span class="section-subtitle">涨跌统计</span>
      </div>
      
      <div class="breadth-grid">
        <el-card class="breadth-card" shadow="never">
          <div class="breadth-content">
            <div class="breadth-row">
              <div class="breadth-item">
                <div class="breadth-label">上涨</div>
                <div class="breadth-value text-up">{{ marketBreadth?.advancing ?? '-' }}</div>
              </div>
              <div class="breadth-divider"></div>
              <div class="breadth-item">
                <div class="breadth-label">下跌</div>
                <div class="breadth-value text-down">{{ marketBreadth?.declining ?? '-' }}</div>
              </div>
              <div class="breadth-divider"></div>
              <div class="breadth-item">
                <div class="breadth-label">平盘</div>
                <div class="breadth-value text-flat">{{ marketBreadth?.unchanged ?? '-' }}</div>
              </div>
            </div>
            <div class="breadth-row">
              <div class="breadth-item">
                <div class="breadth-label">涨停</div>
                <div class="breadth-value text-up">{{ marketBreadth?.limit_up ?? '-' }}</div>
              </div>
              <div class="breadth-divider"></div>
              <div class="breadth-item">
                <div class="breadth-label">跌停</div>
                <div class="breadth-value text-down">{{ marketBreadth?.limit_down ?? '-' }}</div>
              </div>
            </div>
          </div>
        </el-card>
        
        <el-card class="breadth-card" shadow="never">
          <div class="breadth-content">
            <div class="breadth-row single">
              <div class="breadth-item large">
                <div class="breadth-label">涨跌比</div>
                <div class="breadth-value" :class="parseFloat(advanceDeclineRatio) >= 1 ? 'text-up' : 'text-down'">
                  {{ advanceDeclineRatio }}
                </div>
              </div>
            </div>
            <div class="breadth-row single">
              <div class="breadth-item large">
                <div class="breadth-label">市场情绪</div>
                <div class="breadth-value" :class="marketSentiment.class">
                  {{ marketSentiment.text }}
                </div>
              </div>
            </div>
          </div>
        </el-card>
        
        <el-card class="breadth-card" shadow="never">
          <div class="breadth-content">
            <div class="breadth-row single">
              <div class="breadth-item large">
                <div class="breadth-label">两市成交额</div>
                <div class="breadth-value">{{ formatAmount(marketBreadth?.total_amount) }}</div>
              </div>
            </div>
            <div class="breadth-row single">
              <div class="breadth-item large">
                <div class="breadth-label">换手率</div>
                <div class="breadth-value">{{ marketBreadth ? formatNumber(marketBreadth.turnover_rate) + '%' : '-' }}</div>
              </div>
            </div>
          </div>
        </el-card>
      </div>
    </div>
    
    <!-- Sector Heatmap Section -->
    <div class="section">
      <div class="section-header">
        <h2 class="section-title">行业板块热力图</h2>
        <span class="section-subtitle">申万一级行业 (30个)</span>
      </div>
      
      <el-card class="heatmap-card" shadow="never">
        <EChartsWrapper
          :option="heatmapOption"
          :loading="loading"
          height="380px"
        />
      </el-card>
    </div>
    
    <!-- Capital Flow Section -->
    <div class="section">
      <div class="section-header">
        <h2 class="section-title">南北向资金流向</h2>
        <span class="section-subtitle">近10个交易日</span>
      </div>
      
      <el-card class="capital-flow-card" shadow="never">
        <EChartsWrapper
          :option="capitalFlowOption"
          :loading="loading"
          height="320px"
        />
      </el-card>
    </div>
    
    <!-- Sector Performance Table -->
    <div class="section">
      <div class="section-header">
        <h2 class="section-title">行业涨跌排行</h2>
        <span class="section-subtitle">按涨跌幅排序</span>
      </div>
      
      <el-card class="table-card" shadow="never">
        <el-table 
          :data="sectors" 
          stripe 
          size="small"
          :default-sort="{ prop: 'change_pct', order: 'descending' }"
        >
          <el-table-column prop="name" label="行业" width="120" />
          <el-table-column prop="change_pct" label="涨跌幅" width="120" sortable>
            <template #default="{ row }">
              <span :class="getValueClass(row.change_pct)" class="change-cell">
                {{ formatPercent(row.change_pct) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="leading_stock" label="领涨股" min-width="120" />
          <el-table-column prop="leading_change" label="领涨股涨幅" width="120">
            <template #default="{ row }">
              <span :class="getValueClass(row.leading_change)" class="change-cell">
                {{ formatPercent(row.leading_change) }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.domestic-stock-market {
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
  grid-template-columns: repeat(7, 1fr);
  gap: 12px;
}

@media (max-width: 1400px) {
  .indices-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media (max-width: 992px) {
  .indices-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 576px) {
  .indices-grid {
    grid-template-columns: 1fr;
  }
}

.index-card {
  border-radius: 8px;
  transition: all 0.3s ease;
  cursor: pointer;
}

.index-card:hover {
  transform: translateY(-2px);
}

.index-card :deep(.el-card__body) {
  padding: 14px;
}

.index-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.index-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.index-code {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-system);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
}

.index-price {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 6px;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
}

.index-change {
  display: flex;
  gap: 10px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 10px;
}

.change-value,
.change-percent {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
}

.index-meta {
  display: flex;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-line);
}

.meta-item {
  flex: 1;
  text-align: center;
}

.meta-label {
  display: block;
  font-size: 10px;
  color: var(--text-muted);
  margin-bottom: 2px;
}

.meta-value {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-regular);
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
}

/* Market Breadth Grid */
.breadth-grid {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 16px;
}

@media (max-width: 992px) {
  .breadth-grid {
    grid-template-columns: 1fr;
  }
}

.breadth-card {
  border-radius: 8px;
}

.breadth-card :deep(.el-card__body) {
  padding: 16px;
}

.breadth-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.breadth-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.breadth-row.single {
  justify-content: center;
}

.breadth-item {
  flex: 1;
  text-align: center;
}

.breadth-item.large {
  flex: none;
  min-width: 120px;
}

.breadth-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.breadth-value {
  font-size: 20px;
  font-weight: 700;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
}

.breadth-divider {
  width: 1px;
  height: 40px;
  background: var(--border-line);
}

/* Heatmap Card */
.heatmap-card {
  border-radius: 8px;
}

.heatmap-card :deep(.el-card__body) {
  padding: 16px;
}

/* Capital Flow Card */
.capital-flow-card {
  border-radius: 8px;
}

.capital-flow-card :deep(.el-card__body) {
  padding: 16px;
}

/* Table Card */
.table-card {
  border-radius: 8px;
}

.table-card :deep(.el-card__body) {
  padding: 0;
}

.table-card :deep(.el-table) {
  --el-table-border-color: var(--border-line);
}

.table-card :deep(.el-table th) {
  background-color: #fafafa;
  font-weight: 600;
  color: var(--text-primary);
}

.change-cell {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Mono', monospace;
  font-weight: 600;
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
