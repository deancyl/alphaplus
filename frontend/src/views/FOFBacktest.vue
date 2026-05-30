<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, InfoFilled } from '@element-plus/icons-vue'
import SplitPanel from '@/components/SplitPanel.vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import type { EChartsOption } from 'echarts'
import { useBreakpoint } from '@/composables/useBreakpoint'
import {
  searchFunds,
  createPortfolio,
  getPortfolios,
  deletePortfolio,
  runBacktest,
  BENCHMARK_OPTIONS,
  type FundSearchResult,
  type PortfolioFundItem,
  type PortfolioItem,
  type BacktestConfig,
  type BacktestResult,
} from '@/api/portfolio'
import { saveBacktest, getAllBacktests, deleteBacktest, type BacktestHistoryRecord } from '@/services/idb'

// ==================== State ====================

// Breakpoint for responsive design
const { isMobile } = useBreakpoint()

// Active chart tab for mobile
const activeChartTab = ref<'performance' | 'brinson'>('performance')

// Portfolio Builder
const portfolioName = ref('')
const fundRows = ref<PortfolioFundItem[]>([])
const fundSearchResults = ref<FundSearchResult[]>([])
const fundSearchLoading = ref<string | null>(null) // fund_code being searched
const savingPortfolio = ref(false)
const portfolios = ref<PortfolioItem[]>([])
const loadingPortfolios = ref(false)

// Backtest Configuration
const startDate = ref('')
const endDate = ref('')
const selectedBenchmark = ref('000300')
const linkingMethod = ref<'auto' | 'carino' | 'menchero'>('auto')
const periodGranularity = ref<'daily' | 'weekly' | 'monthly'>('monthly')
const useAdjustedNav = ref(false)
const runningBacktest = ref(false)

// Results
const backtestResult = ref<BacktestResult | null>(null)

// Active portfolio
const activePortfolioId = ref<string | null>(null)

// Backtest history (IndexedDB)
const backtestHistory = ref<BacktestHistoryRecord[]>([])
const loadingHistory = ref(false)

// ==================== Computed ====================

/**
 * Total weight of all funds (must equal 100)
 */
const totalWeight = computed(() => {
  return fundRows.value.reduce((sum, row) => sum + row.weight, 0)
})

/**
 * Weight validation status
 */
const weightValidation = computed(() => {
  if (totalWeight.value === 100) return { valid: true, message: '权重合计正确' }
  if (totalWeight.value > 100) return { valid: false, message: `权重超出 ${totalWeight.value - 100}%` }
  return { valid: false, message: `还差 ${100 - totalWeight.value}%` }
})

/**
 * Performance chart option
 */
const performanceChartOption = computed<EChartsOption | null>(() => {
  if (!backtestResult.value) return null
  
  const { portfolio_nav_series, benchmark_nav_series } = backtestResult.value
  
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: 'var(--border-line)',
      borderWidth: 1,
      textStyle: { color: 'var(--text-primary)', fontSize: 12 },
      formatter: (params: any) => {
        const date = params[0]?.axisValue
        let html = `<div style="font-weight:600;margin-bottom:4px">${date}</div>`
        params.forEach((item: any) => {
          html += `<div style="display:flex;justify-content:space-between;gap:20px">
            <span>${item.marker} ${item.seriesName}</span>
            <span style="font-weight:600">${item.value?.toFixed(4)}</span>
          </div>`
        })
        return html
      }
    },
    legend: {
      data: ['组合净值', `${backtestResult.value.benchmark_name}`],
      bottom: 0,
      textStyle: { color: 'var(--text-regular)', fontSize: 12 }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '8%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: portfolio_nav_series.map(p => p.date),
      axisLine: { lineStyle: { color: 'var(--border-line)' } },
      axisLabel: { 
        color: 'var(--text-muted)', 
        fontSize: 11,
        formatter: (value: string) => value.slice(5) // Show MM-DD
      }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: 'var(--text-muted)', fontSize: 11 },
      splitLine: { lineStyle: { color: 'var(--border-line)', type: 'dashed' } }
    },
    series: [
      {
        name: '组合净值',
        type: 'line',
        data: portfolio_nav_series.map(p => p.nav),
        lineStyle: { color: 'var(--brand-navy-dark)', width: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(0, 51, 153, 0.15)' },
              { offset: 1, color: 'rgba(0, 51, 153, 0)' }
            ]
          }
        },
        symbol: 'none',
        smooth: true
      },
      {
        name: backtestResult.value.benchmark_name,
        type: 'line',
        data: benchmark_nav_series.map(p => p.nav),
        lineStyle: { color: 'var(--market-flat)', width: 1.5, type: 'dashed' },
        symbol: 'none',
        smooth: true
      }
    ]
  }
})

