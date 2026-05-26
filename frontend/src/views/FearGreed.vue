<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getFearGreedIndex } from '@/api/analytics'

// Fear/Greed data type
interface FearGreedData {
  trade_date: string
  composite_score: number
  sentiment_status: string
  factor_volatility: number | null
  factor_safe_haven: number | null
  factor_margin_ratio: number | null
  factor_volume_deviation: number | null
  factor_futures_basis: number | null
  factor_stock_strength: number | null
}

// Reactive state
const loading = ref(false)
const fearGreedData = ref<FearGreedData[]>([])
const gaugeChart = ref<echarts.ECharts | null>(null)
const trendChart = ref<echarts.ECharts | null>(null)
const radarChart = ref<echarts.ECharts | null>(null)

// Chart DOM refs
const gaugeChartRef = ref<HTMLElement | null>(null)
const trendChartRef = ref<HTMLElement | null>(null)
const radarChartRef = ref<HTMLElement | null>(null)

// Current data (latest)
const currentData = computed<FearGreedData | null>(() => {
  if (fearGreedData.value.length === 0) return null
  return fearGreedData.value[fearGreedData.value.length - 1]
})

// Sentiment zone colors
const getSentimentColor = (score: number): string => {
  if (score <= 20) return '#E63935' // 极度恐惧 - red
  if (score <= 40) return '#FF9800' // 恐惧 - orange
  if (score <= 60) return '#999999' // 中性 - gray
  if (score <= 80) return '#2E7D32' // 贪婪 - green
  return '#1565C0' // 极度贪婪 - blue
}

const getSentimentLabel = (score: number): string => {
  if (score <= 20) return '极度恐惧'
  if (score <= 40) return '恐惧'
  if (score <= 60) return '中性'
  if (score <= 80) return '贪婪'
  return '极度贪婪'
}

const getSentimentBgClass = (score: number): string => {
  if (score <= 20) return 'status-extreme-fear'
  if (score <= 40) return 'status-fear'
  if (score <= 60) return 'status-neutral'
  if (score <= 80) return 'status-greed'
  return 'status-extreme-greed'
}

// Factor labels for display
const factorLabels: Record<string, string> = {
  factor_volatility: '波动率',
  factor_safe_haven: '避险情绪',
  factor_margin_ratio: '融资余额',
  factor_volume_deviation: '成交量偏离',
  factor_futures_basis: '期货基差',
  factor_stock_strength: '股票强度',
}

