<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getBondYieldCurve, getMoneyMarketRates, getRateHistory } from '@/api/market'
import api from '@/api/index'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import type { EChartsOption } from 'echarts'

// ==================== Types ====================
interface YieldCurvePoint {
  tenor: number
  yield_ytm: number
}

interface YieldCurveData {
  [date: string]: YieldCurvePoint[]
}

interface MoneyRateItem {
  rate_code: string
  trade_date: string
  rate_value: number
  sparkline_data: string | null
  sparklineOption?: EChartsOption
  isSimulated?: boolean
}

interface CreditSpreadItem {
  bond_category: string
  rating: string
  tenor: string
  trade_date: string
  benchmark_type: string
  yield_ytm: number
  credit_spread: number
  percentile_rank: number
}

interface BondIssuanceItem {
  bond_type: string
  issuance_amount: number
  issuance_count: number
}

// ==================== State ====================
const loading = ref(false)
const activeTab = ref('yield')

// Yield curve data - 国债与国开债分开存储
const treasuryCurveData = ref<YieldCurveData>({})
const cdbCurveData = ref<YieldCurveData>({})
const selectedDate = ref<string>('')
const yieldCurveError = ref(false)
const availableDates = computed(() => {
  const all = new Set([
    ...Object.keys(treasuryCurveData.value),
    ...Object.keys(cdbCurveData.value),
  ])
  return Array.from(all).sort().reverse()
})

// Credit spread data
const creditSpreadData = ref<CreditSpreadItem[]>([])

// Money market rates
const moneyRates = ref<MoneyRateItem[]>([])

// Bond issuance data
const issuanceData = ref<BondIssuanceItem[]>([])

// Chart refs
const yieldChart = ref<echarts.ECharts | null>(null)
const spreadChart = ref<echarts.ECharts | null>(null)
const issuanceChart = ref<echarts.ECharts | null>(null)

// DOM refs
const yieldChartRef = ref<HTMLElement | null>(null)
const spreadChartRef = ref<HTMLElement | null>(null)
const issuanceChartRef = ref<HTMLElement | null>(null)

// Tenor labels for display
const tenorLabels: Record<number, string> = {
  0.083: '1M',
  0.25: '3M',
  0.5: '6M',
  1: '1Y',
  2: '2Y',
  3: '3Y',
  5: '5Y',
  7: '7Y',
  10: '10Y',
  20: '20Y',
  30: '30Y',
}

const tenorOrder = [0.083, 0.25, 0.5, 1, 2, 3, 5, 7, 10, 20, 30]

// Rate code labels
const rateLabels: Record<string, string> = {
  // Live SHIBOR tenors (quote_sources.fetch_money_market_rates)
  'O/N': 'SHIBOR 隔夜',
  '1W': 'SHIBOR 1周',
  '2W': 'SHIBOR 2周',
  '1M': 'SHIBOR 1月',
  '3M': 'SHIBOR 3月',
  '6M': 'SHIBOR 6月',
  '9M': 'SHIBOR 9月',
  '1Y': 'SHIBOR 1年',
  // Legacy frozen-table codes, kept so an old cached payload still renders.
  'DR007': 'DR007',
  'SHIBOR_ON': 'SHIBOR隔夜',
  'SHIBOR_1W': 'SHIBOR1周',
  'SHIBOR_1M': 'SHIBOR1月',
  'SHIBOR_3M': 'SHIBOR3月',
  'LPR_1Y': 'LPR1年',
  'LPR_5Y': 'LPR5年',
}

// Format percentage
const formatPct = (val: number | null, decimals = 2): string => {
  if (val === null || val === undefined) return '-'
  return `${val.toFixed(decimals)}%`
}

// Format issuance amount
const formatAmount = (val: number): string => {
  if (val >= 10000) {
    return `${(val / 10000).toFixed(2)}万亿`
  }
  return `${val.toFixed(0)}亿`
}

// ==================== Fetch Data ====================
const fetchYieldCurve = async () => {
  yieldCurveError.value = false
  try {
    // Fetch both 国债 and 国开债 separately so each curve is populated honestly
    const [treasuryData, cdbData] = await Promise.all([
      getBondYieldCurve('国债'),
      getBondYieldCurve('国开'),
    ])
    
    treasuryCurveData.value = treasuryData ?? {}
    cdbCurveData.value = cdbData ?? {}
    
    if (availableDates.value.length > 0) {
      // 保留当前选择，若无效则回退到最新日期
      if (!availableDates.value.includes(selectedDate.value)) {
        selectedDate.value = availableDates.value[0]
      }
    } else {
      selectedDate.value = ''
    }
  } catch (error) {
    // 记录错误并在曲线卡片中显示，而非静默吞掉
    yieldCurveError.value = true
    treasuryCurveData.value = {}
    cdbCurveData.value = {}
  }
}

