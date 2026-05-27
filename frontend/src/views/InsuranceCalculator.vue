<script setup lang="ts">
import { ref, computed, onMounted, nextTick, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { calculateInsurance, type InsurancePolicyRequest, type InsuranceCalculateResponse } from '@/api/insurance'

// Form state
const formData = ref<InsurancePolicyRequest>({
  premium: 10000,
  payment_years: 20,
  age: 30,
  gender: 'M',
  projection_years: 30,
  assumed_growth: 3.5
})

// Result state
const result = ref<InsuranceCalculateResponse | null>(null)
const loading = ref(false)

// Chart ref
const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

// Payment years options
const paymentYearsOptions = [
  { label: '10年', value: 10 },
  { label: '15年', value: 15 },
  { label: '20年', value: 20 },
  { label: '30年', value: 30 }
]

// Gender options
const genderOptions = [
  { label: '男', value: 'M' },
  { label: '女', value: 'F' }
]

// Growth rate options
const growthRateOptions = [
  { label: '3.0%', value: 3.0 },
  { label: '3.5%', value: 3.5 },
  { label: '4.0%', value: 4.0 },
  { label: '4.5%', value: 4.5 },
  { label: '5.0%', value: 5.0 }
]

// LocalStorage key
const STORAGE_KEY = 'insuranceCalcLastParams'

// Form validation
const validateForm = (): boolean => {
  if (formData.value.premium < 1000) {
    ElMessage.warning('年交保费最低1000元')
    return false
  }
  if (formData.value.age < 18 || formData.value.age > 70) {
    ElMessage.warning('投保年龄需在18-70岁之间')
    return false
  }
  return true
}

// Calculate insurance projection
const handleCalculate = async () => {
  if (!validateForm()) return

  loading.value = true
  try {
    const response = await calculateInsurance(formData.value)
    result.value = response

    // Save to localStorage
    localStorage.setItem(STORAGE_KEY, JSON.stringify(formData.value))

    // Render chart
    await nextTick()
    renderChart()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { detail?: string } } }
    ElMessage.error(err?.response?.data?.detail || '计算失败，请重试')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// Load last calculation from localStorage
const loadLastCalculation = () => {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved) {
    try {
      const parsed = JSON.parse(saved) as InsurancePolicyRequest
      formData.value = { ...formData.value, ...parsed }
      ElMessage.success('已加载上次计算参数')
    } catch {
      console.warn('Failed to load saved params')
    }
  }
}

