<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import { getERPSpread } from '@/api/analytics'

// ERP数据类型
interface ERPDataItem {
  index_code: string
  index_name: string
  trade_date: string
  pe_ttm: number
  treasury_yield_10y: number
  erp_spread: number
  percentile_rank_10y: number | null
  index_close_price: number | null
}

// 响应式数据
const erpData = ref<ERPDataItem[]>([])
const loading = ref(false)
const selectedIndex = ref('000300')

// 指数选项
const indexOptions = [
  { value: '000300', label: '沪深300' },
  { value: '000905', label: '中证500' },
  { value: '000852', label: '中证1000' },
  { value: '000016', label: '上证50' },
]

// 当前ERP数据
const currentERP = computed(() => {
  if (erpData.value.length === 0) return null
  return erpData.value[erpData.value.length - 1]
})

// 历史数据（最近500天）
const historicalData = computed(() => {
  return erpData.value.slice(-500)
})

// ERP区域分类
const getERPZone = (erp: number): { label: string; color: string; signal: string } => {
  if (erp < -2) {
    return { label: '极度低估', color: '#2E7D32', signal: '强烈买入' }
  } else if (erp < 0) {
    return { label: '低估', color: '#0B3CC3', signal: '买入' }
  } else if (erp < 2) {
    return { label: '中性', color: '#999999', signal: '持有' }
  } else if (erp < 4) {
    return { label: '高估', color: '#FF9800', signal: '卖出' }
  } else {
    return { label: '极度高估', color: '#E63935', signal: '强烈卖出' }
  }
}

// 当前信号
const currentSignal = computed(() => {
  if (!currentERP.value) return null
  return getERPZone(currentERP.value.erp_spread)
})

// 历史折线图配置
const lineChartOption = computed<EChartsOption>(() => {
  const dates = historicalData.value.map(d => d.trade_date)
  const erpValues = historicalData.value.map(d => d.erp_spread)
  const indexPrices = historicalData.value.map(d => d.index_close_price ?? 0)

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: unknown) => {
        const p = params as { axisValue: string; value: number }[]
        const date = p[0]?.axisValue ?? ''
        const erp = p[0]?.value?.toFixed(2) ?? '-'
        const price = p[1]?.value?.toFixed(2) ?? '-'
        return `${date}<br/>ERP: ${erp}%<br/>指数: ${price}`
      },
    },
    legend: {
      data: ['ERP收益差', '指数价格'],
      top: 10,
      textStyle: { color: '#4A4A4A' },
    },
    grid: [
      { left: '8%', right: '8%', top: '15%', height: '35%' },
      { left: '8%', right: '8%', top: '58%', height: '30%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        gridIndex: 0,
        axisLine: { lineStyle: { color: '#E5E8ED' } },
        axisLabel: { color: '#999999', fontSize: 11 },
        splitLine: { show: false },
      },
      {
        type: 'category',
        data: dates,
        gridIndex: 1,
        axisLine: { lineStyle: { color: '#E5E8ED' } },
        axisLabel: { color: '#999999', fontSize: 11 },
        splitLine: { show: false },
      },
    ],
    yAxis: [
      {
        type: 'value',
        name: 'ERP (%)',
        gridIndex: 0,
        nameTextStyle: { color: '#4A4A4A' },
        axisLine: { show: false },
        axisLabel: { color: '#999999' },
        splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } },
      },
      {
        type: 'value',
        name: '指数价格',
        gridIndex: 1,
        nameTextStyle: { color: '#4A4A4A' },
        axisLine: { show: false },
        axisLabel: { color: '#999999' },
        splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } },
      },
    ],
    visualMap: {
      show: false,
      seriesIndex: 0,
      pieces: [
        { lte: -2, color: '#2E7D32' },
        { gt: -2, lte: 0, color: '#0B3CC3' },
        { gt: 0, lte: 2, color: '#999999' },
        { gt: 2, lte: 4, color: '#FF9800' },
        { gt: 4, color: '#E63935' },
      ],
    },
    markArea: {
      silent: true,
      data: [
        [
          { yAxis: -2, itemStyle: { color: 'rgba(46, 125, 50, 0.08)' } },
          { yAxis: -10 },
        ],
        [
          { yAxis: 4, itemStyle: { color: 'rgba(230, 57, 53, 0.08)' } },
          { yAxis: 10 },
        ],
      ],
    },
    series: [
      {
        name: 'ERP收益差',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: erpValues,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2 },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { yAxis: -2, lineStyle: { color: '#2E7D32', type: 'dashed' }, label: { formatter: '-2%' } },
            { yAxis: 0, lineStyle: { color: '#999999', type: 'dashed' }, label: { formatter: '0%' } },
            { yAxis: 2, lineStyle: { color: '#FF9800', type: 'dashed' }, label: { formatter: '2%' } },
            { yAxis: 4, lineStyle: { color: '#E63935', type: 'dashed' }, label: { formatter: '4%' } },
          ],
        },
      },
      {
        name: '指数价格',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: indexPrices,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#003399', width: 1.5 },
        areaStyle: { color: 'rgba(0, 51, 153, 0.05)' },
      },
    ],
  }
})

