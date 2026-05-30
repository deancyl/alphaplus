<script setup lang="ts">
import { ref, watch, onMounted, nextTick, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import {
  filterFunds,
  calculateAIP,
  type FundItem,
  type AIPCalculateRequest,
  type AIPCalculateResponse
} from '@/api/fund'
import { formatNumber, formatPercent, formatSign } from '@/utils/formatters'

// Form state
const formData = ref<AIPCalculateRequest>({
  fund_code: '',
  frequency: 'monthly',
  amount: 1000,
  start_date: '',
  end_date: ''
})

// Search state for fund autocomplete
const searchQuery = ref('')
const searchResults = ref<FundItem[]>([])
const searchLoading = ref(false)
const showSuggestions = ref(false)

// Result state
const result = ref<AIPCalculateResponse | null>(null)
const loading = ref(false)

// Chart ref
const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

// Frequency options
const frequencyOptions = [
  { label: '每周', value: 'weekly' },
  { label: '每两周', value: 'biweekly' },
  { label: '每月', value: 'monthly' }
]

// LocalStorage key
const STORAGE_KEY = 'aipCalcLastParams'

// Debounce timer
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

// Search funds with debounce
const debouncedSearch = () => {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  searchDebounceTimer = setTimeout(() => {
    handleSearch()
  }, 300)
}

// Search funds
const handleSearch = async () => {
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    return
  }

  searchLoading.value = true
  try {
    const response = await filterFunds({ page: 1, page_size: 20 })
    const query = searchQuery.value.trim().toLowerCase()
    searchResults.value = response.funds.filter(
      f =>
        f.fund_code.toLowerCase().includes(query) ||
        f.fund_name.toLowerCase().includes(query)
    )
    showSuggestions.value = searchResults.value.length > 0
  } catch (error) {
  } finally {
    searchLoading.value = false
  }
}

// Select fund from suggestions
const selectFund = (fund: FundItem) => {
  formData.value.fund_code = fund.fund_code
  searchQuery.value = `${fund.fund_code} - ${fund.fund_name}`
  showSuggestions.value = false
}

// Handle input focus with scroll for keyboard occlusion
const handleInputFocus = (e: FocusEvent) => {
  if (searchResults.value.length > 0) {
    showSuggestions.value = true
  }
  // Scroll input into view to avoid keyboard occlusion on mobile
  const target = e.target as HTMLElement
  if (target) {
    setTimeout(() => {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 100)
  }
}

// Handle click outside
const handleClickOutside = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.closest('.fund-search-wrapper')) {
    showSuggestions.value = false
  }
}

// Form validation
const validateForm = (): boolean => {
  if (!formData.value.fund_code) {
    ElMessage.warning('请选择基金')
    return false
  }
  if (!formData.value.start_date) {
    ElMessage.warning('请选择开始日期')
    return false
  }
  if (formData.value.amount < 1) {
    ElMessage.warning('每期金额必须大于0')
    return false
  }
  return true
}

// Calculate AIP
const handleCalculate = async () => {
  if (!validateForm()) return

  loading.value = true
  try {
    const params: AIPCalculateRequest = {
      ...formData.value,
      end_date: formData.value.end_date || undefined
    }
    const response = await calculateAIP(params)
    result.value = response

    // Save to localStorage
    localStorage.setItem(STORAGE_KEY, JSON.stringify(formData.value))

    // Render chart
    await nextTick()
    renderChart()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { detail?: string } } }
    ElMessage.error(err?.response?.data?.detail || '计算失败，请重试')
  } finally {
    loading.value = false
  }
}

// Load last calculation from localStorage
const loadLastCalculation = () => {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved) {
    try {
      const parsed = JSON.parse(saved) as AIPCalculateRequest
      formData.value = parsed
      if (parsed.fund_code) {
        searchQuery.value = parsed.fund_code
      }
      ElMessage.success('已加载上次计算参数')
    } catch {
      // Silent fail - localStorage parse error, use defaults
    }
  }
}

// Format currency
const formatCurrency = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return '-'
  return `¥${formatNumber(val)}`
}

// Get value class
const getValueClass = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return ''
  return val >= 0 ? 'text-up' : 'text-down'
}