// Format currency
const formatCurrency = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return '-'
  return `¥${val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

// Format percent
const formatPercent = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return '-'
  const sign = val >= 0 ? '+' : ''
  return `${sign}${val.toFixed(2)}%`
}

// Get value class
const getValueClass = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return ''
  return val >= 0 ? 'text-up' : 'text-down'
}

// Render cash value chart
const renderChart = () => {
  if (!chartRef.value || !result.value) return

  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  const projections = result.value.projections
  const breakEvenYear = result.value.break_even_year

  // Build markLine for break-even year
  const markLineData = breakEvenYear
    ? [
        {
          name: '回本年',
          xAxis: `第${breakEvenYear}年`,
          lineStyle: { color: '#52c41a', type: 'dashed' as const, width: 2 },
          label: { formatter: '回本点', position: 'end' as const }
        }
      ]
    : []

  const option = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = params as Array<{ axisValue: string; data: number; seriesName: string }>
        const yearNum = parseInt(p[0].axisValue.replace('第', '').replace('年', ''))
        const item = projections.find(d => d.year === yearNum)
        if (!item) return ''
        return `
          <div style="padding: 8px;">
            <div style="font-weight: 600; margin-bottom: 4px;">第${item.year}年</div>
            <div>累计保费: ${formatCurrency(item.premium_paid)}</div>
            <div>现金价值: ${formatCurrency(item.cash_value)}</div>
            <div>身故保额: ${formatCurrency(item.death_benefit)}</div>
            <div>IRR: ${item.irr !== null ? formatPercent(item.irr) : '-'}</div>
          </div>
        `
      }
    },
    legend: {
      data: ['累计保费', '现金价值', '身故保额'],
      bottom: 0,
      textStyle: { color: 'var(--text-regular)', fontSize: 12 }
    },
    grid: {
      left: 60,
      right: 40,
      top: 40,
      bottom: 60
    },
    xAxis: {
      type: 'category',
      data: projections.map(d => `第${d.year}年`),
      axisLabel: {
        color: 'var(--text-muted)',
        fontSize: 11,
        interval: 4
      },
      axisLine: { lineStyle: { color: 'var(--border-line)' } }
    },
    yAxis: {
      type: 'value',
      name: '金额(元)',
      axisLabel: {
        color: 'var(--text-muted)',
        fontSize: 11,
        formatter: (value: number) => {
          if (value >= 10000) return `${(value / 10000).toFixed(0)}万`
          return value.toString()
        }
      },
      axisLine: { lineStyle: { color: 'var(--border-line)' } },
      splitLine: { lineStyle: { color: 'var(--border-line)', type: 'dashed' } }
    },
    series: [
      {
        name: '累计保费',
        type: 'line' as const,
        data: projections.map(d => d.premium_paid),
        smooth: true,
        lineStyle: { color: '#0066cc', width: 2 },
        areaStyle: {
          color: {
            type: 'linear' as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(0, 102, 204, 0.1)' },
              { offset: 1, color: 'rgba(0, 102, 204, 0)' }
            ]
          }
        }
      },
      {
        name: '现金价值',
        type: 'line' as const,
        data: projections.map(d => d.cash_value),
        smooth: true,
        lineStyle: { color: '#52c41a', width: 2 },
        markLine: {
          silent: true,
          data: markLineData
        }
      },
      {
        name: '身故保额',
        type: 'line' as const,
        data: projections.map(d => d.death_benefit),
        smooth: true,
        lineStyle: { color: '#fa8c16', width: 2, type: 'dashed' }
      }
    ]
  }

  chart.setOption(option)
}

// Handle window resize
const handleResize = () => {
  chart?.resize()
}

// Computed: Latest year data
const latestProjection = computed(() => {
  if (!result.value?.projections.length) return null
  return result.value.projections[result.value.projections.length - 1]
})

onMounted(() => {
  loadLastCalculation()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})
</script>

<template>
  <div class="insurance-calculator">
    <div class="page-header">
      <h2>保险利益测算器</h2>
      <p class="subtitle">计算保险现金价值增长与内部收益率(IRR)，了解回本时间</p>
    </div>

    <div class="calc-container">
      <!-- Form Panel -->
      <div class="form-panel">
        <div class="panel-header">
          <h3>投保参数</h3>
        </div>

        <el-form label-position="top" class="calc-form">
          <!-- Premium -->
          <el-form-item label="年交保费(元)" required>
            <el-input-number
              v-model="formData.premium"
              :min="1000"
              :max="100000"
              :step="1000"
              :precision="0"
              controls-position="right"
              inputmode="numeric"
              autocomplete="off"
              enterkeyhint="next"
            />
          </el-form-item>

          <!-- Payment Years -->
          <el-form-item label="交费年期" required>
            <el-select v-model="formData.payment_years" placeholder="选择交费年期">
              <el-option
                v-for="opt in paymentYearsOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>

          <!-- Age -->
          <el-form-item label="投保年龄" required>
            <el-input-number
              v-model="formData.age"
              :min="18"
              :max="70"
              :step="1"
              controls-position="right"
              inputmode="numeric"
              autocomplete="off"
              enterkeyhint="next"
            />
          </el-form-item>

          <!-- Gender -->
          <el-form-item label="性别" required>
            <el-radio-group v-model="formData.gender">
              <el-radio-button
                v-for="opt in genderOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>

          <!-- Assumed Growth -->
          <el-form-item label="假设年化收益率">
            <el-select v-model="formData.assumed_growth" placeholder="选择收益率">
              <el-option
                v-for="opt in growthRateOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>

          <!-- Projection Years -->
          <el-form-item label="测算年限">
            <el-input-number
              v-model="formData.projection_years"
              :min="10"
              :max="50"
              :step="5"
              controls-position="right"
              inputmode="numeric"
              autocomplete="off"
              enterkeyhint="done"
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
            <i-ep-calculator />
          </el-icon>
          <p>设置投保参数并点击计算</p>
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
          <!-- Break-even Highlight -->
          <div v-if="result.break_even_year" class="break-even-banner">
            <el-icon :size="24" color="#52c41a">
              <i-ep-circle-check-filled />
            </el-icon>
            <span class="banner-text">
              回本年份: <strong>第{{ result.break_even_year }}年</strong>
              <span class="banner-hint">现金价值超过累计保费</span>
            </span>
          </div>
          <div v-else class="break-even-banner warning">
            <el-icon :size="24" color="#fa8c16">
              <i-ep-warning-filled />
            </el-icon>
            <span class="banner-text">
              在{{ formData.projection_years }}年内未能回本
            </span>
          </div>

          <!-- Summary Cards -->
          <div class="summary-cards">
            <div class="summary-card">
              <div class="card-label">累计保费</div>
              <div class="card-value">{{ formatCurrency(latestProjection?.premium_paid) }}</div>
            </div>
            <div class="summary-card">
              <div class="card-label">现金价值</div>
              <div class="card-value">{{ formatCurrency(latestProjection?.cash_value) }}</div>
            </div>
            <div class="summary-card">
              <div class="card-label">身故保额</div>
              <div class="card-value">{{ formatCurrency(latestProjection?.death_benefit) }}</div>
            </div>
            <div class="summary-card">
              <div class="card-label">IRR</div>
              <div class="card-value" :class="getValueClass(latestProjection?.irr)">
                {{ formatPercent(latestProjection?.irr) }}
              </div>
            </div>
          </div>

          <!-- Chart Section -->
          <div class="chart-section">
            <div class="panel-header">
              <h3>现金价值增长曲线</h3>
            </div>
            <div ref="chartRef" class="chart-container" />
          </div>

          <!-- Projection Table -->
          <div class="table-section">
            <div class="panel-header">
              <h3>现金价值明细表</h3>
            </div>
            <el-table :data="result.projections" stripe max-height="400">
              <el-table-column prop="year" label="保单年度" width="100" align="center">
                <template #default="{ row }">
                  <span :class="{ 'break-even': row.year === result?.break_even_year }">
                    第{{ row.year }}年
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="premium_paid" label="累计保费" align="right">
                <template #default="{ row }">
                  {{ formatCurrency(row.premium_paid) }}
                </template>
              </el-table-column>
              <el-table-column prop="cash_value" label="现金价值" align="right">
                <template #default="{ row }">
                  <span :class="{ 'text-up': row.cash_value >= row.premium_paid }">
                    {{ formatCurrency(row.cash_value) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="death_benefit" label="身故保额" align="right">
                <template #default="{ row }">
                  {{ formatCurrency(row.death_benefit) }}
                </template>
              </el-table-column>
              <el-table-column prop="irr" label="IRR" align="right" width="100">
                <template #default="{ row }">
                  <span :class="getValueClass(row.irr)">
                    {{ formatPercent(row.irr) }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.insurance-calculator {
  padding: var(--spacing-md);
  min-height: calc(100vh - 100px);
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

/* Break-even Banner */
.break-even-banner {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: linear-gradient(135deg, rgba(82, 196, 26, 0.1), rgba(82, 196, 26, 0.05));
  border-radius: 6px;
  margin-bottom: var(--spacing-lg);
  border: 1px solid rgba(82, 196, 26, 0.2);
}

.break-even-banner.warning {
  background: linear-gradient(135deg, rgba(250, 140, 22, 0.1), rgba(250, 140, 22, 0.05));
  border-color: rgba(250, 140, 22, 0.2);
}

.banner-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.banner-hint {
  font-size: 12px;
  color: var(--text-muted);
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

/* Chart Section */
.chart-section {
  margin-bottom: var(--spacing-lg);
}

.chart-container {
  width: 100%;
  height: 400px;
}

/* Table Section */
.table-section {
  margin-top: var(--spacing-lg);
}

.break-even {
  font-weight: 700;
  color: #52c41a;
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
}
</style>
