<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import { getERPSpread } from '@/api/analytics'
import { useBreakpoint } from '@/composables/useBreakpoint'

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

// 分析模式类型
type AnalysisMode = 'sd' | 'percentile'

// 无风险利率类型
type RiskFreeType = 'treasury_10y' | 'cdb_10y' | 'dr007' | 'deposit_1y' | 'deposit_3y' | 'deposit_5y'

// 响应式数据
const erpData = ref<ERPDataItem[]>([])
const loading = ref(false)
const selectedIndex = ref('000300')

// Mobile breakpoint detection
const { isMobile } = useBreakpoint()

// 无风险利率选择 - 从 localStorage 恢复
const riskFreeType = ref<RiskFreeType>(
  (localStorage.getItem('erp-risk-free-type') as RiskFreeType) || 'treasury_10y'
)

// 当前无风险利率值
const currentRiskFreeRate = ref<number | null>(null)

// 对比数据
const comparisonData = ref<Array<{
  type: string
  rate: number | null
  erp: number | null
}>>([])

// 分析模式 - 从 localStorage 恢复
const analysisMode = ref<AnalysisMode>(
  (localStorage.getItem('erp-analysis-mode') as AnalysisMode) || 'sd'
)

// 监听模式变化，保存到 localStorage
watch(analysisMode, (newMode) => {
  localStorage.setItem('erp-analysis-mode', newMode)
})

// 监听无风险利率类型变化，保存到 localStorage
watch(riskFreeType, (newType) => {
  localStorage.setItem('erp-risk-free-type', newType)
})

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

// 计算统计数据
const statistics = computed(() => {
  const data = historicalData.value
  if (data.length === 0) return { mean: 0, std: 0, p25: 0, p50: 0, p75: 0 }
  
  const erpValues = data.map(d => d.erp_spread).sort((a, b) => a - b)
  const n = erpValues.length
  
  // 计算均值
  const mean = erpValues.reduce((sum, v) => sum + v, 0) / n
  
  // 计算标准差
  const variance = erpValues.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / n
  const std = Math.sqrt(variance)
  
  // 计算百分位数
  const percentile = (p: number) => {
    const idx = (p / 100) * (n - 1)
    const lower = Math.floor(idx)
    const upper = Math.ceil(idx)
    if (lower === upper) return erpValues[lower]
    return erpValues[lower] + (erpValues[upper] - erpValues[lower]) * (idx - lower)
  }
  
  return {
    mean,
    std,
    p25: percentile(25),
    p50: percentile(50),
    p75: percentile(75),
  }
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
  
  const { mean, std, p25, p50, p75 } = statistics.value
  const isSDMode = analysisMode.value === 'sd'
  
  // SD 模式的参考线
  const sdMarkLines = [
    { yAxis: mean, lineStyle: { color: '#1A1A1A', type: 'solid', width: 2 }, label: { formatter: 'μ', position: 'end' } },
    { yAxis: mean + std, lineStyle: { color: '#E63935', type: 'dashed' }, label: { formatter: '+1σ', position: 'end' } },
    { yAxis: mean - std, lineStyle: { color: '#2E7D32', type: 'dashed' }, label: { formatter: '-1σ', position: 'end' } },
    { yAxis: mean + 2 * std, lineStyle: { color: '#E63935', type: 'dotted' }, label: { formatter: '+2σ', position: 'end' } },
    { yAxis: mean - 2 * std, lineStyle: { color: '#2E7D32', type: 'dotted' }, label: { formatter: '-2σ', position: 'end' } },
  ]
  
  // 百分位模式的参考线
  const percentileMarkLines = [
    { yAxis: p25, lineStyle: { color: '#2E7D32', type: 'dashed' }, label: { formatter: '25th', position: 'end' } },
    { yAxis: p50, lineStyle: { color: '#1A1A1A', type: 'solid', width: 2 }, label: { formatter: '50th (中位数)', position: 'end' } },
    { yAxis: p75, lineStyle: { color: '#E63935', type: 'dashed' }, label: { formatter: '75th', position: 'end' } },
  ]
  
  // markArea 区域着色
  const sdMarkArea = [
    // 低于 -1SD (低估区)
    [
      { yAxis: mean - std, itemStyle: { color: 'rgba(46, 125, 50, 0.12)' } },
      { yAxis: mean - 2 * std - 1 },
    ],
    // 高于 +1SD (高估区)
    [
      { yAxis: mean + std, itemStyle: { color: 'rgba(230, 57, 53, 0.12)' } },
      { yAxis: mean + 2 * std + 1 },
    ],
  ]
  
  const percentileMarkArea = [
    // 低于 25th 百分位 (低估区)
    [
      { yAxis: p25, itemStyle: { color: 'rgba(46, 125, 50, 0.12)' } },
      { yAxis: p25 - 5 },
    ],
    // 高于 75th 百分位 (高估区)
    [
      { yAxis: p75, itemStyle: { color: 'rgba(230, 57, 53, 0.12)' } },
      { yAxis: p75 + 5 },
    ],
  ]

  return {
    tooltip: {
      trigger: isMobile.value ? 'none' : 'axis',
      axisPointer: { type: 'cross' },
      formatter: isMobile.value ? undefined : (params: unknown) => {
        const p = params as { axisValue: string; value: number; seriesName: string }[]
        const date = p[0]?.axisValue ?? ''
        const erp = p.find(item => item.seriesName === 'ERP收益差')?.value?.toFixed(2) ?? '-'
        const price = p.find(item => item.seriesName === '指数价格')?.value?.toFixed(2) ?? '-'
        return `${date}<br/>ERP: ${erp}%<br/>指数: ${price}`
      },
    },
    legend: {
      data: ['ERP收益差', '指数价格'],
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
        name: 'ERP (%)',
        nameTextStyle: { color: '#4A4A4A' },
        axisLine: { show: false },
        axisLabel: { color: '#999999' },
        splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } },
      },
      {
        type: 'value',
        name: '指数价格',
        nameTextStyle: { color: '#4A4A4A' },
        axisLine: { show: false },
        axisLabel: { color: '#999999', opacity: 0.5 },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: 'ERP收益差',
        type: 'line',
        yAxisIndex: 0,
        data: erpValues,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2 },
        markLine: {
          silent: true,
          symbol: 'none',
          data: isSDMode ? sdMarkLines : percentileMarkLines,
        },
        markArea: {
          silent: true,
          data: isSDMode ? sdMarkArea : percentileMarkArea,
        },
      },
      {
        name: '指数价格',
        type: 'line',
        yAxisIndex: 1,
        data: indexPrices,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#003399', width: 1.5, opacity: 0.5 },
        areaStyle: { color: 'rgba(0, 51, 153, 0.03)' },
      },
    ],
  } as EChartsOption
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