// Handle numeric input focus with scroll for keyboard occlusion
const handleNumericInputFocus = (e: FocusEvent) => {
  const target = e.target as HTMLElement
  if (target) {
    setTimeout(() => {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 100)
  }
}

// Handle date picker focus with scroll for keyboard occlusion
const handleDatePickerFocus = (e: FocusEvent) => {
  const target = e.target as HTMLElement
  if (target) {
    setTimeout(() => {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 100)
  }
}

// Render NAV chart with investment markers
const renderChart = () => {
  if (!chartRef.value || !result.value) return

  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  const navHistory = result.value.nav_history
  const investmentDates = new Set(result.value.investment_dates)

  // Build markPoint data for investment dates
  const markPointData = navHistory
    .filter(item => investmentDates.has(item.date))
    .map(item => ({
      coord: [item.date, item.nav],
      value: '买',
      itemStyle: { color: '#0066cc' }
    }))

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = params as Array<{ axisValue: string; data: number; seriesName: string }>
        const item = navHistory.find(d => d.date === p[0].axisValue)
        if (!item) return ''
        return `
          <div style="padding: 8px;">
            <div style="font-weight: 600; margin-bottom: 4px;">${item.date}</div>
            <div>净值: ${item.nav.toFixed(4)}</div>
            <div>持有份额: ${item.units.toFixed(2)}</div>
            <div>持有市值: ¥${item.value.toFixed(2)}</div>
            <div>累计收益率: ${formatPercent(item.cumulative_return)}</div>
          </div>
        `
      }
    },
    legend: {
      data: ['净值', '累计收益率'],
      bottom: 0,
      textStyle: { color: 'var(--text-regular)', fontSize: 12 }
    },
    grid: {
      left: 60,
      right: 60,
      top: 40,
      bottom: 60
    },
    xAxis: {
      type: 'category',
      data: navHistory.map(d => d.date),
      axisLabel: {
        color: 'var(--text-muted)',
        fontSize: 11,
        rotate: 45
      },
      axisLine: { lineStyle: { color: 'var(--border-line)' } }
    },
    yAxis: [
      {
        type: 'value',
        name: '净值',
        position: 'left',
        axisLabel: { color: 'var(--text-muted)', fontSize: 11 },
        axisLine: { lineStyle: { color: 'var(--border-line)' } },
        splitLine: { lineStyle: { color: 'var(--border-line)', type: 'dashed' } }
      },
      {
        type: 'value',
        name: '收益率(%)',
        position: 'right',
        axisLabel: {
          color: 'var(--text-muted)',
          fontSize: 11,
          formatter: '{value}%'
        },
        axisLine: { lineStyle: { color: 'var(--border-line)' } },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '净值',
        type: 'line' as const,
        data: navHistory.map(d => d.nav),
        smooth: true,
        lineStyle: { color: '#0066cc', width: 2 },
        areaStyle: {
          color: {
            type: 'linear' as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(0, 102, 204, 0.2)' },
              { offset: 1, color: 'rgba(0, 102, 204, 0)' }
            ]
          }
        },
        markPoint: {
          symbol: 'circle',
          symbolSize: 8,
          data: markPointData,
          label: { show: false }
        }
      },
      {
        name: '累计收益率',
        type: 'line' as const,
        yAxisIndex: 1,
        data: navHistory.map(d => d.cumulative_return),
        smooth: true,
        lineStyle: { color: '#E63935', width: 1.5, type: 'dashed' },
        itemStyle: { color: '#E63935' }
      }
    ]
  }

  chart.setOption(option)
}

// Handle window resize
const handleResize = () => {
  chart?.resize()
}

// Watch search query
watch(searchQuery, () => {
  if (searchQuery.value && !formData.value.fund_code) {
    debouncedSearch()
  }
})

// Clear fund code when search query changes manually
watch(searchQuery, (newVal, oldVal) => {
  if (oldVal && newVal !== oldVal) {
    formData.value.fund_code = ''
  }
})

onMounted(() => {
  loadLastCalculation()
  document.addEventListener('click', handleClickOutside)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
})
</script>