const fetchCreditSpread = async () => {
  try {
    const response = await api.get<CreditSpreadItem[]>('/market/bond/credit-spread')
    // Assign the payload, never the `{ data, _meta }` envelope (see
    // fetchIssuanceData): a non-array reaching el-table throws.
    creditSpreadData.value = Array.isArray(response.data) ? response.data : []
  } catch (error) {
    creditSpreadData.value = []
  }
}

const fetchMoneyRates = async () => {
  try {
    const response = await getMoneyMarketRates()
    moneyRates.value = response
    
    // Fetch sparkline data for each rate in parallel (avoid N+1 serial awaits)
    const histories = await Promise.all(
      moneyRates.value.map(rate =>
        getRateHistory(rate.rate_code, 30).catch(() => null)
      )
    )
    moneyRates.value.forEach((rate, i) => {
      const historyResponse = histories[i]
      if (historyResponse && historyResponse.values.length > 0) {
        rate.isSimulated = historyResponse.is_simulated
        rate.sparklineOption = createSparklineOption(historyResponse.values)
      } else {
        rate.sparklineOption = undefined
      }
    })
  } catch (error) {
    moneyRates.value = []
  }
}

// Create sparkline option from rate values
const createSparklineOption = (values: number[]): EChartsOption => {
  const firstValue = values[0]
  const lastValue = values[values.length - 1]
  const isUp = lastValue >= firstValue
  const lineColor = isUp ? '#2E7D32' : '#E63935'
  
  return {
    xAxis: { type: 'category' as const, show: false },
    yAxis: { type: 'value' as const, show: false },
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    series: [{
      type: 'line' as const,
      data: values,
      lineStyle: { color: lineColor, width: 1.5 },
      areaStyle: {
        color: {
          type: 'linear' as const,
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: isUp ? 'rgba(46, 125, 50, 0.3)' : 'rgba(230, 57, 53, 0.3)' },
            { offset: 1, color: 'rgba(255, 255, 255, 0)' }
          ]
        }
      },
      symbol: 'none',
    }]
  }
}

const fetchIssuanceData = async () => {
  try {
    const response = await api.get<BondIssuanceItem[]>('/market/bond/issuance')
    // `.data` is required: assigning the whole `{ data, _meta }` envelope made
    // el-table receive a non-iterable object, which threw "e is not iterable"
    // inside updateAllSelected and blanked the page behind the ErrorBoundary.
    const rows = Array.isArray(response.data) ? response.data : []
    issuanceData.value = rows
  } catch (error) {
    issuanceData.value = []
  }
}