/**
 * Brinson attribution waterfall chart option
 */
const brinsonChartOption = computed<EChartsOption | null>(() => {
  if (!backtestResult.value) return null
  
  const { brinson_attribution } = backtestResult.value
  
  // Waterfall chart data: [value, positive part, negative part]
  const data = [
    { name: '配置效应', value: brinson_attribution.allocation_effect },
    { name: '选择效应', value: brinson_attribution.selection_effect },
    { name: '交互效应', value: brinson_attribution.interaction_effect },
    { name: '总超额收益', value: brinson_attribution.total_excess_return }
  ]
  
  // Calculate cumulative for waterfall effect
  let cumulative = 0
  const waterfallData = data.map((item, index) => {
    const start = cumulative
    const end = cumulative + item.value
    cumulative = end
    
    return {
      name: item.name,
      value: item.value,
      itemStyle: {
        color: item.value >= 0 ? 'var(--market-up)' : 'var(--market-down)'
      }
    }
  })
  
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: 'var(--border-line)',
      borderWidth: 1,
      textStyle: { color: 'var(--text-primary)', fontSize: 12 },
      formatter: (params: any) => {
        const item = params[0]
        const sign = item.value >= 0 ? '+' : ''
        return `<div style="font-weight:600">${item.name}</div>
                <div style="color:${item.value >= 0 ? 'var(--market-up)' : 'var(--market-down)'}">
                  ${sign}${item.value.toFixed(2)}%
                </div>`
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '8%',
      top: '8%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: waterfallData.map(d => d.name),
      axisLine: { lineStyle: { color: 'var(--border-line)' } },
      axisLabel: { color: 'var(--text-regular)', fontSize: 12 }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { 
        color: 'var(--text-muted)', 
        fontSize: 11,
        formatter: '{value}%'
      },
      splitLine: { lineStyle: { color: 'var(--border-line)', type: 'dashed' } }
    },
    series: [{
      type: 'bar',
      data: waterfallData,
      barWidth: '40%',
      label: {
        show: true,
        position: 'top',
        formatter: (params: any) => {
          const sign = params.value >= 0 ? '+' : ''
          return `${sign}${params.value.toFixed(2)}%`
        },
        fontSize: 11,
        color: 'var(--text-primary)'
      }
    }]
  }
})

/**
 * Period breakdown chart option for multi-period attribution
 */
const periodChartOption = computed<EChartsOption | null>(() => {
  if (!backtestResult.value?.multi_period_brinson_attribution?.periods) return null
  
  const periods = backtestResult.value.multi_period_brinson_attribution.periods
  
  return {
    title: { 
      text: '期间归因分解', 
      left: 'center',
      textStyle: { color: 'var(--text-primary)', fontSize: 14 }
    },
    tooltip: { 
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: 'var(--border-line)',
      borderWidth: 1,
      textStyle: { color: 'var(--text-primary)', fontSize: 12 }
    },
    legend: { 
      data: ['配置效应', '选择效应', '交互效应'],
      bottom: 0,
      textStyle: { color: 'var(--text-regular)', fontSize: 12 }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '15%',
      containLabel: true
    },
    xAxis: { 
      type: 'category', 
      data: periods.map(p => p.period_start),
      axisLine: { lineStyle: { color: 'var(--border-line)' } },
      axisLabel: { 
        color: 'var(--text-muted)', 
        fontSize: 10,
        rotate: 45
      }
    },
    yAxis: { 
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { 
        color: 'var(--text-muted)', 
        fontSize: 11,
        formatter: '{value}%'
      },
      splitLine: { lineStyle: { color: 'var(--border-line)', type: 'dashed' } }
    },
    series: [
      { 
        name: '配置效应', 
        type: 'bar', 
        data: periods.map(p => p.allocation_effect),
        itemStyle: { color: 'var(--brand-navy-dark)' }
      },
      { 
        name: '选择效应', 
        type: 'bar', 
        data: periods.map(p => p.selection_effect),
        itemStyle: { color: 'var(--market-up)' }
      },
      { 
        name: '交互效应', 
        type: 'bar', 
        data: periods.map(p => p.interaction_effect),
        itemStyle: { color: 'var(--market-flat)' }
      }
    ]
  }
})

// ==================== Methods ====================

/**
 * Add a new fund row
 */
const addFundRow = () => {
  fundRows.value.push({
    fund_code: '',
    fund_name: '',
    weight: 0
  })
}

/**
 * Remove a fund row
 */
const removeFundRow = (index: number) => {
  fundRows.value.splice(index, 1)
}

/**
 * Search funds for autocomplete
 */