// Format date
const formatDate = (dateStr: string): string => {
  if (!dateStr || dateStr.length < 8) return dateStr
  return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`
}

// Initialize gauge chart
const initGaugeChart = () => {
  if (!gaugeChartRef.value || !currentData.value) return

  if (gaugeChart.value) {
    gaugeChart.value.dispose()
  }

  gaugeChart.value = echarts.init(gaugeChartRef.value)
  const score = currentData.value.composite_score
  const color = getSentimentColor(score)

  const option: echarts.EChartsOption = {
    series: [
      {
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        splitNumber: 5,
        radius: '100%',
        center: ['50%', '70%'],
        axisLine: {
          lineStyle: {
            width: 20,
            color: [
              [0.2, '#E63935'],
              [0.4, '#FF9800'],
              [0.6, '#999999'],
              [0.8, '#2E7D32'],
              [1, '#1565C0'],
            ],
          },
        },
        pointer: {
          width: 5,
          length: '60%',
          itemStyle: {
            color: color,
          },
        },
        axisTick: {
          distance: -20,
          length: 6,
          lineStyle: {
            color: '#999',
            width: 1,
          },
        },
        splitLine: {
          distance: -20,
          length: 12,
          lineStyle: {
            color: '#999',
            width: 2,
          },
        },
        axisLabel: {
          distance: -35,
          color: '#4A4A4A',
          fontSize: 12,
          formatter: (value: number) => {
            if (value === 0) return '极度恐惧'
            if (value === 20) return '恐惧'
            if (value === 40) return '中性'
            if (value === 60) return '贪婪'
            if (value === 80) return '极度贪婪'
            if (value === 100) return ''
            return ''
          },
        },
        detail: {
          valueAnimation: true,
          formatter: '{value}',
          fontSize: 36,
          fontWeight: 'bold',
          color: color,
          offsetCenter: [0, '10%'],
        },
        data: [
          {
            value: score,
          },
        ],
      },
    ],
  }

  gaugeChart.value.setOption(option)
}

// Initialize trend chart
const initTrendChart = () => {
  if (!trendChartRef.value || fearGreedData.value.length === 0) return

  if (trendChart.value) {
    trendChart.value.dispose()
  }

  trendChart.value = echarts.init(trendChartRef.value)

  const dates = fearGreedData.value.map(d => formatDate(d.trade_date))
  const scores = fearGreedData.value.map(d => d.composite_score)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#E5E8ED',
      borderWidth: 1,
      textStyle: {
        color: '#1A1A1A',
      },
      formatter: (params: unknown) => {
        const p = params as Array<{ axisValue: string; value: number; marker: string }>
        if (!p || p.length === 0) return ''
        const data = p[0]
        const score = data.value
        const status = getSentimentLabel(score)
        return `
          <div style="padding: 8px;">
            <div style="font-weight: 600; margin-bottom: 4px;">${data.axisValue}</div>
            <div>${data.marker} 恐惧贪婪指数: <strong>${score}</strong></div>
            <div style="color: ${getSentimentColor(score)};">情绪状态: ${status}</div>
          </div>
        `
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
      data: dates,
      boundaryGap: false,
      axisLine: {
        lineStyle: {
          color: '#E5E8ED',
        },
      },
      axisLabel: {
        color: '#4A4A4A',
        fontSize: 11,
        rotate: 45,
      },
      axisTick: {
        show: false,
      },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      splitLine: {
        lineStyle: {
          color: '#E5E8ED',
          type: 'dashed',
        },
      },
      axisLine: {
        show: false,
      },
      axisLabel: {
        color: '#4A4A4A',
        fontSize: 11,
      },
    },
    visualMap: {
      show: false,
      pieces: [
        { lte: 20, color: '#E63935' },
        { gt: 20, lte: 40, color: '#FF9800' },
        { gt: 40, lte: 60, color: '#999999' },
        { gt: 60, lte: 80, color: '#2E7D32' },
        { gt: 80, color: '#1565C0' },
      ],
    },
    series: [
      {
        type: 'line',
        data: scores,
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: {
          width: 2,
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(21, 101, 192, 0.3)' },
            { offset: 1, color: 'rgba(21, 101, 192, 0.05)' },
          ]),
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: {
            type: 'dashed',
            width: 1,
          },
          data: [
            { yAxis: 20, lineStyle: { color: '#E63935' }, label: { formatter: '极度恐惧', position: 'end' } },
            { yAxis: 40, lineStyle: { color: '#FF9800' }, label: { formatter: '恐惧', position: 'end' } },
            { yAxis: 60, lineStyle: { color: '#999999' }, label: { formatter: '中性', position: 'end' } },
            { yAxis: 80, lineStyle: { color: '#2E7D32' }, label: { formatter: '贪婪', position: 'end' } },
          ],
        },
      },
    ],
  }

  trendChart.value.setOption(option)
}

// Initialize radar chart
const initRadarChart = () => {
  if (!radarChartRef.value || !currentData.value) return

  if (radarChart.value) {
    radarChart.value.dispose()
  }

  radarChart.value = echarts.init(radarChartRef.value)

  const data = currentData.value
  const factorKeys = [
    'factor_volatility',
    'factor_safe_haven',
    'factor_margin_ratio',
    'factor_volume_deviation',
    'factor_futures_basis',
    'factor_stock_strength',
  ] as const

  const radarData = factorKeys.map(key => {
    const value = data[key]
    return value !== null ? Math.max(0, Math.min(100, value)) : 0
  })

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#E5E8ED',
      borderWidth: 1,
      textStyle: {
        color: '#1A1A1A',
      },
    },
    radar: {
      indicator: factorKeys.map(key => ({
        name: factorLabels[key],
        max: 100,
      })),
      radius: '65%',
      center: ['50%', '50%'],
      splitNumber: 4,
      axisName: {
        color: '#4A4A4A',
        fontSize: 12,
      },
      splitLine: {
        lineStyle: {
          color: '#E5E8ED',
        },
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(255, 255, 255, 0)', 'rgba(0, 51, 153, 0.03)'],
        },
      },
      axisLine: {
        lineStyle: {
          color: '#E5E8ED',
        },
      },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: radarData,
            name: '因子贡献',
            symbol: 'circle',
            symbolSize: 6,
            lineStyle: {
              color: '#003399',
              width: 2,
            },
            areaStyle: {
              color: 'rgba(0, 51, 153, 0.2)',
            },
            itemStyle: {
              color: '#003399',
            },
          },
        ],
      },
    ],
  }

  radarChart.value.setOption(option)
}

// Fetch data from API
const fetchData = async () => {
  loading.value = true
  try {
    const response = await getFearGreedIndex()
    fearGreedData.value = response.sort((a, b) => 
      a.trade_date.localeCompare(b.trade_date)
    )
    
    // Initialize charts after data is loaded
    setTimeout(() => {
      initGaugeChart()
      initTrendChart()
      initRadarChart()
    }, 100)
  } catch (error) {
    ElMessage.error('获取恐惧贪婪指数数据失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// Handle window resize
const handleResize = () => {
  gaugeChart.value?.resize()
  trendChart.value?.resize()
  radarChart.value?.resize()
}

// Watch for data changes
watch(currentData, () => {
  if (currentData.value) {
    setTimeout(() => {
      initGaugeChart()
      initRadarChart()
    }, 50)
  }
})

onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  gaugeChart.value?.dispose()
  trendChart.value?.dispose()
  radarChart.value?.dispose()
})
</script>

<template>
  <div class="fear-greed" v-loading="loading">
    <!-- Header -->
    <div class="page-header">
      <h2>恐惧贪婪指数</h2>
      <div class="header-info">
        <span class="update-time" v-if="currentData">
          更新时间: {{ formatDate(currentData.trade_date) }}
        </span>
        <el-tag 
          v-if="currentData" 
          :class="['status-tag', getSentimentBgClass(currentData.composite_score)]"
          size="large"
        >
          {{ currentData.sentiment_status }}
        </el-tag>
      </div>
    </div>

    <!-- Main content -->
    <div class="content-grid" v-if="currentData">
      <!-- Left: Gauge chart -->
      <div class="gauge-section card">
        <div class="card-title">当前情绪指数</div>
        <div class="gauge-container" ref="gaugeChartRef"></div>
        <div class="gauge-legend">
          <div class="legend-item">
            <span class="legend-color" style="background: #E63935;"></span>
            <span>极度恐惧 (0-20)</span>
          </div>
          <div class="legend-item">
            <span class="legend-color" style="background: #FF9800;"></span>
            <span>恐惧 (20-40)</span>
          </div>
          <div class="legend-item">
            <span class="legend-color" style="background: #999999;"></span>
            <span>中性 (40-60)</span>
          </div>
          <div class="legend-item">
            <span class="legend-color" style="background: #2E7D32;"></span>
            <span>贪婪 (60-80)</span>
          </div>
          <div class="legend-item">
            <span class="legend-color" style="background: #1565C0;"></span>
            <span>极度贪婪 (80-100)</span>
          </div>
        </div>
      </div>

      <!-- Right: Radar chart -->
      <div class="radar-section card">
        <div class="card-title">因子贡献分析</div>
        <div class="radar-container" ref="radarChartRef"></div>
        <div class="factor-list">
          <div 
            v-for="(label, key) in factorLabels" 
            :key="key"
            class="factor-item"
          >
            <span class="factor-name">{{ label }}</span>
            <span class="factor-value">
              {{ currentData[key as keyof FearGreedData] !== null 
                ? (currentData[key as keyof FearGreedData] as number).toFixed(1) 
                : '-' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Bottom: Trend chart -->
      <div class="trend-section card">
        <div class="card-title">历史趋势 (近30天)</div>
        <div class="trend-container" ref="trendChartRef"></div>
      </div>
    </div>

    <!-- Empty state -->
    <div class="empty-state" v-else-if="!loading">
      <p>暂无数据</p>
    </div>
  </div>
</template>

<style scoped>
.fear-greed {
  min-height: calc(100vh - 100px);
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

.update-time {
  font-size: 13px;
  color: var(--text-muted);
}

.status-tag {
  font-weight: 600;
  border: none;
}

.status-extreme-fear {
  background-color: rgba(230, 57, 53, 0.15);
  color: #E63935;
}

.status-fear {
  background-color: rgba(255, 152, 0, 0.15);
  color: #FF9800;
}

.status-neutral {
  background-color: rgba(153, 153, 153, 0.15);
  color: #666666;
}

.status-greed {
  background-color: rgba(46, 125, 50, 0.15);
  color: #2E7D32;
}

.status-extreme-greed {
  background-color: rgba(21, 101, 192, 0.15);
  color: #1565C0;
}

.content-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto auto;
  gap: 16px;
}

.gauge-section,
.radar-section {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
}

.trend-section {
  grid-column: 1 / -1;
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

.gauge-container {
  width: 100%;
  height: 280px;
}

.gauge-legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 16px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border-line);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-regular);
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

.radar-container {
  width: 100%;
  height: 260px;
}

.factor-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border-line);
}

.factor-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--bg-system);
  border-radius: 4px;
}

.factor-name {
  font-size: 13px;
  color: var(--text-regular);
}

.factor-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.trend-container {
  width: 100%;
  height: 320px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
  color: var(--text-muted);
}

/* Responsive */
@media (max-width: 1200px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
  
  .trend-section {
    grid-column: 1;
  }
}
</style>