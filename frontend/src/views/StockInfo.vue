<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import api from '@/api/index'

// Types
interface StockSearchResult {
  stock_code: string
  stock_name: string
}

interface StockQuote {
  stock_code: string
  stock_name: string
  price: number | null
  change: number | null
  change_percent: number | null
  volume: number | null
  turnover: number | null
  pe_ttm: number | null
  pb: number | null
  high: number | null
  low: number | null
  open: number | null
  pre_close: number | null
}

interface StockInfo {
  industry: string | null
  concept_sectors: string[]
  company_intro: string | null
}

interface KLineData {
  date: string
  open: number
  close: number
  high: number
  low: number
  volume: number
}

// State
const searchQuery = ref('')
const searchResults = ref<StockSearchResult[]>([])
const searchLoading = ref(false)
const selectedStock = ref<StockSearchResult | null>(null)
const stockQuote = ref<StockQuote | null>(null)
const stockInfo = ref<StockInfo | null>(null)
const klineData = ref<KLineData[]>([])
const quoteLoading = ref(false)
const klineLoading = ref(false)
const chartInstance = ref<echarts.ECharts | null>(null)
const chartContainer = ref<HTMLElement | null>(null)

// Debounce timer
let searchTimer: ReturnType<typeof setTimeout> | null = null

// Format helpers
const formatNumber = (val: number | null | undefined, decimals = 2): string => {
  if (val === null || val === undefined) return '-'
  return val.toFixed(decimals)
}

const formatVolume = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return '-'
  if (val >= 100000000) return `${(val / 100000000).toFixed(2)}亿`
  if (val >= 10000) return `${(val / 10000).toFixed(2)}万`
  return val.toString()
}

const formatTurnover = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return '-'
  if (val >= 100000000) return `${(val / 100000000).toFixed(2)}亿`
  if (val >= 10000) return `${(val / 10000).toFixed(2)}万`
  return val.toString()
}

const getValueClass = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return ''
  return val >= 0 ? 'text-up' : 'text-down'
}

// Fetch suggestions callback for autocomplete
const fetchSuggestions = (query: string, cb: (results: StockSearchResult[]) => void) => {
  cb(searchResults.value)
}

// Search with debounce
const handleSearch = (query: string) => {
  if (searchTimer) clearTimeout(searchTimer)
  
  if (!query || query.length < 1) {
    searchResults.value = []
    return
  }
  
  searchTimer = setTimeout(async () => {
    searchLoading.value = true
    try {
      const response = await api.get<{ results: StockSearchResult[] }>('/stock/search', {
        params: { keyword: query }
      })
      searchResults.value = response.results || []
    } catch (error) {
      searchResults.value = []
    } finally {
      searchLoading.value = false
    }
  }, 300)
}

// Select stock
const handleSelectStock = (stock: StockSearchResult) => {
  selectedStock.value = stock
  searchQuery.value = `${stock.stock_code} ${stock.stock_name}`
  searchResults.value = []
  fetchStockData()
}

// Fetch all stock data
const fetchStockData = async () => {
  if (!selectedStock.value) return
  
  const code = selectedStock.value.stock_code
  
  // Fetch quote, info, and kline in parallel
  quoteLoading.value = true
  klineLoading.value = true
  
  try {
    const [quoteRes, infoRes, klineRes] = await Promise.all([
      api.get<StockQuote>(`/stock/${code}/quote`),
      api.get<StockInfo>(`/stock/${code}/info`),
      api.get<{ data: KLineData[] }>(`/stock/${code}/kline`, {
        params: { period: 'daily', limit: 120 }
      })
    ])
    
    stockQuote.value = quoteRes
    stockInfo.value = infoRes
    klineData.value = klineRes.data || []
    
    // Render chart after data loaded
    await nextTick()
    renderKLineChart()
  } catch (error) {
    ElMessage.error('获取股票数据失败')
  } finally {
    quoteLoading.value = false
    klineLoading.value = false
  }
}