const handleFundSearch = async (query: string, index: number) => {
  if (!query || query.length < 2) {
    fundSearchResults.value = []
    return
  }
  
  const row = fundRows.value[index]
  if (!row) return
  
  fundSearchLoading.value = row.fund_code
  
  try {
    const results = await searchFunds(query)
    fundSearchResults.value = results
  } catch (error) {
    ElMessage.error('基金搜索失败，请重试')
  } finally {
    fundSearchLoading.value = null
  }
}

/**
 * Select fund from autocomplete
 */
const selectFund = (fund: FundSearchResult, index: number) => {
  fundRows.value[index] = {
    fund_code: fund.fund_code,
    fund_name: fund.fund_name,
    weight: fundRows.value[index].weight || 0
  }
  fundSearchResults.value = []
}

/**
 * Save portfolio
 */
const savePortfolio = async () => {
  if (!portfolioName.value.trim()) {
    ElMessage.warning('请输入组合名称')
    return
  }
  
  if (!weightValidation.value.valid) {
    ElMessage.warning('权重合计必须等于100%')
    return
  }
  
  if (fundRows.value.length === 0) {
    ElMessage.warning('请至少添加一只基金')
    return
  }
  
  // Validate all funds are selected
  const hasEmptyFunds = fundRows.value.some(row => !row.fund_code)
  if (hasEmptyFunds) {
    ElMessage.warning('请为所有行选择基金')
    return
  }
  
  savingPortfolio.value = true
  
  try {
    const portfolio = await createPortfolio({
      name: portfolioName.value,
      funds: fundRows.value
    })
    
    ElMessage.success('组合保存成功')
    activePortfolioId.value = portfolio.id
    await loadPortfolios()
  } catch (error) {
    ElMessage.error('保存组合失败，请重试')
  } finally {
    savingPortfolio.value = false
  }
}

/**
 * Load portfolios list
 */
const loadPortfolios = async () => {
  loadingPortfolios.value = true
  
  try {
    portfolios.value = await getPortfolios()
  } catch (error) {
    ElMessage.error('加载组合列表失败')
    // Use empty array on error
    portfolios.value = []
  } finally {
    loadingPortfolios.value = false
  }
}

/**
 * Load portfolio into editor
 */
const loadPortfolio = (portfolio: PortfolioItem) => {
  portfolioName.value = portfolio.name
  fundRows.value = [...portfolio.funds]
  activePortfolioId.value = portfolio.id
}

/**
 * Delete portfolio
 */