<template>
  <div class="aip-calculator">
    <div class="page-header">
      <h2>定投计算器</h2>
      <p class="subtitle">模拟定期定额投资收益，对比一次性投入效果</p>
    </div>

    <div class="calc-container">
      <!-- Form Panel -->
      <div class="form-panel">
        <div class="panel-header">
          <h3>投资参数</h3>
        </div>

        <el-form label-position="top" class="calc-form">
          <!-- Fund Code with Autocomplete -->
          <el-form-item label="基金代码" required>
            <div class="fund-search-wrapper">
              <el-input
                v-model="searchQuery"
                placeholder="输入基金代码或名称搜索"
                clearable
                inputmode="search"
                autocomplete="off"
                enterkeyhint="next"
                @focus="handleInputFocus"
              >
                <template #prefix>
                  <el-icon><i-ep-search /></el-icon>
                </template>
              </el-input>

              <!-- Suggestions Dropdown -->
              <div v-if="showSuggestions && searchResults.length > 0" class="suggestions-dropdown">
                <div
                  v-for="fund in searchResults"
                  :key="fund.fund_code"
                  class="suggestion-item"
                  @click="selectFund(fund)"
                >
                  <span class="fund-code">{{ fund.fund_code }}</span>
                  <span class="fund-name">{{ fund.fund_name }}</span>
                </div>
              </div>
            </div>
          </el-form-item>

          <!-- Frequency -->
          <el-form-item label="定投频率" required>
            <el-select v-model="formData.frequency" placeholder="选择频率">
              <el-option
                v-for="opt in frequencyOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>

          <!-- Amount -->
          <el-form-item label="每期金额(元)" required>
            <el-input-number
              v-model="formData.amount"
              :min="1"
              :step="100"
              :precision="0"
              controls-position="right"
              inputmode="numeric"
              autocomplete="off"
              enterkeyhint="next"
              @focus="handleNumericInputFocus"
            />
          </el-form-item>

          <!-- Start Date -->
          <el-form-item label="开始日期" required>
            <el-date-picker
              v-model="formData.start_date"
              type="date"
              placeholder="选择开始日期"
              value-format="YYYY-MM-DD"
              :disabled-date="(time: Date) => time.getTime() > Date.now()"
              @focus="handleDatePickerFocus"
            />
          </el-form-item>

          <!-- End Date -->
          <el-form-item label="结束日期">
            <el-date-picker
              v-model="formData.end_date"
              type="date"
              placeholder="默认今天"
              value-format="YYYY-MM-DD"
              :disabled-date="(time: Date) => time.getTime() > Date.now()"
              enterkeyhint="done"
              @focus="handleDatePickerFocus"
            />
          </el-form-item>

          <!-- Calculate Button -->
          <el-form-item>
            <el-button
              type="primary"
              :loading="loading"
              @click="handleCalculate"
            >
              计算
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- Result Panel -->
      <div class="result-panel">
        <!-- Empty State -->
        <div v-if="!result && !loading" class="empty-state">
          <el-icon :size="64" color="var(--text-muted)">
            <i-ep-data-analysis />
          </el-icon>
          <p>设置投资参数并点击计算</p>
        </div>

        <!-- Loading State -->
        <div v-else-if="loading" class="loading-state">
          <el-icon class="is-loading" :size="48" color="var(--brand-navy-active)">
            <i-ep-loading />
          </el-icon>
          <p>正在计算中...</p>
        </div>

        <!-- Result Content -->
        <template v-else-if="result">
          <!-- Summary Cards -->
          <div class="summary-cards">
            <div class="summary-card">
              <div class="card-label">总投入</div>
              <div class="card-value">{{ formatCurrency(result.total_investment) }}</div>
            </div>
            <div class="summary-card">
              <div class="card-label">当前价值</div>
              <div class="card-value">{{ formatCurrency(result.current_value) }}</div>
            </div>
            <div class="summary-card">
              <div class="card-label">收益率</div>
              <div class="card-value" :class="getValueClass(result.return_rate)">
                {{ formatPercent(result.return_rate) }}
              </div>
            </div>
            <div class="summary-card">
              <div class="card-label">最大回撤</div>
              <div class="card-value text-down">
                {{ formatPercent(-Math.abs(result.max_drawdown)) }}
              </div>
            </div>
          </div>

          <!-- Additional Stats -->
          <div class="stats-row">
            <div class="stat-item">
              <span class="stat-label">投资期数</span>
              <span class="stat-value">{{ result.periods }} 期</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">持有份额</span>
              <span class="stat-value">{{ formatNumber(result.units_total) }} 份</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">波动率</span>
              <span class="stat-value">{{ formatPercent(result.volatility) }}</span>
            </div>
          </div>

          <!-- Comparison Section -->
          <div class="comparison-section">
            <div class="panel-header">
              <h3>定投 vs 一次性投入</h3>
            </div>
            <div class="comparison-cards">
              <div class="compare-card">
                <div class="compare-label">定投收益</div>
                <div class="compare-value" :class="getValueClass(result.return_rate)">
                  {{ formatPercent(result.return_rate) }}
                </div>
              </div>
              <div class="compare-vs">VS</div>
              <div class="compare-card">
                <div class="compare-label">一次性投入</div>
                <div class="compare-value" :class="getValueClass(result.lump_sum_comparison.return_rate)">
                  {{ formatPercent(result.lump_sum_comparison.return_rate) }}
                </div>
              </div>
            </div>
          </div>

          <!-- Chart Section -->
          <div class="chart-section">
            <div class="panel-header">
              <h3>净值走势曲线</h3>
            </div>
            <div ref="chartRef" class="chart-container" />
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.aip-calculator {
  padding: var(--spacing-md);
  min-height: calc(100vh - 100px); /* Fallback for older browsers */
  min-height: calc(100dvh - 100px);
}