// ==================== Charts ====================
const initYieldChart = () => {
  if (!yieldChartRef.value || !selectedDate.value) return

  if (yieldChart.value) {
    yieldChart.value.dispose()
  }

  yieldChart.value = echarts.init(yieldChartRef.value)
  
  // 国债与国开债分别取自各自接口，避免用同一份数据伪造两条曲线
  const treasuryCurve: [number, number][] = []
  const cdbCurve: [number, number][] = []
  
  const treasuryData = treasuryCurveData.value[selectedDate.value] || []
  const cdbData = cdbCurveData.value[selectedDate.value] || []
  
  treasuryData.forEach((point: YieldCurvePoint) => {
    treasuryCurve.push([point.tenor, point.yield_ytm])
  })
  cdbData.forEach((point: YieldCurvePoint) => {
    cdbCurve.push([point.tenor, point.yield_ytm])
  })
  
  // 仅当对应数据存在时才绘制该序列，避免空序列进入图例
  const series: any[] = []
  if (treasuryCurve.length > 0) {
    series.push({
      name: '国债',
      type: 'line',
      data: treasuryCurve.map(d => d[1]),
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { color: '#003399', width: 2 },
      itemStyle: { color: '#003399' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(0, 51, 153, 0.15)' },
          { offset: 1, color: 'rgba(0, 51, 153, 0.02)' },
        ]),
      },
    })
  }
  if (cdbCurve.length > 0) {
    series.push({
      name: '国开债',
      type: 'line',
      data: cdbCurve.map(d => d[1]),
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { color: '#E63935', width: 2 },
      itemStyle: { color: '#E63935' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(230, 57, 53, 0.15)' },
          { offset: 1, color: 'rgba(230, 57, 53, 0.02)' },
        ]),
      },
    })
  }
  
  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: 'var(--border-line)',
      borderWidth: 1,
      textStyle: { color: 'var(--text-primary)' },
      formatter: (params: unknown) => {
        const items = params as Array<{ seriesName: string; value: [number, number]; marker: string }>
        if (!items || items.length === 0) return ''
        const tenor = items[0].value[0]
        const tenorLabel = tenorLabels[tenor] || `${tenor}Y`
        let html = `<div style="padding: 8px;"><div style="font-weight: 600; margin-bottom: 8px;">期限: ${tenorLabel}</div>`
        items.forEach(item => {
          html += `<div>${item.marker} ${item.seriesName}: <strong>${item.value[1].toFixed(2)}%</strong></div>`
        })
        html += '</div>'
        return html
      },
    },
    legend: {
      data: series.map(s => (s as { name: string }).name),
      top: 10,
      textStyle: { color: 'var(--text-regular)' },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: tenorOrder.map(t => tenorLabels[t] || `${t}Y`),
      axisLine: { lineStyle: { color: 'var(--border-line)' } },
      axisLabel: { color: 'var(--text-regular)', fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '收益率(%)',
      nameTextStyle: { color: 'var(--text-muted)', fontSize: 11 },
      splitLine: { lineStyle: { color: 'var(--border-line)', type: 'dashed' } },
      axisLine: { show: false },
      axisLabel: { color: 'var(--text-regular)', fontSize: 11 },
    },
    series,
  }

  yieldChart.value.setOption(option)
}

const initSpreadChart = () => {
  if (!spreadChartRef.value) return

  if (spreadChart.value) {
    spreadChart.value.dispose()
  }

  spreadChart.value = echarts.init(spreadChartRef.value)

  // Group data by rating
  const ratings = ['AAA', 'AA+', 'AA', 'AA-']
  const tenors = ['1Y', '3Y', '5Y']
  
  const seriesData: Record<string, number[]> = {}
  ratings.forEach(rating => {
    seriesData[rating] = tenors.map(tenor => {
      const item = creditSpreadData.value.find(
        d => d.rating === rating && d.tenor === tenor
      )
      return item?.credit_spread || 0
    })
  })

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: 'var(--border-line)',
      borderWidth: 1,
      textStyle: { color: 'var(--text-primary)' },
      formatter: (params: unknown) => {
        const items = params as Array<{ seriesName: string; value: number; marker: string; axisValue: string }>
        if (!items || items.length === 0) return ''
        let html = `<div style="padding: 8px;"><div style="font-weight: 600; margin-bottom: 8px;">期限: ${items[0].axisValue}</div>`
        items.forEach(item => {
          html += `<div>${item.marker} ${item.seriesName}: <strong>${item.value.toFixed(2)}BP</strong></div>`
        })
        html += '</div>'
        return html
      },
    },
    legend: {
      data: ratings,
      top: 10,
      textStyle: { color: 'var(--text-regular)' },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: tenors,
      axisLine: { lineStyle: { color: 'var(--border-line)' } },
      axisLabel: { color: 'var(--text-regular)', fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '信用利差(BP)',
      nameTextStyle: { color: 'var(--text-muted)', fontSize: 11 },
      splitLine: { lineStyle: { color: 'var(--border-line)', type: 'dashed' } },
      axisLine: { show: false },
      axisLabel: { color: 'var(--text-regular)', fontSize: 11 },
    },
    series: ratings.map((rating, index) => ({
      name: rating,
      type: 'bar',
      data: seriesData[rating],
      barGap: '10%',
      itemStyle: {
        color: ['#003399', '#0B3CC3', '#5B8FF9', '#FF9800'][index],
        borderRadius: [2, 2, 0, 0],
      },
    })),
  }

  spreadChart.value.setOption(option)
}