const handleDeletePortfolio = async (portfolio: PortfolioItem) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除组合"${portfolio.name}"吗？`,
      '确认删除',
      { type: 'warning' }
    )
    
    await deletePortfolio(portfolio.id)
    ElMessage.success('删除成功')
    
    if (activePortfolioId.value === portfolio.id) {
      activePortfolioId.value = null
      portfolioName.value = ''
      fundRows.value = []
    }
    
    await loadPortfolios()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除组合失败')
    }
  }
}

/**
 * Run backtest
 */
const runBacktestHandler = async () => {
  if (!activePortfolioId.value) {
    ElMessage.warning('请先保存组合')
    return
  }
  
  if (!startDate.value || !endDate.value) {
    ElMessage.warning('请选择回测日期区间')
    return
  }
  
  if (new Date(startDate.value) >= new Date(endDate.value)) {
    ElMessage.warning('开始日期必须早于结束日期')
    return
  }
  
  runningBacktest.value = true
  
  try {
    const config: BacktestConfig = {
      start_date: startDate.value,
      end_date: endDate.value,
      benchmark: selectedBenchmark.value,
      linking_method: linkingMethod.value,
      period_granularity: periodGranularity.value,
      use_adjusted_nav: useAdjustedNav.value
    }
    
    backtestResult.value = await runBacktest(activePortfolioId.value, config)
    
    // Save to IndexedDB for offline access
    const backtestId = `${activePortfolioId.value}-${Date.now()}`
    await saveBacktest(backtestId, backtestResult.value)
    await loadBacktestHistory()
    
    if (backtestResult.value.is_simulated) {
      ElMessage.warning('使用模拟数据进行展示')
    } else {
      ElMessage.success('回测完成')
    }
  } catch (error) {
    ElMessage.error('回测运行失败，请检查参数后重试')
  } finally {
    runningBacktest.value = false
  }
}

/**
 * Format percentage for display
 */
const formatPercent = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return '-'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

/**
 * Format number for display
 */
const formatNumber = (value: number | null | undefined, decimals: number = 2): string => {
  if (value === null || value === undefined) return '-'
  return value.toFixed(decimals)
}

/**
 * Get value class (up/down/flat)
 */
const getValueClass = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return ''
  return value >= 0 ? 'text-up' : 'text-down'
}

/**
 * Load backtest history from IndexedDB
 */
const loadBacktestHistory = async () => {
  loadingHistory.value = true
  try {
    backtestHistory.value = await getAllBacktests()
  } finally {
    loadingHistory.value = false
  }
}

/**
 * Load a historical backtest result
 */
const loadHistoryResult = (record: BacktestHistoryRecord) => {
  backtestResult.value = record.result
  ElMessage.success(`已加载历史回测: ${record.portfolio_name}`)
}

/**
 * Delete a backtest from history
 */
const handleDeleteHistory = async (record: BacktestHistoryRecord) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除历史回测"${record.portfolio_name}"吗？`,
      '确认删除',
      { type: 'warning' }
    )
    
    await deleteBacktest(record.id)
    ElMessage.success('删除成功')
    await loadBacktestHistory()
    
    // Clear current result if it was the deleted one
    if (backtestResult.value && backtestResult.value.portfolio_name === record.portfolio_name) {
      backtestResult.value = null
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

/**
 * Format date for history display
 */
const formatHistoryDate = (dateStr: string): string => {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// ==================== Lifecycle ====================

onMounted(() => {
  loadPortfolios()
  loadBacktestHistory()
  
  // Set default dates (last 3 years)
  const today = new Date()
  const threeYearsAgo = new Date(today.getFullYear() - 3, today.getMonth(), today.getDate())
  
  endDate.value = today.toISOString().slice(0, 10)
  startDate.value = threeYearsAgo.toISOString().slice(0, 10)
})

// Clear results when config changes
watch([startDate, endDate, selectedBenchmark, linkingMethod, periodGranularity, useAdjustedNav], () => {
  backtestResult.value = null
})
</script>

<template>
  <div class="fof-backtest">
    <SplitPanel
      :initial-left-size="360"
      :min-left-size="300"
      :max-left-size="480"
      storage-key="fofbacktest-panel-size"
    >
      <!-- Left Panel: Portfolio Builder & Config -->
      <template #left="{ collapsed }">
        <div class="config-panel" :class="{ 'config-panel--collapsed': collapsed }">
          <!-- Portfolio Builder Section -->
          <ErrorBoundary v-if="!collapsed" error-message="组合构建加载失败">
            <div class="config-section">
              <h3 class="section-title">
                <span class="section-icon">📊</span>
                组合构建
              </h3>
            
            <!-- Portfolio Name -->
            <div class="form-item">
              <label>组合名称</label>
              <el-input
                v-model="portfolioName"
                placeholder="输入组合名称"
                clearable
              />
            </div>
            
            <!-- Fund Rows -->
            <div class="fund-rows">
              <div class="fund-rows-header">
                <span>基金配置</span>
                <el-button
                  type="primary"
                  size="small"
                  @click="addFundRow"
                  :icon="Plus"
                >
                  添加基金
                </el-button>
              </div>
              
              <div
                v-for="(row, index) in fundRows"
                :key="index"
                class="fund-row"
              >
                <!-- Fund Code Autocomplete -->
                <el-autocomplete
                  v-model="row.fund_code"
                  :fetch-suggestions="(q: string, cb: any) => handleFundSearch(q, index)"
                  placeholder="搜索基金代码/名称"
                  clearable
                  class="fund-autocomplete"
                  @select="(item: FundSearchResult) => selectFund(item, index)"
                >
                  <template #default="{ item }">
                    <div class="fund-suggestion">
                      <span class="fund-code">{{ item.fund_code }}</span>
                      <span class="fund-name">{{ item.fund_name }}</span>
                      <span class="fund-type">{{ item.fund_type }}</span>
                    </div>
                  </template>
                </el-autocomplete>
                
                <!-- Weight Input -->
                <el-input-number
                  v-model="row.weight"
                  :min="0"
                  :max="100"
                  :step="5"
                  :precision="1"
                  placeholder="权重%"
                  class="weight-input"
                />
                
                <!-- Remove Button -->
                <el-button
                  type="danger"
                  size="small"
                  @click="removeFundRow(index)"
                  :icon="Delete"
                  circle
                />
              </div>
              
              <!-- Weight Summary -->
              <div class="weight-summary" :class="{ 'weight-error': !weightValidation.valid }">
                <span>权重合计: {{ totalWeight.toFixed(1) }}%</span>
                <span class="weight-message">{{ weightValidation.message }}</span>
              </div>
            </div>
            
            <!-- Save Button -->
            <el-button
              type="primary"
              @click="savePortfolio"
              :loading="savingPortfolio"
              :disabled="!weightValidation.valid || fundRows.length === 0"
              class="save-btn"
            >
              保存组合
            </el-button>
            
            <!-- Portfolio List -->
            <div class="portfolio-list">
              <h4>已保存组合</h4>
              <div v-if="loadingPortfolios" class="loading-placeholder">
                加载中...
              </div>
              <div v-else-if="portfolios.length === 0" class="empty-hint">
                暂无保存的组合
              </div>
              <div v-else class="portfolio-items">
                <div
                  v-for="portfolio in portfolios"
                  :key="portfolio.id"
                  class="portfolio-item"
                  :class="{ 'portfolio-item--active': activePortfolioId === portfolio.id }"
                  @click="loadPortfolio(portfolio)"
                >
                  <div class="portfolio-info">
                    <span class="portfolio-name">{{ portfolio.name }}</span>
                    <span class="portfolio-count">{{ portfolio.funds.length }}只基金</span>
                  </div>
                  <el-button
                    type="danger"
                    size="small"
                    @click.stop="handleDeletePortfolio(portfolio)"
                    :icon="Delete"
                    circle
                  />
                </div>
              </div>
            </div>
            </div>
          </ErrorBoundary>
          
          <!-- Backtest Configuration Section -->
          <ErrorBoundary v-if="!collapsed" error-message="回测配置加载失败">
            <div class="config-section">
              <h3 class="section-title">
                <span class="section-icon">⚙️</span>
                回测配置
              </h3>
            
            <div class="form-item">
              <label>开始日期</label>
              <el-date-picker
                v-model="startDate"
                type="date"
                placeholder="选择开始日期"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </div>
            
            <div class="form-item">
              <label>结束日期</label>
              <el-date-picker
                v-model="endDate"
                type="date"
                placeholder="选择结束日期"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </div>
            
            <div class="form-item">
              <label>基准指数</label>
              <el-select v-model="selectedBenchmark" style="width: 100%">
                <el-option
                  v-for="benchmark in BENCHMARK_OPTIONS"
                  :key="benchmark.code"
                  :label="benchmark.name"
                  :value="benchmark.code"
                >
                  <span style="float: left">{{ benchmark.name }}</span>
                  <span style="float: right; color: var(--text-muted); font-size: 12px">
                    {{ benchmark.fullName }}
                  </span>
                </el-option>
              </el-select>
            </div>
            
            <div class="form-item">
              <label>多期链接方法</label>
              <el-radio-group v-model="linkingMethod" class="linking-method-group">
                <el-radio-button value="auto">自动</el-radio-button>
                <el-radio-button value="carino">Carino</el-radio-button>
                <el-radio-button value="menchero">Menchero</el-radio-button>
              </el-radio-group>
              <div class="hint-text">当超额收益接近零时自动切换Menchero</div>
            </div>
            
            <div class="form-item">
              <label>期间粒度</label>
              <el-select v-model="periodGranularity" style="width: 100%">
                <el-option value="daily" label="日度" />
                <el-option value="weekly" label="周度" />
                <el-option value="monthly" label="月度" />
              </el-select>
            </div>
            
            <div class="form-item">
              <div class="checkbox-row">
                <el-checkbox v-model="useAdjustedNav">
                  使用复权净值 (分红再投资)
                </el-checkbox>
                <el-tooltip 
                  content="复权净值将分红按除权日净值再投资，用于准确比较长期收益"
                  placement="top"
                >
                  <el-icon class="info-icon"><InfoFilled /></el-icon>
                </el-tooltip>
              </div>
            </div>
            
            <el-button
              type="primary"
              size="large"
              @click="runBacktestHandler"
              :loading="runningBacktest"
              :disabled="!activePortfolioId"
              class="run-btn"
            >
              运行回测
            </el-button>
            </div>
          </ErrorBoundary>
          
          <!-- Backtest History Section -->
          <ErrorBoundary v-if="!collapsed" error-message="历史记录加载失败">
            <div class="config-section history-section">
              <h3 class="section-title">
                <span class="section-icon">📜</span>
                历史记录
              </h3>
              
              <div v-if="loadingHistory" class="loading-placeholder">
                加载中...
              </div>
              <div v-else-if="backtestHistory.length === 0" class="empty-hint">
                暂无历史回测记录
              </div>
              <div v-else class="history-list">
                <div
                  v-for="record in backtestHistory"
                  :key="record.id"
                  class="history-item"
                  @click="loadHistoryResult(record)"
                >
                  <div class="history-info">
                    <div class="history-name">{{ record.portfolio_name }}</div>
                    <div class="history-meta">
                      <span class="history-date">{{ formatHistoryDate(record.created_at) }}</span>
                      <span 
                        class="history-return"
                        :class="getValueClass(record.result.performance.total_return)"
                      >
                        {{ formatPercent(record.result.performance.total_return) }}
                      </span>
                    </div>
                  </div>
                  <el-button
                    type="danger"
                    size="small"
                    @click.stop="handleDeleteHistory(record)"
                    :icon="Delete"
                    circle
                  />
                </div>
              </div>
            </div>
          </ErrorBoundary>
        </div>
      </template>
      
<!-- Right Panel: Results Dashboard -->
      <template #right>
        <ErrorBoundary error-message="回测结果加载失败">
          <div class="results-panel">
            <!-- Empty State -->
            <div v-if="!backtestResult" class="empty-state">
              <div class="empty-icon">📈</div>
              <h3>FOF组合回测</h3>
              <p>在左侧构建组合并运行回测</p>
              <div class="empty-tips">
                <div class="tip-item">💡 添加基金并分配权重（合计100%）</div>
                <div class="tip-item">💡 选择回测日期区间和基准指数</div>
                <div class="tip-item">💡 点击"运行回测"查看结果</div>
              </div>
            </div>

            <!-- Results Content -->
            <template v-else>
            <!-- Header -->
            <div class="results-header">
              <div class="results-title">
                <h2>{{ backtestResult.portfolio_name }}</h2>
                <span class="results-period">
                  {{ backtestResult.start_date }} ~ {{ backtestResult.end_date }}
                </span>
              </div>
              <div class="results-badges">
                <el-tag v-if="useAdjustedNav" type="success" size="small">
                  复权净值
                </el-tag>
                <span v-if="backtestResult.is_simulated" class="simulated-badge">
                  模拟数据
                </span>
              </div>
            </div>
            
            <!-- Statistics Cards -->
            <div class="stats-grid">
              <div class="stat-card">
                <div class="stat-label">总收益</div>
                <div class="stat-value" :class="getValueClass(backtestResult.performance.total_return)">
                  {{ formatPercent(backtestResult.performance.total_return) }}
                </div>
              </div>
              
              <div class="stat-card">
                <div class="stat-label">年化收益</div>
                <div class="stat-value" :class="getValueClass(backtestResult.performance.annual_return)">
                  {{ formatPercent(backtestResult.performance.annual_return) }}
                </div>
              </div>
              
              <div class="stat-card">
                <div class="stat-label">最大回撤</div>
                <div class="stat-value text-down">
                  -{{ formatPercent(Math.abs(backtestResult.performance.max_drawdown)) }}
                </div>
              </div>
              
              <div class="stat-card">
                <div class="stat-label">夏普比率</div>
                <div class="stat-value" :class="getValueClass(backtestResult.performance.sharpe_ratio)">
                  {{ formatNumber(backtestResult.performance.sharpe_ratio, 2) }}
                </div>
              </div>
              
              <div class="stat-card">
                <div class="stat-label">年化波动</div>
                <div class="stat-value">
                  {{ formatPercent(backtestResult.performance.volatility) }}
                </div>
              </div>
              
              <div class="stat-card" v-if="backtestResult.performance.calmar_ratio !== null">
                <div class="stat-label">卡玛比率</div>
                <div class="stat-value" :class="getValueClass(backtestResult.performance.calmar_ratio)">
                  {{ formatNumber(backtestResult.performance.calmar_ratio, 2) }}
                </div>
              </div>
            </div>
            
            <!-- Performance Chart -->
            <div class="chart-section">
              <!-- Mobile Tab Selector -->
              <div v-if="isMobile" class="chart-tabs-mobile">
                <el-radio-group v-model="activeChartTab" size="small">
                  <el-radio-button value="performance">净值曲线</el-radio-button>
                  <el-radio-button value="brinson">Brinson归因</el-radio-button>
                </el-radio-group>
              </div>
              
              <!-- Desktop: Show both charts -->
              <template v-if="!isMobile">
                <h3 class="chart-title">净值曲线</h3>
                <EChartsWrapper
                  v-if="performanceChartOption"
                  :option="performanceChartOption"
                  height="400px"
                />
                
                <!-- Brinson Attribution Chart -->
                <h3 class="chart-title" style="margin-top: 24px;">Brinson归因分析</h3>
                <EChartsWrapper
                  v-if="brinsonChartOption"
                  :option="brinsonChartOption"
                  height="300px"
                />
              </template>
              
              <!-- Mobile: Show active chart with fixed height -->
              <template v-else>
                <div v-show="activeChartTab === 'performance'" class="chart-tab-content">
                  <h3 class="chart-title">净值曲线</h3>
                  <EChartsWrapper
                    v-if="performanceChartOption"
                    :option="performanceChartOption"
                    height="260px"
                  />
                </div>
                
                <div v-show="activeChartTab === 'brinson'" class="chart-tab-content">
                  <h3 class="chart-title">Brinson归因分析</h3>
                  <EChartsWrapper
                    v-if="brinsonChartOption"
                    :option="brinsonChartOption"
                    height="260px"
                  />
                </div>
              </template>
              
              <!-- Brinson Details Table -->
              <div class="brinson-details">
                <el-table
                  :data="backtestResult.brinson_attribution.details"
                  stripe
                  size="small"
                >
                  <el-table-column prop="asset_class" label="资产类别" width="120" />
                  <el-table-column prop="portfolio_weight" label="组合权重%" width="100">
                    <template #default="{ row }">
                      {{ formatNumber(row.portfolio_weight, 1) }}%
                    </template>
                  </el-table-column>
                  <el-table-column prop="benchmark_weight" label="基准权重%" width="100">
                    <template #default="{ row }">
                      {{ formatNumber(row.benchmark_weight, 1) }}%
                    </template>
                  </el-table-column>
                  <el-table-column prop="allocation" label="配置效应%" width="100">
                    <template #default="{ row }">
                      <span :class="getValueClass(row.allocation)">
                        {{ formatPercent(row.allocation) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="selection" label="选择效应%" width="100">
                    <template #default="{ row }">
                      <span :class="getValueClass(row.selection)">
                        {{ formatPercent(row.selection) }}
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="total" label="总贡献%">
                    <template #default="{ row }">
                      <span :class="getValueClass(row.total)">
                        {{ formatPercent(row.total) }}
                      </span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
            
            <!-- Multi-Period Brinson Attribution -->
            <div class="chart-section">
              <h3 class="chart-title">
                多期归因分析
                <el-tag size="small" type="info" style="margin-left: 8px">
                  {{ backtestResult.multi_period_brinson_attribution.linking_method }}
                </el-tag>
              </h3>
              
              <!-- Attribution Summary -->
              <div class="attribution-summary">
                <div class="attribution-item">
                  <span class="label">配置效应:</span>
                  <span class="value" :class="getValueClass(backtestResult.multi_period_brinson_attribution.allocation_effect)">
                    {{ formatPercent(backtestResult.multi_period_brinson_attribution.allocation_effect) }}
                  </span>
                </div>
                <div class="attribution-item">
                  <span class="label">选择效应:</span>
                  <span class="value" :class="getValueClass(backtestResult.multi_period_brinson_attribution.selection_effect)">
                    {{ formatPercent(backtestResult.multi_period_brinson_attribution.selection_effect) }}
                  </span>
                </div>
                <div class="attribution-item">
                  <span class="label">交互效应:</span>
                  <span class="value" :class="getValueClass(backtestResult.multi_period_brinson_attribution.interaction_effect)">
                    {{ formatPercent(backtestResult.multi_period_brinson_attribution.interaction_effect) }}
                  </span>
                </div>
                <div class="attribution-item residual">
                  <span class="label">残差:</span>
                  <span class="value">{{ backtestResult.multi_period_brinson_attribution.residual.toExponential(2) }}</span>
                  <el-tag 
                    v-if="Math.abs(backtestResult.multi_period_brinson_attribution.residual) < 1e-12" 
                    type="success" 
                    size="small"
                  >
                    ✓ 精度达标
                  </el-tag>
                </div>
              </div>
              
              <!-- Period Breakdown Chart -->
              <div v-if="!isMobile">
                <EChartsWrapper 
                  v-if="periodChartOption" 
                  :option="periodChartOption" 
                  height="300px" 
                />
              </div>
              <div v-else>
                <EChartsWrapper 
                  v-if="periodChartOption" 
                  :option="periodChartOption" 
                  height="260px" 
                />
              </div>
            </div>
          </template>
        </div>
      </ErrorBoundary>
    </template>
  </SplitPanel>
</div>
</template>

<style scoped>
.fof-backtest {
  height: calc(100vh - 100px);
  padding: 0;
}

.config-panel {
  height: 100%;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.config-panel--collapsed {
  padding: 12px 8px;
  align-items: center;
}

.config-section {
  flex-shrink: 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-line);
}

.section-icon {
  font-size: 18px;
}

.form-item {
  margin-bottom: 12px;
}

.form-item label {
  display: block;
  font-size: 13px;
  color: var(--text-regular);
  margin-bottom: 6px;
}

/* Fund Rows */
.fund-rows {
  margin-bottom: 16px;
}

.fund-rows-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--text-regular);
}

.fund-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
  padding: 8px;
  background: var(--bg-system);
  border-radius: 4px;
}

.fund-autocomplete {
  flex: 1;
}

.weight-input {
  width: 100px;
}

.fund-suggestion {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
}

.fund-code {
  font-weight: 600;
  color: var(--brand-navy-dark);
  min-width: 60px;
}

.fund-name {
  flex: 1;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fund-type {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-system);
  padding: 2px 6px;
  border-radius: 3px;
}

.weight-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(46, 125, 50, 0.1);
  border-radius: 4px;
  font-size: 13px;
  color: var(--market-down);
}

