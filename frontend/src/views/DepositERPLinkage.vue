<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import { getERPSpread } from '@/api/analytics'

type RiskFreeType = 'deposit_1y' | 'deposit_3y' | 'deposit_5y'

interface ERPDataItem {
  index_code: string
  index_name: string
  trade_date: string
  pe_ttm: number
  treasury_yield_10y: number
  erp_spread: number
  percentile_rank_10y: number | null
  index_close_price: number | null
  risk_free_rate?: number
}

const erpData = ref<ERPDataItem[]>([])
const loading = ref(false)
const selectedIndex = ref('000300')

const riskFreeType = ref<RiskFreeType>(
  (localStorage.getItem('deposit-erp-risk-free-type') as RiskFreeType) || 'deposit_1y'
)

watch(riskFreeType, (newType) => {
  localStorage.setItem('deposit-erp-risk-free-type', newType)
})

const indexOptions = [
  { value: '000300', label: '沪深300' },
  { value: '000905', label: '中证500' },
  { value: '000852', label: '中证1000' },
  { value: '000016', label: '上证50' },
]

const riskFreeTypeLabels: Record<RiskFreeType, string> = {
  deposit_1y: '大额存款1年',
  deposit_3y: '大额存款3年',
  deposit_5y: '大额存款5年',
}

const currentERP = computed(() => {
  if (erpData.value.length === 0) return null
  return erpData.value[erpData.value.length - 1]
})

const historicalData = computed(() => {
  return erpData.value.slice(-500)
})

const statistics = computed(() => {
  const data = historicalData.value
  if (data.length === 0) return { mean: 0, std: 0, min: 0, max: 0 }
  
  const erpValues = data.map(d => d.erp_spread)
  const n = erpValues.length
  
  const mean = erpValues.reduce((sum, v) => sum + v, 0) / n
  const variance = erpValues.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / n
  const std = Math.sqrt(variance)
  
  return {
    mean,
    std,
    min: Math.min(...erpValues),
    max: Math.max(...erpValues),
  }
})

const dualAxisChartOption = computed<EChartsOption>(() => {
  const dates = historicalData.value.map(d => d.trade_date)
  const depositRates = historicalData.value.map(d => d.risk_free_rate ?? d.treasury_yield_10y)
  const erpValues = historicalData.value.map(d => d.erp_spread)
  
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: unknown) => {
        const p = params as { axisValue: string; value: number; seriesName: string }[]
        const date = p[0]?.axisValue ?? ''
        const depositRate = p.find(item => item.seriesName === '存款利率')?.value?.toFixed(2) ?? '-'
        const erp = p.find(item => item.seriesName === 'ERP收益差')?.value?.toFixed(2) ?? '-'
        return `${date}<br/>存款利率: ${depositRate}%<br/>ERP: ${erp}%`
      },
    },
    legend: {
      data: ['存款利率', 'ERP收益差'],
      top: 10,
      textStyle: { color: '#4A4A4A' },
    },
    grid: { left: '8%', right: '10%', top: '15%', bottom: '12%' },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#E5E8ED' } },
      axisLabel: { color: '#999999', fontSize: 11 },
      splitLine: { show: false },
    },
    yAxis: [
      {
        type: 'value',
        name: '存款利率 (%)',
        nameTextStyle: { color: '#4A4A4A' },
        axisLine: { show: false },
        axisLabel: { color: '#999999' },
        splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } },
      },
      {
        type: 'value',
        name: 'ERP (%)',
        nameTextStyle: { color: '#4A4A4A' },
        axisLine: { show: false },
        axisLabel: { color: '#999999' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '存款利率',
        type: 'line',
        yAxisIndex: 0,
        data: depositRates,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: '#003399' },
        areaStyle: { color: 'rgba(0, 51, 153, 0.1)' },
      },
      {
        name: 'ERP收益差',
        type: 'line',
        yAxisIndex: 1,
        data: erpValues,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: '#E63935' },
      },
    ],
  } as EChartsOption
})