// Render K-line chart
const renderKLineChart = () => {
  if (!chartContainer.value || klineData.value.length === 0) return
  
  if (chartInstance.value) {
    chartInstance.value.dispose()
  }
  
  chartInstance.value = echarts.init(chartContainer.value)
  
  const dates = klineData.value.map(item => item.date)
  const ohlc = klineData.value.map(item => [item.open, item.close, item.low, item.high])
  const volumes = klineData.value.map(item => item.volume)
  
  const option: echarts.EChartsOption = {
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#E5E8ED',
      textStyle: { color: '#1A1A1A', fontSize: 12 },
      formatter: (params: unknown) => {
        const data = params as Array<{ seriesName: string; dataIndex: number; data: unknown }>
        const idx = data[0].dataIndex
        const k = klineData.value[idx]
        if (!k) return ''
        const change = k.close - k.open
        const changePercent = ((change / k.open) * 100).toFixed(2)
        const color = change >= 0 ? '#E63935' : '#2E7D32'
        return `
          <div style="padding: 4px 8px;">
            <div style="font-weight: 600; margin-bottom: 6px;">${k.date}</div>
            <div>开盘: ${k.open.toFixed(2)}</div>
            <div>收盘: <span style="color: ${color}">${k.close.toFixed(2)}</span></div>
            <div>最高: ${k.high.toFixed(2)}</div>
            <div>最低: ${k.low.toFixed(2)}</div>
            <div>涨跌: <span style="color: ${color}">${change >= 0 ? '+' : ''}${change.toFixed(2)} (${change >= 0 ? '+' : ''}${changePercent}%)</span></div>
            <div>成交量: ${formatVolume(k.volume)}</div>
          </div>
        `
      }
    },
    axisPointer: {
      link: [{ xAxisIndex: 'all' }]
    },
    grid: [
      { left: '8%', right: '3%', top: '5%', height: '55%' },
      { left: '8%', right: '3%', top: '68%', height: '18%' }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#E5E8ED' } },
        axisLabel: { color: '#999999', fontSize: 11 },
        splitLine: { show: false }
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#E5E8ED' } },
        axisLabel: { show: false },
        splitLine: { show: false }
      }
    ],
    yAxis: [
      {
        scale: true,
        axisLine: { lineStyle: { color: '#E5E8ED' } },
        axisLabel: { color: '#999999', fontSize: 11 },
        splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } }
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLine: { lineStyle: { color: '#E5E8ED' } },
        axisLabel: { 
          color: '#999999', 
          fontSize: 11,
          formatter: (val: number) => formatVolume(val)
        },
        splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } }
      }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        itemStyle: {
          color: '#E63935',
          color0: '#2E7D32',
          borderColor: '#E63935',
          borderColor0: '#2E7D32'
        }
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: {
          color: (params: { dataIndex: number }) => {
            const k = klineData.value[params.dataIndex]
            if (!k) return '#999999'
            return k.close >= k.open ? '#E63935' : '#2E7D32'
          }
        }
      }
    ]
  }
  
  chartInstance.value.setOption(option)
}

// Handle window resize
const handleResize = () => {
  chartInstance.value?.resize()
}

// Watch search query
watch(searchQuery, (val) => {
  handleSearch(val)
})

// Lifecycle
onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance.value?.dispose()
})
</script>