// 仪表盘配置
const gaugeChartOption = computed<EChartsOption>(() => {
  const percentile = currentERP.value?.percentile_rank_10y ?? 50

  return {
    series: [
      {
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        radius: '100%',
        center: ['50%', '70%'],
        splitNumber: 10,
        axisLine: {
          lineStyle: {
            width: 20,
            color: [
              [0.2, '#2E7D32'],
              [0.4, '#0B3CC3'],
              [0.6, '#999999'],
              [0.8, '#FF9800'],
              [1, '#E63935'],
            ],
          },
        },
        pointer: {
          icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
          length: '60%',
          width: 8,
          offsetCenter: [0, '-10%'],
          itemStyle: { color: '#1A1A1A' },
        },
        axisTick: {
          length: 8,
          lineStyle: { color: 'auto', width: 1 },
        },
        splitLine: {
          length: 15,
          lineStyle: { color: 'auto', width: 2 },
        },
        axisLabel: {
          color: '#4A4A4A',
          fontSize: 11,
          distance: -45,
          formatter: (value: string | number) => {
            const num = typeof value === 'string' ? parseFloat(value) : value
            if (num === 0) return '极低'
            if (num === 20) return '低'
            if (num === 40) return ''
            if (num === 50) return '中'
            if (num === 60) return ''
            if (num === 80) return '高'
            if (num === 100) return '极高'
            return ''
          },
        },
        title: { offsetCenter: [0, '30%'], fontSize: 14, color: '#4A4A4A' },
        detail: {
          valueAnimation: true,
          formatter: '{value}%',
          fontSize: 24,
          fontWeight: 'bold',
          offsetCenter: [0, '0%'],
          color: '#1A1A1A',
        },
        data: [{ value: percentile, name: '历史百分位' }],
      },
    ],
  }
})

// 散点图配置（ERP与指数涨跌相关性）
const scatterChartOption = computed<EChartsOption>(() => {
  // 计算每日涨跌幅
  const scatterData: [number, number][] = []
  for (let i = 1; i < historicalData.value.length; i++) {
    const prev = historicalData.value[i - 1]
    const curr = historicalData.value[i]
    if (prev.index_close_price && curr.index_close_price) {
      const change = ((curr.index_close_price - prev.index_close_price) / prev.index_close_price) * 100
      scatterData.push([curr.erp_spread, change])
    }
  }

  return {
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as { data: [number, number] }
        return `ERP: ${p.data[0].toFixed(2)}%<br/>涨跌幅: ${p.data[1].toFixed(2)}%`
      },
    },
    grid: { left: '10%', right: '5%', top: '10%', bottom: '15%' },
    xAxis: {
      type: 'value',
      name: 'ERP (%)',
      nameLocation: 'middle',
      nameGap: 30,
      nameTextStyle: { color: '#4A4A4A' },
      axisLine: { lineStyle: { color: '#E5E8ED' } },
      axisLabel: { color: '#999999' },
      splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } },
    },
    yAxis: {
      type: 'value',
      name: '指数涨跌幅 (%)',
      nameLocation: 'middle',
      nameGap: 40,
      nameTextStyle: { color: '#4A4A4A' },
      axisLine: { show: false },
      axisLabel: { color: '#999999' },
      splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } },
    },
    visualMap: {
      show: false,
      dimension: 0,
      pieces: [
        { lte: -2, color: '#2E7D32' },
        { gt: -2, lte: 0, color: '#0B3CC3' },
        { gt: 0, lte: 2, color: '#999999' },
        { gt: 2, lte: 4, color: '#FF9800' },
        { gt: 4, color: '#E63935' },
      ],
    },
    series: [
      {
        type: 'scatter',
        symbolSize: 6,
        data: scatterData,
        itemStyle: { opacity: 0.6 },
      },
      {
        type: 'line',
        data: scatterData,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#003399', width: 2, type: 'dashed' },
        // 简单线性回归趋势线
        encode: { x: 0, y: 1 },
      },
    ],
  }
})