.page-header {
  margin-bottom: var(--spacing-lg);
}

.page-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-xs);
}

.subtitle {
  font-size: 14px;
  color: var(--text-muted);
}

.calc-container {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: var(--spacing-lg);
  align-items: start;
}

/* Form Panel */
.form-panel {
  background: var(--bg-card);
  border-radius: 8px;
  padding: var(--spacing-md);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  position: sticky;
  top: var(--spacing-md);
}

.panel-header {
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-sm);
  border-bottom: 1px solid var(--border-line);
}

.panel-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.calc-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

/* Fund Search Autocomplete */
.fund-search-wrapper {
  position: relative;
  width: 100%;
}

.suggestions-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: var(--bg-card);
  border: 1px solid var(--border-line);
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  max-height: 240px;
  overflow-y: auto;
  z-index: var(--z-dropdown);
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  cursor: pointer;
  transition: background-color 0.2s;
}

.suggestion-item:hover {
  background-color: var(--bg-system);
}

.suggestion-item .fund-code {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  min-width: 70px;
}

.suggestion-item .fund-name {
  font-size: 13px;
  color: var(--text-regular);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Result Panel */
.result-panel {
  background: var(--bg-card);
  border-radius: 8px;
  padding: var(--spacing-lg);
  min-height: 600px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.empty-state,
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: var(--text-muted);
}

.empty-state p,
.loading-state p {
  margin-top: var(--spacing-md);
  font-size: 14px;
}

/* Summary Cards */
.summary-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.summary-card {
  background: var(--bg-system);
  border-radius: 6px;
  padding: var(--spacing-md);
  text-align: center;
}

.card-label {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: var(--spacing-xs);
}

.card-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

/* Stats Row */
.stats-row {
  display: flex;
  gap: var(--spacing-xl);
  padding: var(--spacing-md);
  background: var(--bg-system);
  border-radius: 6px;
  margin-bottom: var(--spacing-lg);
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted);
}

.stat-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

/* Comparison Section */
.comparison-section {
  margin-bottom: var(--spacing-lg);
}

.comparison-cards {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.compare-card {
  flex: 1;
  background: var(--bg-system);
  border-radius: 6px;
  padding: var(--spacing-lg);
  text-align: center;
}

.compare-label {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: var(--spacing-xs);
}

.compare-value {
  font-size: 28px;
  font-weight: 700;
}

.compare-vs {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-muted);
}

/* Chart Section */
.chart-section {
  margin-top: var(--spacing-lg);
}

.chart-container {
  width: 100%;
  height: 400px;
}

/* Responsive */
@media (max-width: 1200px) {
  .summary-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 900px) {
  .calc-container {
    grid-template-columns: 1fr;
  }

  .form-panel {
    position: static;
  }
}

@media (max-width: 600px) {
  .summary-cards {
    grid-template-columns: 1fr;
  }

  .stats-row {
    flex-wrap: wrap;
    gap: var(--spacing-md);
  }

  .comparison-cards {
    flex-direction: column;
  }

  .compare-vs {
    transform: rotate(90deg);
  }
}
</style>