// 无风险利率类型标签映射
const riskFreeTypeLabels: Record<RiskFreeType, string> = {
  treasury_10y: '国债10年',
  cdb_10y: '国开债10年',
  dr007: 'DR007',
  deposit_1y: '大额存款1年',
  deposit_3y: '大额存款3年',
  deposit_5y: '大额存款5年',
}

// 获取数据
const fetchData = async () => {
  loading.value = true
  try {
    const response = await getERPSpread(selectedIndex.value, riskFreeType.value)
    erpData.value = response.sort((a, b) => a.trade_date.localeCompare(b.trade_date))
    // 从最新数据中获取当前无风险利率
    if (response.length > 0) {
      const latest = response[response.length - 1]
      currentRiskFreeRate.value = latest.risk_free_rate ?? latest.treasury_yield_10y
    }
  } catch (error) {
    ElMessage.error('获取ERP数据失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 获取对比数据
const fetchComparison = async () => {
  const types: RiskFreeType[] = ['treasury_10y', 'cdb_10y', 'dr007', 'deposit_1y', 'deposit_3y', 'deposit_5y']
  const results = await Promise.all(
    types.map(async (type) => {
      try {
        const response = await getERPSpread(selectedIndex.value, type)
        const sorted = response.sort((a, b) => a.trade_date.localeCompare(b.trade_date))
        const latest = sorted[sorted.length - 1]
        return {
          type: riskFreeTypeLabels[type],
          rate: latest?.risk_free_rate ?? latest?.treasury_yield_10y ?? null,
          erp: latest?.erp_spread ?? null,
        }
      } catch {
        return {
          type: riskFreeTypeLabels[type],
          rate: null,
          erp: null,
        }
      }
    })
  )
  comparisonData.value = results
}

// 格式化数字
const formatNumber = (val: number | null | undefined, suffix = ''): string => {
  if (val === null || val === undefined) return '-'
  return `${val.toFixed(2)}${suffix}`
}

// 监听指数切换
watch(selectedIndex, () => {
  fetchData()
  fetchComparison()
})

// 监听无风险利率切换
watch(riskFreeType, () => {
  fetchData()
})

onMounted(() => {
  fetchData()
  fetchComparison()
})
</script>

<template>
  <div class="erp-spread">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1>股债收益差 (ERP)</h1>
      <p class="subtitle">标准差视角与百分位分级带状着色视角</p>
    </div>

    <!-- 指数选择器与分析模式切换 -->
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
      
      <div class="mode-toggle">
        <span class="label">分析视角：</span>
        <el-radio-group v-model="analysisMode" size="small">
          <el-radio-button value="sd">标准差视角</el-radio-button>
          <el-radio-button value="percentile">百分位视角</el-radio-button>
        </el-radio-group>
      </div>
      
      <div class="rf-toggle">
        <span class="label">无风险利率：</span>
        <el-select v-model="riskFreeType" placeholder="选择利率类型" style="width: 140px">
          <el-option-group label="国债/货币市场">
            <el-option value="treasury_10y" label="国债10年" />
            <el-option value="cdb_10y" label="国开债10年" />
            <el-option value="dr007" label="DR007" />
          </el-option-group>
          <el-option-group label="大额存款">
            <el-option value="deposit_1y" label="1年期" />
            <el-option value="deposit_3y" label="3年期" />
            <el-option value="deposit_5y" label="5年期" />
          </el-option-group>
        </el-select>
      </div>
    </div>
    
    <!-- 统计数据展示 -->
    <div class="stats-row" v-if="historicalData.length > 0">
      <div class="stats-card" v-if="analysisMode === 'sd'">
        <div class="stats-title">标准差统计</div>
        <div class="stats-values">
          <span>均值 (μ): {{ statistics.mean.toFixed(2) }}%</span>
          <span>标准差 (σ): {{ statistics.std.toFixed(2) }}%</span>
          <span>+1σ: {{ (statistics.mean + statistics.std).toFixed(2) }}%</span>
          <span>-1σ: {{ (statistics.mean - statistics.std).toFixed(2) }}%</span>
        </div>
      </div>
      <div class="stats-card" v-else>
        <div class="stats-title">百分位统计</div>
        <div class="stats-values">
          <span>25th: {{ statistics.p25.toFixed(2) }}%</span>
          <span>50th (中位数): {{ statistics.p50.toFixed(2) }}%</span>
          <span>75th: {{ statistics.p75.toFixed(2) }}%</span>
        </div>
      </div>
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
        <div class="metric-label">{{ riskFreeTypeLabels[riskFreeType] }}</div>
        <div class="metric-value">{{ currentRiskFreeRate?.toFixed(2) ?? formatNumber(currentERP?.treasury_yield_10y) }}%</div>
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
        <!-- Mobile Dynamic Text Header -->
        <div class="mobile-text-header" v-if="isMobile && currentERP">
          <div class="mobile-header-item">
            <span class="mobile-header-label">当前ERP</span>
            <span class="mobile-header-value" :style="{ color: getERPZone(currentERP.erp_spread)?.color ?? '#1A1A1A' }">
              {{ currentERP.erp_spread?.toFixed(2) }}%
            </span>
          </div>
          <div class="mobile-header-item">
            <span class="mobile-header-label">估值状态</span>
            <span class="mobile-header-status" :style="{ backgroundColor: getERPZone(currentERP.erp_spread)?.color }">
              {{ getERPZone(currentERP.erp_spread)?.label }}
            </span>
          </div>
          <div class="mobile-header-item">
            <span class="mobile-header-label">历史百分位</span>
            <span class="mobile-header-value">{{ currentERP.percentile_rank_10y?.toFixed(1) ?? '-' }}%</span>
          </div>
          <div class="mobile-header-item">
            <span class="mobile-header-label">更新日期</span>
            <span class="mobile-header-value">{{ currentERP.trade_date }}</span>
          </div>
        </div>
        
        <div class="chart-header">
          <h3>ERP历史走势 (近500天) - {{ analysisMode === 'sd' ? '标准差视角' : '百分位视角' }}</h3>
          <div class="legend-items" v-if="analysisMode === 'sd'">
            <span class="legend-item"><i class="dot" style="background: #2E7D32"></i>低于-1σ (低估区)</span>
            <span class="legend-item"><i class="dot" style="background: #1A1A1A"></i>均值 μ</span>
            <span class="legend-item"><i class="dot" style="background: #E63935"></i>高于+1σ (高估区)</span>
          </div>
          <div class="legend-items" v-else>
            <span class="legend-item"><i class="dot" style="background: #2E7D32"></i>低于25th (低估区)</span>
            <span class="legend-item"><i class="dot" style="background: #1A1A1A"></i>50th 中位数</span>
            <span class="legend-item"><i class="dot" style="background: #E63935"></i>高于75th (高估区)</span>
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
      <h3>{{ analysisMode === 'sd' ? '标准差区间定义' : '百分位区间定义' }}</h3>
      <div class="zone-items" v-if="analysisMode === 'sd'">
        <div class="zone-item">
          <span class="zone-color" style="background: rgba(46, 125, 50, 0.3)"></span>
          <span class="zone-label">ERP &lt; μ - 1σ</span>
          <span class="zone-meaning">低估区</span>
          <span class="zone-signal">ERP低于历史均值1个标准差，买入信号</span>
        </div>
        <div class="zone-item">
          <span class="zone-color" style="background: #F4F6F9"></span>
          <span class="zone-label">μ - 1σ ~ μ + 1σ</span>
          <span class="zone-meaning">正常区间</span>
          <span class="zone-signal">ERP处于历史正常波动范围</span>
        </div>
        <div class="zone-item">
          <span class="zone-color" style="background: rgba(230, 57, 53, 0.3)"></span>
          <span class="zone-label">ERP &gt; μ + 1σ</span>
          <span class="zone-meaning">高估区</span>
          <span class="zone-signal">ERP高于历史均值1个标准差，卖出信号</span>
        </div>
      </div>
      <div class="zone-items" v-else>
        <div class="zone-item">
          <span class="zone-color" style="background: rgba(46, 125, 50, 0.3)"></span>
          <span class="zone-label">ERP &lt; 25th</span>
          <span class="zone-meaning">低估区</span>
          <span class="zone-signal">ERP低于历史25%分位，买入信号</span>
        </div>
        <div class="zone-item">
          <span class="zone-color" style="background: #F4F6F9"></span>
          <span class="zone-label">25th ~ 75th</span>
          <span class="zone-meaning">正常区间</span>
          <span class="zone-signal">ERP处于历史中间50%范围</span>
        </div>
        <div class="zone-item">
          <span class="zone-color" style="background: rgba(230, 57, 53, 0.3)"></span>
          <span class="zone-label">ERP &gt; 75th</span>
          <span class="zone-meaning">高估区</span>
          <span class="zone-signal">ERP高于历史75%分位，卖出信号</span>
        </div>
      </div>
    </div>

    <!-- 不同无风险利率下的ERP对比 -->
    <div class="comparison-section">
      <h3>不同无风险利率下的ERP对比</h3>
      <el-table 
        :data="comparisonData" 
        size="small"
        :border="true"
        style="width: 100%"
      >
        <el-table-column prop="type" label="利率类型" width="120" align="center" />
        <el-table-column prop="rate" label="当前利率 (%)" width="120" align="center">
          <template #default="{ row }">
            <span class="rate-value">{{ row.rate?.toFixed(2) ?? '-' }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="erp" label="ERP (%)" align="center">
          <template #default="{ row }">
            <span 
              class="erp-value" 
              :style="{ color: getERPZone(row.erp ?? 0)?.color ?? '#1A1A1A' }"
            >
              {{ row.erp?.toFixed(2) ?? '-' }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
      <div class="comparison-note">
        <span class="note-icon">💡</span>
        <span class="note-text">
          当前使用 <strong>{{ riskFreeTypeLabels[riskFreeType] }}</strong> 计算ERP。
          不同无风险利率基准会影响ERP数值，投资者可根据偏好选择参考基准。
        </span>
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
  gap: 24px;
  flex-wrap: wrap;
}

.index-selector .label {
  font-size: 14px;
  color: var(--text-regular);
}

.mode-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
}

.rf-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stats-row {
  margin-bottom: 20px;
}

.stats-card {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 12px 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.stats-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.stats-values {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-regular);
  flex-wrap: wrap;
}

.stats-values span {
  padding: 2px 8px;
  background: var(--bg-system);
  border-radius: 2px;
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

/* Mobile Dynamic Text Header */
.mobile-text-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-system);
  border-radius: 6px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.mobile-header-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 70px;
}

.mobile-header-label {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
}

.mobile-header-value {
  font-size: 14px;
  font-weight: 700;
  font-family: 'DIN Alternate', -apple-system, sans-serif;
  color: var(--text-primary);
}

.mobile-header-status {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
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
  grid-template-columns: repeat(3, 1fr);
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

.comparison-section {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  margin-top: 20px;
}

.comparison-section h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.rate-value {
  font-weight: 600;
  color: var(--text-primary);
}

.erp-value {
  font-weight: 700;
}

.comparison-note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--bg-system);
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.note-icon {
  font-size: 14px;
}

.note-text strong {
  color: var(--brand-navy-dark);
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
    grid-template-columns: 1fr;
  }

  .legend-items {
    flex-wrap: wrap;
  }
  
  .index-selector {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .mode-toggle,
  .rf-toggle {
    width: 100%;
  }
}
</style>