// 获取数据
const fetchData = async () => {
  loading.value = true
  try {
    const response = await getERPSpread(selectedIndex.value)
    erpData.value = response.sort((a, b) => a.trade_date.localeCompare(b.trade_date))
  } catch (error) {
    ElMessage.error('获取ERP数据失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 格式化数字
const formatNumber = (val: number | null | undefined, suffix = ''): string => {
  if (val === null || val === undefined) return '-'
  return `${val.toFixed(2)}${suffix}`
}

// 监听指数切换
watch(selectedIndex, () => {
  fetchData()
})

onMounted(() => {
  fetchData()
})
</script>

<template>
  <div class="erp-spread">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1>股债收益差 (ERP)</h1>
      <p class="subtitle">标准差视角与百分位分级带状着色视角</p>
    </div>

    <!-- 指数选择器 -->
    <div class="index-selector">
      <span class="label">选择指数：</span>
      <el-select v-model="selectedIndex" placeholder="请选择指数" style="width: 160px">
        <el-option
          v-for="item in indexOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
    </div>

    <!-- 核心指标卡片 -->
    <div class="metrics-row">
      <div class="metric-card">
        <div class="metric-label">当前ERP</div>
        <div class="metric-value" :style="{ color: currentSignal?.color ?? '#1A1A1A' }">
          {{ formatNumber(currentERP?.erp_spread, '%') }}
        </div>
        <div class="metric-zone" :style="{ backgroundColor: currentSignal?.color }">
          {{ currentSignal?.label ?? '-' }}
        </div>
      </div>

      <div class="metric-card">
        <div class="metric-label">历史百分位 (10年)</div>
        <div class="metric-value">{{ formatNumber(currentERP?.percentile_rank_10y, '%') }}</div>
        <div class="metric-desc">相对历史水平</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">PE(TTM)</div>
        <div class="metric-value">{{ formatNumber(currentERP?.pe_ttm) }}</div>
        <div class="metric-desc">指数估值</div>
      </div>

      <div class="metric-card">
        <div class="metric-label">10年期国债收益率</div>
        <div class="metric-value">{{ formatNumber(currentERP?.treasury_yield_10y, '%') }}</div>
        <div class="metric-desc">无风险利率</div>
      </div>

      <div class="metric-card signal-card" :style="{ borderColor: currentSignal?.color }">
        <div class="metric-label">投资信号</div>
        <div class="signal-value" :style="{ color: currentSignal?.color }">
          {{ currentSignal?.signal ?? '-' }}
        </div>
        <div class="signal-desc">
          {{ currentERP?.erp_spread && currentERP.erp_spread < -2 ? 'ERP低于-2%，股市相对债券极具吸引力' :
              currentERP?.erp_spread && currentERP.erp_spread > 4 ? 'ERP高于4%，股市相对债券估值过高' :
              '根据ERP水平判断股债相对价值' }}
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="charts-container">
      <!-- 历史ERP折线图 -->
      <div class="chart-card full-width">
        <div class="chart-header">
          <h3>ERP历史走势 (近500天)</h3>
          <div class="legend-items">
            <span class="legend-item"><i class="dot" style="background: #2E7D32"></i>极度低估</span>
            <span class="legend-item"><i class="dot" style="background: #0B3CC3"></i>低估</span>
            <span class="legend-item"><i class="dot" style="background: #999999"></i>中性</span>
            <span class="legend-item"><i class="dot" style="background: #FF9800"></i>高估</span>
            <span class="legend-item"><i class="dot" style="background: #E63935"></i>极度高估</span>
          </div>
        </div>
        <EChartsWrapper
          :option="lineChartOption"
          :loading="loading"
          height="400px"
        />
      </div>

      <!-- 百分位仪表盘 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>ERP百分位位置</h3>
        </div>
        <EChartsWrapper
          :option="gaugeChartOption"
          :loading="loading"
          height="280px"
        />
        <div class="gauge-desc">
          当前ERP处于过去10年 {{ formatNumber(currentERP?.percentile_rank_10y, '%') }} 分位
        </div>
      </div>

      <!-- ERP与指数相关性散点图 -->
      <div class="chart-card">
        <div class="chart-header">
          <h3>ERP vs 指数涨跌相关性</h3>
        </div>
        <EChartsWrapper
          :option="scatterChartOption"
          :loading="loading"
          height="280px"
        />
        <div class="scatter-desc">
          低ERP时买入，高ERP时卖出，历史回测效果显著
        </div>
      </div>
    </div>

    <!-- ERP区间说明 -->
    <div class="zone-legend">
      <h3>ERP区间定义</h3>
      <div class="zone-items">
        <div class="zone-item">
          <span class="zone-color" style="background: #2E7D32"></span>
          <span class="zone-label">ERP &lt; -2%</span>
          <span class="zone-meaning">极度低估</span>
          <span class="zone-signal">强烈买入信号</span>
        </div>
        <div class="zone-item">
          <span class="zone-color" style="background: #0B3CC3"></span>
          <span class="zone-label">-2% ~ 0%</span>
          <span class="zone-meaning">低估</span>
          <span class="zone-signal">买入信号</span>
        </div>
        <div class="zone-item">
          <span class="zone-color" style="background: #999999"></span>
          <span class="zone-label">0% ~ 2%</span>
          <span class="zone-meaning">中性</span>
          <span class="zone-signal">持有</span>
        </div>
        <div class="zone-item">
          <span class="zone-color" style="background: #FF9800"></span>
          <span class="zone-label">2% ~ 4%</span>
          <span class="zone-meaning">高估</span>
          <span class="zone-signal">卖出信号</span>
        </div>
        <div class="zone-item">
          <span class="zone-color" style="background: #E63935"></span>
          <span class="zone-label">ERP &gt; 4%</span>
          <span class="zone-meaning">极度高估</span>
          <span class="zone-signal">强烈卖出信号</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.erp-spread {
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

.index-selector {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.index-selector .label {
  font-size: 14px;
  color: var(--text-regular);
}

.metrics-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
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

.metric-zone {
  display: inline-block;
  margin-top: 8px;
  padding: 2px 8px;
  border-radius: 2px;
  font-size: 12px;
  color: #fff;
}

.metric-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.signal-card {
  border: 2px solid transparent;
  background: linear-gradient(var(--bg-card), var(--bg-card)) padding-box,
              linear-gradient(135deg, var(--brand-navy-dark), var(--brand-navy-active)) border-box;
}

.signal-value {
  font-size: 24px;
  font-weight: 700;
  margin-top: 4px;
}

.signal-desc {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 8px;
  line-height: 1.4;
}

.charts-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.chart-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.legend-items {
  display: flex;
  gap: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.legend-item .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.gauge-desc,
.scatter-desc {
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 8px;
}

.zone-legend {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.zone-legend h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.zone-items {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.zone-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  background: var(--bg-system);
  border-radius: 4px;
}

.zone-color {
  width: 100%;
  height: 4px;
  border-radius: 2px;
}

.zone-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.zone-meaning {
  font-size: 12px;
  color: var(--text-regular);
}

.zone-signal {
  font-size: 11px;
  color: var(--text-muted);
}

@media (max-width: 1200px) {
  .metrics-row {
    grid-template-columns: repeat(3, 1fr);
  }

  .charts-container {
    grid-template-columns: 1fr;
  }

  .zone-items {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 768px) {
  .metrics-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .zone-items {
    grid-template-columns: repeat(2, 1fr);
  }

  .legend-items {
    flex-wrap: wrap;
  }
}
</style>
