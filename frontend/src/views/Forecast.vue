<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import type { EChartsOption } from 'echarts'
import {
  getForecast,
  type ForecastData,
} from '@/api/analytics'

// Index universe for the selector (must match backend INDEX_SYMBOLS).
const INDEX_OPTIONS = [
  { code: '000300', name: '沪深300' },
  { code: '000001', name: '上证指数' },
  { code: '000905', name: '中证500' },
  { code: '000852', name: '中证1000' },
  { code: '399006', name: '创业板指' },
  { code: '000016', name: '上证50' },
  { code: '000688', name: '科创50' },
]

const selectedIndex = ref('000300')
const horizon = ref(20)
const lookback = ref(500)
const withLlm = ref(false)

const loading = ref(false)
const llmLoading = ref(false)
const forecast = ref<ForecastData | null>(null)
const errorMsg = ref<string | null>(null)

const fetchForecast = async (useLlm = withLlm.value) => {
  loading.value = true
  errorMsg.value = null
  if (useLlm) llmLoading.value = true
  try {
    const data = await getForecast(selectedIndex.value, horizon.value, lookback.value, useLlm)
    if (data) {
      forecast.value = data
    } else {
      forecast.value = null
      errorMsg.value = '该指数本次预测数据不可用（上游行情不可达），未使用任何模拟数据。'
    }
  } catch {
    forecast.value = null
    errorMsg.value = '请求失败：后端或上游数据源不可用。'
  } finally {
    loading.value = false
    llmLoading.value = false
  }
}

const runWithLlm = async () => {
  withLlm.value = true
  await fetchForecast(true)
  if (forecast.value && !forecast.value.llm.available) {
    if (forecast.value.llm.error === 'llm_not_configured') {
      ElMessage.info('未配置 LLM 密钥，AI 解读不可用（数值预测仍然有效）。')
    } else if (forecast.value.llm.error) {
      ElMessage.warning(`AI 解读暂不可用：${forecast.value.llm.error}`)
    }
  }
}

const regimeLabel = (regime: string): string => {
  const map: Record<string, string> = {
    trending: '趋势型',
    mean_reverting: '均值回归型',
    random_walk: '随机游走型',
    unknown: '未知',
  }
  const base = map[regime.replace('_high_vol', '')] ?? regime
  return regime.includes('high_vol') ? `${base} · 高波动` : base
}

const pct = (v: number | null | undefined, digits = 2): string =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : `${(v * 100).toFixed(digits)}%`

const num = (v: number | null | undefined, digits = 4): string =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : v.toFixed(digits)

const forecastChartOption = computed<EChartsOption>(() => {
  const f = forecast.value
  if (!f) return {}
  const q = f.projection.quantiles
  const dates = ['当前', ...f.projection.dates]
  return {
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['乐观 (P90)', '偏乐观 (P75)', '中位 (P50)', '偏悲观 (P25)', '悲观 (P10)'],
      top: 0,
    },
    grid: { left: 60, right: 20, top: 40, bottom: 40 },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: { type: 'value', scale: true, name: '点位' },
    series: [
      { name: '悲观 (P10)', type: 'line', data: q.p10, lineStyle: { width: 1 }, showSymbol: false, color: '#c0392b' },
      { name: '偏悲观 (P25)', type: 'line', data: q.p25, lineStyle: { width: 1, type: 'dashed' }, showSymbol: false, color: '#e67e22' },
      { name: '中位 (P50)', type: 'line', data: q.p50, lineStyle: { width: 3 }, showSymbol: false, color: '#1565C0' },
      { name: '偏乐观 (P75)', type: 'line', data: q.p75, lineStyle: { width: 1, type: 'dashed' }, showSymbol: false, color: '#27ae60' },
      { name: '乐观 (P90)', type: 'line', data: q.p90, lineStyle: { width: 1 }, showSymbol: false, color: '#16a085' },
    ],
  }
})

onMounted(() => fetchForecast(false))
</script>