const initIssuanceChart = () => {
  if (!issuanceChartRef.value) return

  if (issuanceChart.value) {
    issuanceChart.value.dispose()
  }

  issuanceChart.value = echarts.init(issuanceChartRef.value)

  const types = issuanceData.value.map(d => d.bond_type)
  const amounts = issuanceData.value.map(d => d.issuance_amount)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: 'var(--border-line)',
      borderWidth: 1,
      textStyle: { color: 'var(--text-primary)' },
      formatter: (params: unknown) => {
        const items = params as Array<{ name: string; value: number; marker: string }>
        if (!items || items.length === 0) return ''
        const item = items[0]
        return `<div style="padding: 8px;">
          <div style="font-weight: 600;">${item.name}</div>
          <div>${item.marker} 发行规模: <strong>${formatAmount(item.value)}</strong></div>
        </div>`
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '10%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: types,
      axisLine: { lineStyle: { color: 'var(--border-line)' } },
      axisLabel: { color: 'var(--text-regular)', fontSize: 11, rotate: 30 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '发行规模(亿)',
      nameTextStyle: { color: 'var(--text-muted)', fontSize: 11 },
      splitLine: { lineStyle: { color: 'var(--border-line)', type: 'dashed' } },
      axisLine: { show: false },
      axisLabel: { color: 'var(--text-regular)', fontSize: 11 },
    },
    series: [{
      type: 'bar',
      data: amounts,
      barMaxWidth: 40,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#003399' },
          { offset: 1, color: '#0B3CC3' },
        ]),
        borderRadius: [4, 4, 0, 0],
      },
      emphasis: {
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#E63935' },
            { offset: 1, color: '#FF6B6B' },
          ]),
        },
      },
    }],
  }

  issuanceChart.value.setOption(option)
}

// ==================== Lifecycle ====================
const handleResize = () => {
  yieldChart.value?.resize()
  spreadChart.value?.resize()
  issuanceChart.value?.resize()
}

// el-tabs 切换时，隐藏面板中的图表初始化为空白尺寸；切回时重新初始化/调整尺寸
const handleTabChange = (name: string | number) => {
  nextTick(() => {
    setTimeout(() => {
      if (name === 'yield') {
        if (!yieldChart.value && yieldChartRef.value) {
          initYieldChart()
        } else {
          yieldChart.value?.resize()
        }
      } else if (name === 'spread') {
        if (!spreadChart.value && spreadChartRef.value) {
          initSpreadChart()
        } else {
          spreadChart.value?.resize()
        }
      } else if (name === 'issuance') {
        if (!issuanceChart.value && issuanceChartRef.value) {
          initIssuanceChart()
        } else {
          issuanceChart.value?.resize()
        }
      }
    }, 50)
  })
}

// 日期选择变化时重新渲染收益率曲线
watch(selectedDate, () => {
  nextTick(() => {
    if (yieldChartRef.value) {
      initYieldChart()
    }
  })
})