<template>
  <div class="stock-info">
    <!-- Search Section -->
    <div class="search-section">
      <div class="search-box">
        <el-autocomplete
          v-model="searchQuery"
          :fetch-suggestions="fetchSuggestions"
          placeholder="输入股票代码或名称搜索"
          :loading="searchLoading"
          clearable
          @select="handleSelectStock"
        >
          <template #default="{ item }">
            <div class="search-item">
              <span class="code">{{ item.stock_code }}</span>
              <span class="name">{{ item.stock_name }}</span>
            </div>
          </template>
        </el-autocomplete>
      </div>
    </div>
    
    <!-- Main Content -->
    <div v-if="selectedStock" class="content-container">
      <!-- Left: Quote & Info -->
      <div class="left-panel">
        <!-- Quote Card -->
        <div class="quote-card card">
          <div class="card-title">
            {{ stockQuote?.stock_name || selectedStock.stock_name }}
            <span class="stock-code">{{ stockQuote?.stock_code || selectedStock.stock_code }}</span>
          </div>
          
          <div v-if="quoteLoading" class="loading-state">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>加载中...</span>
          </div>
          
          <div v-else-if="stockQuote" class="quote-content">
            <!-- Price Section -->
            <div class="price-section">
              <div class="current-price" :class="getValueClass(stockQuote.change)">
                {{ formatNumber(stockQuote.price) }}
              </div>
              <div class="price-change">
                <span :class="getValueClass(stockQuote.change)">
                  {{ stockQuote.change !== null ? (stockQuote.change >= 0 ? '+' : '') + formatNumber(stockQuote.change) : '-' }}
                </span>
                <span class="change-percent" :class="getValueClass(stockQuote.change_percent)">
                  {{ stockQuote.change_percent !== null ? (stockQuote.change_percent >= 0 ? '+' : '') + formatNumber(stockQuote.change_percent) + '%' : '-' }}
                </span>
              </div>
            </div>
            
            <!-- Quote Details -->
            <div class="quote-details">
              <div class="detail-row">
                <div class="detail-item">
                  <span class="label">今开</span>
                  <span class="value">{{ formatNumber(stockQuote.open) }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">最高</span>
                  <span class="value text-up">{{ formatNumber(stockQuote.high) }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">最低</span>
                  <span class="value text-down">{{ formatNumber(stockQuote.low) }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">昨收</span>
                  <span class="value">{{ formatNumber(stockQuote.pre_close) }}</span>
                </div>
              </div>
              
              <div class="detail-row">
                <div class="detail-item">
                  <span class="label">成交量</span>
                  <span class="value">{{ formatVolume(stockQuote.volume) }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">成交额</span>
                  <span class="value">{{ formatTurnover(stockQuote.turnover) }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">市盈率TTM</span>
                  <span class="value">{{ formatNumber(stockQuote.pe_ttm) }}</span>
                </div>
                <div class="detail-item">
                  <span class="label">市净率</span>
                  <span class="value">{{ formatNumber(stockQuote.pb) }}</span>
                </div>
              </div>
            </div>
          </div>
          
          <div v-else class="empty-state">
            <span>暂无行情数据</span>
          </div>
        </div>
        
        <!-- Info Card -->
        <div class="info-card card">
          <div class="card-title">基本信息</div>
          
          <div v-if="stockInfo" class="info-content">
            <!-- Industry -->
            <div v-if="stockInfo.industry" class="info-item">
              <span class="label">所属行业</span>
              <el-tag size="small" type="info">{{ stockInfo.industry }}</el-tag>
            </div>
            
            <!-- Concept Sectors -->
            <div v-if="stockInfo.concept_sectors && stockInfo.concept_sectors.length > 0" class="info-item">
              <span class="label">概念板块</span>
              <div class="tag-group">
                <el-tag
                  v-for="sector in stockInfo.concept_sectors.slice(0, 10)"
                  :key="sector"
                  size="small"
                  type="success"
                >
                  {{ sector }}
                </el-tag>
                <span v-if="stockInfo.concept_sectors.length > 10" class="more-tag">
                  +{{ stockInfo.concept_sectors.length - 10 }}
                </span>
              </div>
            </div>
            
            <!-- Company Intro -->
            <div v-if="stockInfo.company_intro" class="info-item full-width">
              <span class="label">公司简介</span>
              <p class="intro-text">{{ stockInfo.company_intro }}</p>
            </div>
          </div>
          
          <div v-else class="empty-state">
            <span>暂无基本信息</span>
          </div>
        </div>
      </div>
      
      <!-- Right: K-Line Chart -->
      <div class="right-panel">
        <div class="chart-card card">
          <div class="card-title">日K线图</div>
          
          <div v-if="klineLoading" class="loading-state chart-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>加载中...</span>
          </div>
          
          <div
            v-else-if="klineData.length > 0"
            ref="chartContainer"
            class="chart-container"
          ></div>
          
          <div v-else class="empty-state chart-empty">
            <span>暂无K线数据</span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Empty State -->
    <div v-else class="empty-container">
      <div class="empty-content">
        <el-icon :size="64" color="var(--text-muted)"><Search /></el-icon>
        <p>输入股票代码或名称开始查询</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stock-info {
  height: calc(100vh - 100px); /* Fallback for older browsers */
  height: calc(100dvh - 100px);
  display: flex;
  flex-direction: column;
}

/* Search Section */
.search-section {
  margin-bottom: 16px;
}

.search-box {
  max-width: 400px;
}

.search-box :deep(.el-autocomplete) {
  width: 100%;
}

.search-item {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-item .code {
  font-family: 'SF Mono', Monaco, monospace;
  color: var(--text-primary);
  font-weight: 500;
}

.search-item .name {
  color: var(--text-regular);
}

/* Content Container */
.content-container {
  flex: 1;
  display: flex;
  gap: 16px;
  min-height: 0;
}

.left-panel {
  width: 380px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.right-panel {
  flex: 1;
  min-width: 0;
}

/* Cards */
.quote-card,
.info-card,
.chart-card {
  background: var(--bg-card);
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  padding: 16px;
}

.quote-card {
  flex-shrink: 0;
}

.info-card {
  flex: 1;
  overflow-y: auto;
}

.chart-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-line);
  display: flex;
  align-items: center;
  gap: 8px;
}

.stock-code {
  font-size: 13px;
  font-weight: 400;
  color: var(--text-muted);
  font-family: 'SF Mono', Monaco, monospace;
}

/* Quote Content */
.quote-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.price-section {
  display: flex;
  align-items: baseline;
  gap: 16px;
}

.current-price {
  font-size: 32px;
  font-weight: 700;
  font-family: 'SF Mono', Monaco, monospace;
}

.price-change {
  display: flex;
  gap: 8px;
  font-size: 16px;
  font-weight: 500;
  font-family: 'SF Mono', Monaco, monospace;
}

.change-percent {
  padding: 2px 6px;
  border-radius: 2px;
  background: rgba(230, 57, 53, 0.1);
}

.change-percent.text-down {
  background: rgba(46, 125, 50, 0.1);
}

.quote-details {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-item .label {
  font-size: 12px;
  color: var(--text-muted);
}

.detail-item .value {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  font-family: 'SF Mono', Monaco, monospace;
}

/* Info Content */
.info-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item.full-width {
  flex: 1;
}

.info-item .label {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
}

.tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.more-tag {
  font-size: 12px;
  color: var(--text-muted);
  padding: 2px 6px;
  background: var(--bg-system);
  border-radius: 2px;
}

.intro-text {
  font-size: 13px;
  color: var(--text-regular);
  line-height: 1.6;
  text-align: justify;
}

/* Chart */
.chart-container {
  flex: 1;
  min-height: 300px;
}

.chart-loading,
.chart-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Loading & Empty States */
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
  color: var(--text-muted);
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: var(--text-muted);
  font-size: 14px;
}

.empty-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: var(--text-muted);
}

.empty-content p {
  font-size: 14px;
}

/* Icon imports workaround */
:deep(.el-icon) {
  font-size: inherit;
}
</style>