.weight-summary.weight-error {
  background: rgba(230, 57, 53, 0.1);
  color: var(--market-up);
}

.weight-message {
  font-weight: 600;
}

.save-btn {
  width: 100%;
  margin-bottom: 16px;
}

/* Portfolio List */
.portfolio-list {
  border-top: 1px solid var(--border-line);
  padding-top: 16px;
}

.portfolio-list h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.loading-placeholder,
.empty-hint {
  text-align: center;
  padding: 20px;
  color: var(--text-muted);
  font-size: 13px;
}

.portfolio-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.portfolio-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: var(--bg-system);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.portfolio-item:hover {
  background: var(--bg-card);
  border-color: var(--brand-navy-active);
}

.portfolio-item--active {
  background: rgba(0, 51, 153, 0.05);
  border-color: var(--brand-navy-dark);
}

.portfolio-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.portfolio-name {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 13px;
}

.portfolio-count {
  font-size: 12px;
  color: var(--text-muted);
}

/* Run Button */
.run-btn {
  width: 100%;
  margin-top: 12px;
  height: 44px;
  font-size: 15px;
}

/* Results Panel */
.results-panel {
  height: 100%;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 20px;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: var(--text-muted);
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state h3 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.empty-state p {
  font-size: 14px;
  margin-bottom: 24px;
}

.empty-tips {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tip-item {
  font-size: 13px;
  padding: 8px 16px;
  background: var(--bg-system);
  border-radius: 4px;
}

/* Results Header */
.results-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-line);
}