const fetchAllData = async () => {
  loading.value = true
  try {
    await Promise.all([
      fetchYieldCurve(),
      fetchCreditSpread(),
      fetchMoneyRates(),
      fetchIssuanceData(),
    ])
    
    // Initialize charts after data is loaded
    setTimeout(() => {
      initYieldChart()
      initSpreadChart()
      initIssuanceChart()
    }, 100)
  } catch (error) {
    ElMessage.error('获取债券市场数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchAllData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  yieldChart.value?.dispose()
  spreadChart.value?.dispose()
  issuanceChart.value?.dispose()
})
</script>

<template>
  <ErrorBoundary error-message="债券市场数据加载失败">
    <div class="bond-market" v-loading="loading">
    <!-- Header -->
    <div class="page-header">
      <h2>国内债券市场总览</h2>
      <div class="header-info">
        <el-date-picker
          v-model="selectedDate"
          type="date"
          placeholder="选择日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          :clearable="false"
          style="width: 160px"
        />
      </div>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" class="market-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="收益率曲线" name="yield">
        <div class="chart-card card">
          <div class="card-title">国债与国开债收益率曲线</div>
          <div v-if="yieldCurveError" class="chart-error">收益率曲线数据加载失败，请稍后重试</div>
          <div class="chart-container" ref="yieldChartRef"></div>
          <div class="chart-legend">
            <div class="legend-item">
              <span class="legend-color" style="background: #003399;"></span>
              <span>国债</span>
            </div>
            <div class="legend-item">
              <span class="legend-color" style="background: #E63935;"></span>
              <span>国开债</span>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="信用利差" name="spread">
        <div class="chart-card card">
          <div class="card-title">信用债利差矩阵 (中票)</div>
          <div class="chart-container" ref="spreadChartRef"></div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="货币利率" name="money">
        <div class="chart-card card">
          <div class="card-title">货币市场利率</div>
          <el-table :data="moneyRates" stripe style="width: 100%">
            <el-table-column prop="rate_code" label="利率品种" width="150">
              <template #default="{ row }">
                {{ rateLabels[row.rate_code] || row.rate_code }}
              </template>
            </el-table-column>
            <el-table-column prop="trade_date" label="日期" width="120">
              <template #default="{ row }">
                {{ row.trade_date }}
              </template>
            </el-table-column>
            <el-table-column prop="rate_value" label="利率(%)" width="120">
              <template #default="{ row }">
                <span class="rate-value">{{ formatPct(row.rate_value) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="走势" min-width="200">
              <template #default="{ row }">
                <div class="sparkline">
                  <EChartsWrapper
                    v-if="row.sparklineOption"
                    :option="row.sparklineOption"
                    :is-sparkline="true"
                    height="30px"
                  />
                  <span v-else class="text-muted">暂无数据</span>
                </div>
                <span v-if="row.isSimulated && row.sparklineOption" class="simulated-badge-mini">模拟</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="发行统计" name="issuance">
        <div class="chart-card card">
          <div class="card-title">债券发行统计 (本月)</div>
          <div class="chart-container chart-height-md" ref="issuanceChartRef"></div>
          
          <!-- Summary table -->
          <div class="summary-section">
            <div class="summary-title">发行明细</div>
            <el-table :data="issuanceData" stripe size="small">
              <el-table-column prop="bond_type" label="债券类型" width="120" />
              <el-table-column prop="issuance_amount" label="发行规模(亿)" width="140">
                <template #default="{ row }">
                  {{ row.issuance_amount.toFixed(0) }}
                </template>
              </el-table-column>
              <el-table-column prop="issuance_count" label="发行数量" width="120">
                <template #default="{ row }">
                  {{ row.issuance_count }}只
                </template>
              </el-table-column>
              <el-table-column label="占比">
                <template #default="{ row }">
                  <el-progress
                    :percentage="(row.issuance_amount / issuanceData.reduce((sum, d) => sum + d.issuance_amount, 0)) * 100"
                    :stroke-width="8"
                    :show-text="false"
                  />
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-tab-pane>
      </el-tabs>
    </div>
  </ErrorBoundary>
</template>

<style scoped>
.bond-market {
  min-height: calc(100vh - 100px); /* Fallback for older browsers */
  min-height: calc(100dvh - 100px);
  padding: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-line);
}

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.market-tabs {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
}

.chart-card {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-line);
}

.chart-container {
  width: 100%;
  height: 400px;
}

.chart-error {
  padding: 10px 12px;
  margin-bottom: 12px;
  background: rgba(230, 57, 53, 0.08);
  border: 1px solid rgba(230, 57, 53, 0.3);
  border-radius: 4px;
  color: var(--market-up);
  font-size: 13px;
}

.chart-height-md {
  height: 320px;
}

.chart-legend {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border-line);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-regular);
}

.legend-color {
  width: 16px;
  height: 4px;
  border-radius: 2px;
}

.rate-value {
  font-weight: 600;
  color: var(--text-primary);
}

.text-muted {
  color: var(--text-muted);
}

.sparkline {
  height: 30px;
  display: flex;
  align-items: center;
}

.simulated-badge-mini {
  font-size: 10px;
  color: #FF8C00;
  background: rgba(255, 140, 0, 0.1);
  padding: 1px 4px;
  border-radius: 2px;
  margin-left: 4px;
}

.summary-section {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--border-line);
}

.summary-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

/* Element Plus overrides */
:deep(.el-tabs__header) {
  margin-bottom: 20px;
}

:deep(.el-tabs__item) {
  font-size: 14px;
  color: var(--text-regular);
}

:deep(.el-tabs__item.is-active) {
  color: var(--brand-navy-dark);
  font-weight: 600;
}

:deep(.el-tabs__active-bar) {
  background-color: var(--brand-navy-dark);
}

:deep(.el-table th) {
  background-color: #fafafa;
  color: var(--text-primary);
  font-weight: 600;
}

:deep(.el-progress-bar__inner) {
  background: linear-gradient(90deg, #003399, #0B3CC3);
}

/* Responsive */
@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .chart-container {
    height: 300px;
  }
}
</style>