const spreadCurveOption = computed<EChartsOption>(() => {
  const dates = historicalData.value.map(d => d.trade_date)
  const spreads = historicalData.value.map(d => d.erp_spread)
  
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = params as { axisValue: string; value: number }[]
        return `${p[0]?.axisValue ?? ''}<br/>ERP: ${p[0]?.value?.toFixed(2) ?? '-'}%`
      },
    },
    grid: { left: '8%', right: '5%', top: '10%', bottom: '15%' },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#E5E8ED' } },
      axisLabel: { color: '#999999', fontSize: 11 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'ERP (%)',
      nameTextStyle: { color: '#4A4A4A' },
      axisLine: { show: false },
      axisLabel: { color: '#999999' },
      splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } },
    },
    series: [
      {
        type: 'line',
        data: spreads,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2 },
        areaStyle: { color: 'rgba(11, 60, 195, 0.1)' },
      },
    ],
  } as EChartsOption
})

const fetchData = async () => {
  loading.value = true
  try {
    const response = await getERPSpread(selectedIndex.value, riskFreeType.value)
    erpData.value = response.sort((a, b) => a.trade_date.localeCompare(b.trade_date))
  } catch (error) {
    ElMessage.error('获取ERP数据失败')
  } finally {
    loading.value = false
  }
}

watch(selectedIndex, () => {
  fetchData()
})

watch(riskFreeType, () => {
  fetchData()
})

onMounted(() => {
  fetchData()
})
</script>

<template>
  <div class="deposit-erp-linkage">
    <div class="page-header">
      <h1>存款利率-ERP联动分析</h1>
      <p class="subtitle">大额存款利率与股债收益差关联研究</p>
    </div>

    <div class="selector-row">
      <span class="label">选择指数：</span>
      <el-select v-model="selectedIndex" placeholder="请选择指数" style="width: 160px">
        <el-option
          v-for="item in indexOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      
      <div class="rf-toggle">
        <span class="label">存款期限：</span>
        <el-radio-group v-model="riskFreeType" size="small">
          <el-radio-button value="deposit_1y">1年期</el-radio-button>
          <el-radio-button value="deposit_3y">3年期</el-radio-button>
          <el-radio-button value="deposit_5y">5年期</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <div class="metrics-row" v-if="currentERP">
      <div class="metric-card">
        <div class="metric-label">当前存款利率</div>
        <div class="metric-value">
          {{ (currentERP.risk_free_rate ?? currentERP.treasury_yield_10y)?.toFixed(2) ?? '-' }}%
        </div>
        <div class="metric-desc">{{ riskFreeTypeLabels[riskFreeType] }}</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">当前ERP</div>
        <div class="metric-value" :style="{ color: currentERP.erp_spread < 0 ? '#2E7D32' : '#E63935' }">
          {{ currentERP.erp_spread?.toFixed(2) ?? '-' }}%
        </div>
        <div class="metric-desc">股债收益差</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">PE(TTM)</div>
        <div class="metric-value">{{ currentERP.pe_ttm?.toFixed(2) ?? '-' }}</div>
        <div class="metric-desc">指数估值</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">历史均值</div>
        <div class="metric-value">{{ statistics.mean.toFixed(2) }}%</div>
        <div class="metric-desc">ERP均值</div>
      </div>
    </div>

    <div class="charts-container">
      <div class="chart-card full-width">
        <div class="chart-header">
          <h3>存款利率与ERP双轴图</h3>
        </div>
        <EChartsWrapper
          :option="dualAxisChartOption"
          :loading="loading"
          height="400px"
        />
      </div>

      <div class="chart-card full-width">
        <div class="chart-header">
          <h3>ERP历史曲线</h3>
        </div>
        <EChartsWrapper
          :option="spreadCurveOption"
          :loading="loading"
          height="300px"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.deposit-erp-linkage {
  padding: 16px;
  max-width: 1600px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.subtitle {
  font-size: 14px;
  color: var(--text-muted);
}

.selector-row {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}

.selector-row .label {
  font-size: 14px;
  color: var(--text-regular);
}

.rf-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.metric-card {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.metric-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.metric-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
}

.metric-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.charts-container {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.chart-card {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.chart-card.full-width {
  grid-column: 1 / -1;
}

.chart-header {
  margin-bottom: 12px;
}

.chart-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

@media (max-width: 768px) {
  .metrics-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .selector-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .rf-toggle {
    width: 100%;
  }
}
</style>