<template>
  <div class="forecast-page">
    <div class="page-header">
      <h1>指数走势分析与预测</h1>
      <p class="subtitle">
        基于真实日线序列的客观经济模型：历史漂移 + 均值回归，输出经验分位路径带。
        所有数字由服务端计算，未使用任何模拟数据。
      </p>
    </div>

    <el-card class="control-card">
      <div class="controls">
        <div class="control">
          <label>标的</label>
          <el-select v-model="selectedIndex" style="width: 160px" @change="fetchForecast">
            <el-option v-for="o in INDEX_OPTIONS" :key="o.code" :label="o.name" :value="o.code" />
          </el-select>
        </div>
        <div class="control">
          <label>预测天数</label>
          <el-input-number v-model="horizon" :min="1" :max="120" @change="fetchForecast" />
        </div>
        <div class="control">
          <label>估计回看</label>
          <el-input-number v-model="lookback" :min="60" :max="2500" :step="100" @change="fetchForecast" />
        </div>
        <el-button type="primary" :loading="loading" @click="fetchForecast(false)">重新计算</el-button>
        <el-button :loading="llmLoading" @click="runWithLlm">AI 解读</el-button>
      </div>
    </el-card>

    <SkeletonLoader v-if="loading" :rows="6" />

    <el-alert
      v-else-if="errorMsg"
      :title="errorMsg"
      type="warning"
      show-icon
      :closable="false"
    />

    <template v-else-if="forecast">
      <div class="metrics-grid">
        <div class="metric">
          <span class="label">最新收盘</span>
          <span class="value">{{ num(forecast.last_close, 2) }}</span>
          <span class="hint">as of {{ forecast.as_of }} · {{ forecast.observations }} 个样本</span>
        </div>
        <div class="metric">
          <span class="label">年化漂移</span>
          <span class="value">{{ pct(forecast.metrics.annualised_drift) }}</span>
          <span class="hint">近 {{ forecast.observations }} 日对数收益</span>
        </div>
        <div class="metric">
          <span class="label">年化波动率</span>
          <span class="value">{{ pct(forecast.metrics.annualised_volatility) }}</span>
          <span class="hint">252 交易日年化</span>
        </div>
        <div class="metric">
          <span class="label">最大回撤</span>
          <span class="value">{{ pct(forecast.metrics.max_drawdown) }}</span>
          <span class="hint">样本内</span>
        </div>
        <div class="metric">
          <span class="label">Hurst (DFA)</span>
          <span class="value">{{ num(forecast.metrics.hurst, 3) }}</span>
          <span class="hint">0.5=随机游走</span>
        </div>
        <div class="metric">
          <span class="label">状态判定</span>
          <span class="value">{{ regimeLabel(forecast.metrics.regime) }}</span>
          <span class="hint">偏离 {{ num(forecast.metrics.valuation_z, 2) }}σ</span>
        </div>
      </div>

      <el-card class="chart-card">
        <template #header>
          <div class="card-header">
            <span>{{ forecast.index_name }} · 未来 {{ forecast.horizon_days }} 个交易日分位路径</span>
            <span class="band-summary">
              中位 {{ pct(forecast.expected_band.median_return) }} ·
              上行概率 {{ pct(forecast.expected_band.prob_up) }}
            </span>
          </div>
        </template>
        <EChartsWrapper :option="forecastChartOption" height="420px" />
      </el-card>

      <el-card class="model-card">
        <template #header><span>模型构成</span></template>
        <el-table :data="forecast.model.components" size="small">
          <el-table-column prop="name" label="分量" width="180" />
          <el-table-column prop="weight" label="权重" width="90" />
          <el-table-column label="年化漂移" width="120">
            <template #default="{ row }">{{ pct(row.annualised_drift) }}</template>
          </el-table-column>
          <el-table-column prop="rationale" label="依据" />
        </el-table>
        <p class="blended">
          合成日漂移：{{ num(forecast.model.blended_daily_drift, 6) }}
          （已钳制在 ±3 倍样本日波动以内）
        </p>
      </el-card>

      <el-card class="llm-card">
        <template #header>
          <div class="card-header">
            <span>AI 解读</span>
            <el-tag v-if="forecast.llm.enabled" size="small" type="success">
              {{ forecast.llm.model }} · {{ forecast.llm.api_style }}
            </el-tag>
            <el-tag v-else size="small" type="info">未配置</el-tag>
          </div>
        </template>
        <div v-if="forecast.llm.available" class="llm-text">{{ forecast.llm.text }}</div>
        <el-alert
          v-else
          :title="`AI 解读不可用：${forecast.llm.error ?? '未知原因'}`"
          type="info"
          :closable="false"
          show-icon
        />
      </el-card>

      <div class="notes-grid">
        <el-card>
          <template #header><span>口径（basis）</span></template>
          <ul><li v-for="(b, i) in forecast.basis" :key="i">{{ b }}</li></ul>
        </el-card>
        <el-card>
          <template #header><span>局限（limits）</span></template>
          <ul><li v-for="(l, i) in forecast.limits" :key="i">{{ l }}</li></ul>
        </el-card>
      </div>
    </template>
  </div>
</template>

<style scoped>
.forecast-page { padding: 20px; max-width: 1200px; margin: 0 auto; }
.page-header h1 { font-size: 24px; margin-bottom: 8px; }
.subtitle { color: var(--ink-soft, #5a6b87); font-size: 13px; line-height: 1.6; }
.control-card { margin: 16px 0; }
.controls { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; }
.control { display: flex; flex-direction: column; gap: 4px; }
.control label { font-size: 12px; color: var(--ink-soft, #5a6b87); }
.metrics-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px; margin: 16px 0;
}
.metric {
  background: var(--surface, #fff); border: 1px solid var(--line, #d9e2ef);
  border-radius: 12px; padding: 12px 14px; display: flex; flex-direction: column; gap: 4px;
}
.metric .label { font-size: 12px; color: var(--ink-soft, #5a6b87); }
.metric .value { font-size: 20px; font-weight: 600; }
.metric .hint { font-size: 11px; color: var(--ink-soft, #8494ad); }
.chart-card, .model-card, .llm-card { margin: 16px 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.band-summary { font-size: 13px; color: var(--ink-soft, #5a6b87); }
.blended { margin-top: 10px; font-size: 13px; color: var(--ink-soft, #5a6b87); }
.llm-text { white-space: pre-wrap; line-height: 1.8; font-size: 14px; }
.notes-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; }
.notes-grid ul { margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.8; color: var(--ink-soft, #5a6b87); }
</style>