.results-title h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.results-period {
  font-size: 13px;
  color: var(--text-muted);
}

.simulated-badge {
  font-size: 12px;
  color: #FF8C00;
  background: rgba(255, 140, 0, 0.1);
  padding: 4px 8px;
  border-radius: 4px;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.stat-card {
  padding: 16px;
  background: var(--bg-system);
  border-radius: 4px;
  text-align: center;
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

/* Chart Section */
.chart-section {
  margin-bottom: 24px;
}

.chart-tabs-mobile {
  margin-bottom: 12px;
  display: flex;
  justify-content: center;
}

.chart-tab-content {
  width: 100%;
}

.chart-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.brinson-details {
  margin-top: 16px;
  overflow-x: auto;
}

/* Linking Method Controls */
.linking-method-group {
  width: 100%;
}

.hint-text {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

/* Checkbox with tooltip */
.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-icon {
  font-size: 16px;
  color: var(--text-muted);
  cursor: help;
  transition: color 0.2s;
}

.info-icon:hover {
  color: var(--brand-navy-dark);
}

/* Results badges container */
.results-badges {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Multi-Period Attribution Summary */
.attribution-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
  padding: 16px;
  background: var(--bg-system);
  border-radius: 4px;
}

.attribution-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.attribution-item .label {
  font-size: 13px;
  color: var(--text-regular);
}

.attribution-item .value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.attribution-item.residual {
  grid-column: 1 / -1;
  padding-top: 8px;
  border-top: 1px solid var(--border-line);
  margin-top: 8px;
}

.attribution-item.residual .value {
  font-size: 13px;
  font-family: 'Courier New', monospace;
  color: var(--text-muted);
}

/* Backtest History Section */
.history-section {
  border-top: 1px solid var(--border-line);
  padding-top: 16px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 240px;
  overflow-y: auto;
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: var(--bg-system);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.history-item:hover {
  background: var(--bg-card);
  border-color: var(--brand-navy-active);
}

.history-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  overflow: hidden;
}

.history-name {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
}

.history-date {
  color: var(--text-muted);
}

.history-return {
  font-weight: 600;
}

/* Responsive */
@media (max-width: 768px) {
  .fof-backtest {
    height: auto;
    min-height: calc(100vh - 100px);
  }
  
  .config-panel {
    max-height: 50vh;
  }
  
  .fund-row {
    flex-wrap: wrap;
  }
  
  .fund-autocomplete {
    width: 100%;
    margin-bottom: 8px;
  }
  
  .weight-input {
    flex: 1;
  }
  
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .stat-value {
    font-size: 18px;
  }
}
</style>
