<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getFearGreedIndex } from '@/api/analytics'
import { useBreakpoint } from '@/composables/useBreakpoint'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import DataConfidenceBadge from '@/components/DataConfidenceBadge.vue'

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

// Factor configuration for topology
interface FactorConfig {
  key: keyof FearGreedData
  label: string
  description: string
  position: { x: number; y: number }
  angle: number
}

// Data source type tracking
type DataSource = 'real' | 'delayed' | 'simulated'

// Reactive state
const fearGreedLoading = ref(true)
const fearGreedDataSource = ref<DataSource>('simulated')
const loading = ref(false)
const fearGreedData = ref<FearGreedData[]>([])
const gaugeChart = ref<echarts.ECharts | null>(null)
const trendChart = ref<echarts.ECharts | null>(null)

// Mobile breakpoint detection
const { isMobile } = useBreakpoint()

// Chart DOM refs
const gaugeChartRef = ref<HTMLElement | null>(null)
const trendChartRef = ref<HTMLElement | null>(null)

// Current data (latest)
const currentData = computed<FearGreedData | null>(() => {
  if (fearGreedData.value.length === 0) return null
  return fearGreedData.value[fearGreedData.value.length - 1]
})

// Sentiment zone colors
const getSentimentColor = (score: number): string => {
  if (score <= 25) return '#E63935' // 极度恐惧 - red
  if (score <= 45) return '#FF9800' // 恐惧 - orange
  if (score <= 55) return '#999999' // 中性 - gray
  if (score <= 75) return '#2E7D32' // 贪婪 - green
  return '#1565C0' // 极度贪婪 - blue
}

const getSentimentLabel = (score: number): string => {
  if (score <= 25) return '极度恐惧'
  if (score <= 45) return '恐惧'
  if (score <= 55) return '中性'
  if (score <= 75) return '贪婪'
  return '极度贪婪'
}

const getSentimentBgClass = (score: number): string => {
  if (score <= 25) return 'status-extreme-fear'
  if (score <= 45) return 'status-fear'
  if (score <= 55) return 'status-neutral'
  if (score <= 75) return 'status-greed'
  return 'status-extreme-greed'
}

// Factor configuration for topology tree
const factorConfigs: FactorConfig[] = [
  { key: 'factor_volatility', label: '波动率', description: '市场波动性指标', position: { x: 15, y: 20 }, angle: -60 },
  { key: 'factor_margin_ratio', label: '融资余额', description: '杠杆资金变化', position: { x: 50, y: 5 }, angle: -30 },
  { key: 'factor_stock_strength', label: '股票强度', description: '个股表现强度', position: { x: 85, y: 20 }, angle: 0 },
  { key: 'factor_safe_haven', label: '避险情绪', description: '避险资产需求', position: { x: 85, y: 80 }, angle: 60 },
  { key: 'factor_futures_basis', label: '期货基差', description: '期现价差', position: { x: 50, y: 95 }, angle: 30 },
  { key: 'factor_volume_deviation', label: '成交量偏离', description: '成交量异常', position: { x: 15, y: 80 }, angle: 120 },
]

// Format date
const formatDate = (dateStr: string): string => {
  if (!dateStr || dateStr.length < 8) return dateStr
  return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`
}

// Get factor value safely
const getFactorValue = (key: keyof FearGreedData): number => {
  if (!currentData.value) return 0
  const value = currentData.value[key]
  return value !== null && typeof value === 'number' ? Math.max(0, Math.min(100, value)) : 0
}

// Initialize gauge chart with enhanced animation
const initGaugeChart = () => {
  if (!gaugeChartRef.value || !currentData.value) return

  if (gaugeChart.value) {
    gaugeChart.value.dispose()
  }

  gaugeChart.value = echarts.init(gaugeChartRef.value)
  const score = currentData.value.composite_score
  const color = getSentimentColor(score)
  const label = getSentimentLabel(score)

  const option: echarts.EChartsOption = {
    series: [
      {
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        splitNumber: 5,
        radius: '95%',
        center: ['50%', '65%'],
        axisLine: {
          lineStyle: {
            width: 30,
            color: [
              [0.25, '#E63935'],
              [0.45, '#FF9800'],
              [0.55, '#999999'],
              [0.75, '#2E7D32'],
              [1, '#1565C0'],
            ],
          },
        },
        pointer: {
          width: 6,
          length: '50%',
          itemStyle: {
            color: color,
            shadowColor: 'rgba(0, 0, 0, 0.3)',
            shadowBlur: 8,
            shadowOffsetX: 2,
            shadowOffsetY: 2,
          },
        },
        anchor: {
          show: true,
          showAbove: true,
          size: 18,
          itemStyle: {
            borderWidth: 4,
            borderColor: color,
            color: '#FFFFFF',
            shadowColor: 'rgba(0, 0, 0, 0.2)',
            shadowBlur: 6,
          },
        },
        axisTick: {
          distance: -30,
          length: 8,
          lineStyle: {
            color: '#999',
            width: 1,
          },
        },
        splitLine: {
          distance: -30,
          length: 15,
          lineStyle: {
            color: '#999',
            width: 2,
          },
        },
        axisLabel: {
          distance: -45,
          color: '#4A4A4A',
          fontSize: 11,
          formatter: (value: number) => {
            if (value === 0) return '极度恐惧'
            if (value === 25) return '恐惧'
            if (value === 50) return '中性'
            if (value === 75) return '贪婪'
            if (value === 100) return '极度贪婪'
            return ''
          },
        },
        title: {
          show: true,
          offsetCenter: [0, '25%'],
          fontSize: 16,
          fontWeight: 600,
          color: color,
          formatter: () => label,
        },
        detail: {
          valueAnimation: true,
          formatter: '{value}',
          fontSize: 44,
          fontWeight: 'bold',
          color: color,
          offsetCenter: [0, '30%'],
          fontFamily: 'DIN Alternate, -apple-system, sans-serif',
        },
        data: [
          {
            value: score,
          },
        ],
        animation: true,
        animationDuration: 2000,
        animationEasing: 'cubicOut',
      },
    ],
  }

  gaugeChart.value.setOption(option)
}

// Initialize trend chart with zone shading
const initTrendChart = () => {
  if (!trendChartRef.value || fearGreedData.value.length === 0) return

  if (trendChart.value) {
    trendChart.value.dispose()
  }

  trendChart.value = echarts.init(trendChartRef.value)

  const dates = fearGreedData.value.map(d => formatDate(d.trade_date))
  const scores = fearGreedData.value.map(d => d.composite_score)
  const lastIndex = scores.length - 1

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: isMobile.value ? 'none' : 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#E5E8ED',
      borderWidth: 1,
      textStyle: {
        color: '#1A1A1A',
      },
      formatter: isMobile.value ? undefined : (params: unknown) => {
        const p = params as Array<{ axisValue: string; value: number; marker: string; dataIndex: number }>
        if (!p || p.length === 0) return ''
        const data = p[0]
        const score = data.value
        const status = getSentimentLabel(score)
        const isLatest = data.dataIndex === lastIndex
        return `
          <div style="padding: 8px;">
            <div style="font-weight: 600; margin-bottom: 4px;">${data.axisValue} ${isLatest ? '<span style="color: #1565C0;">(当前)</span>' : ''}</div>
            <div>${data.marker} 恐惧贪婪指数: <strong>${score}</strong></div>
            <div style="color: ${getSentimentColor(score)};">情绪状态: ${status}</div>
          </div>
        `
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
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
        { lte: 25, color: '#E63935' },
        { gt: 25, lte: 45, color: '#FF9800' },
        { gt: 45, lte: 55, color: '#999999' },
        { gt: 55, lte: 75, color: '#2E7D32' },
        { gt: 75, color: '#1565C0' },
      ],
    },
    // @ts-expect-error - ECharts series type inference issue with complex callback configurations
    series: [
      {
        type: 'line' as const,
        data: scores,
        smooth: true,
        symbol: 'circle',
        symbolSize: function (_value: number, params: { dataIndex: number }) {
          return params.dataIndex === lastIndex ? 10 : 4
        },
        itemStyle: {
          color: function (params: { dataIndex: number; value?: number }) {
            return params.dataIndex === lastIndex ? '#1565C0' : getSentimentColor(params.value as number)
          },
          borderWidth: function (params: { dataIndex: number }) {
            return params.dataIndex === lastIndex ? 3 : 0
          },
          borderColor: '#FFFFFF',
        },
        lineStyle: {
          width: 2.5,
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(21, 101, 192, 0.25)' },
            { offset: 0.5, color: 'rgba(21, 101, 192, 0.1)' },
            { offset: 1, color: 'rgba(21, 101, 192, 0.02)' },
          ]),
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: {
            type: 'dashed',
            width: 1,
          },
          label: {
            show: true,
            position: 'insideEndTop',
            fontSize: 10,
            color: '#666',
          },
          data: [
            { yAxis: 25, lineStyle: { color: '#E63935' }, label: { formatter: '极度恐惧' } },
            { yAxis: 45, lineStyle: { color: '#FF9800' }, label: { formatter: '恐惧' } },
            { yAxis: 55, lineStyle: { color: '#999999' }, label: { formatter: '中性' } },
            { yAxis: 75, lineStyle: { color: '#2E7D32' }, label: { formatter: '贪婪' } },
          ],
        },
        markArea: {
          silent: true,
          data: [
            [
              { yAxis: 0, itemStyle: { color: 'rgba(230, 57, 53, 0.06)' } },
              { yAxis: 25 },
            ],
            [
              { yAxis: 75, itemStyle: { color: 'rgba(21, 101, 192, 0.06)' } },
              { yAxis: 100 },
            ],
          ],
        },
        markPoint: {
          symbol: 'pin',
          symbolSize: 40,
          data: [
            {
              coord: [dates[lastIndex], scores[lastIndex]],
              value: scores[lastIndex],
              itemStyle: {
                color: getSentimentColor(scores[lastIndex]),
              },
              label: {
                show: true,
                color: '#FFFFFF',
                fontSize: 11,
                fontWeight: 'bold',
              },
            },
          ],
        },
      },
    ],
  }

  trendChart.value.setOption(option)
}

// Fetch data from API
const fetchData = async () => {
  fearGreedLoading.value = true
  loading.value = true
  try {
    const response = await getFearGreedIndex()
    if (response && Array.isArray(response) && response.length > 0) {
      fearGreedData.value = response.sort((a, b) => 
        a.trade_date.localeCompare(b.trade_date)
      )
      fearGreedDataSource.value = 'real'
    }
    
    // Initialize charts after DOM update
    await nextTick()
    initGaugeChart()
    initTrendChart()
  } catch (error) {
    ElMessage.error('获取恐惧贪婪指数数据失败')
    fearGreedDataSource.value = 'simulated'
  } finally {
    fearGreedLoading.value = false
    loading.value = false
  }
}

// Debounced resize handler
let resizeTimer: ReturnType<typeof setTimeout> | null = null
const handleResize = () => {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    gaugeChart.value?.resize()
    trendChart.value?.resize()
  }, 200)
}

// Watch for data changes
watch(currentData, async () => {
  if (currentData.value) {
    await nextTick()
    initGaugeChart()
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
})
</script>

<template>
  <div class="fear-greed">
    <!-- Header -->
    <div class="page-header">
      <h2>恐惧贪婪指数</h2>
      <div class="header-info">
        <DataConfidenceBadge 
          :source="fearGreedDataSource" 
          :timestamp="currentData?.trade_date"
        />
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

    <ErrorBoundary>
      <!-- Loading Skeletons -->
      <template v-if="fearGreedLoading">
        <div class="skeleton-wrapper">
          <SkeletonLoader variant="gauge" height="500px" />
        </div>
        <div class="skeleton-wrapper" style="margin-top: 16px;">
          <SkeletonLoader variant="image" height="300px" />
        </div>
        <div class="skeleton-wrapper" style="margin-top: 16px;">
          <SkeletonLoader variant="table" :rows="3" :columns="3" />
        </div>
      </template>

      <!-- Main content -->
      <div class="content-wrapper" v-else-if="currentData">
      <!-- Topology Tree Section -->
      <div class="topology-section">
        <!-- SVG Connection Lines -->
        <svg class="topology-lines" viewBox="0 0 100 100" preserveAspectRatio="none">
          <defs>
            <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" style="stop-color: rgba(0, 51, 153, 0.3)" />
              <stop offset="50%" style="stop-color: rgba(0, 51, 153, 0.5)" />
              <stop offset="100%" style="stop-color: rgba(0, 51, 153, 0.3)" />
            </linearGradient>
          </defs>
          <!-- Lines from center to each satellite -->
          <line 
            v-for="factor in factorConfigs" 
            :key="`line-${factor.key}`"
            :x1="50" 
            :y1="50" 
            :x2="factor.position.x" 
            :y2="factor.position.y"
            stroke="url(#lineGradient)"
            stroke-width="0.3"
            class="topology-line"
          />
          <!-- Center circle -->
          <circle cx="50" cy="50" r="8" fill="var(--brand-navy-dark)" opacity="0.8" />
        </svg>

        <!-- Central Gauge Card -->
        <div class="center-card">
          <div class="gauge-wrapper" ref="gaugeChartRef"></div>
        </div>

        <!-- Satellite Factor Cards -->
        <div 
          v-for="factor in factorConfigs" 
          :key="factor.key"
          class="satellite-card"
          :style="{ 
            left: `${factor.position.x}%`, 
            top: `${factor.position.y}%`,
            transform: `translate(-50%, -50%)`
          }"
        >
          <div class="satellite-header">
            <span class="satellite-label">{{ factor.label }}</span>
            <span 
              class="satellite-value"
              :style="{ color: getSentimentColor(getFactorValue(factor.key)) }"
            >
              {{ getFactorValue(factor.key).toFixed(2) }}
            </span>
          </div>
          <div class="progress-bar">
            <div 
              class="progress-fill"
              :style="{ 
                width: `${getFactorValue(factor.key)}%`,
                background: getSentimentColor(getFactorValue(factor.key))
              }"
            ></div>
          </div>
          <div class="satellite-desc">{{ factor.description }}</div>
        </div>
      </div>

      <!-- Historical Trend Section -->
      <div class="trend-section card">
        <!-- Mobile Dynamic Text Header -->
        <div class="mobile-text-header" v-if="isMobile && currentData">
          <div class="mobile-header-item">
            <span class="mobile-header-label">当前指数</span>
            <span class="mobile-header-value" :style="{ color: getSentimentColor(currentData.composite_score) }">
              {{ currentData.composite_score.toFixed(2) }}
            </span>
          </div>
          <div class="mobile-header-item">
            <span class="mobile-header-label">情绪状态</span>
            <span class="mobile-header-status" :style="{ backgroundColor: getSentimentColor(currentData.composite_score) }">
              {{ getSentimentLabel(currentData.composite_score) }}
            </span>
          </div>
          <div class="mobile-header-item">
            <span class="mobile-header-label">更新日期</span>
            <span class="mobile-header-value">{{ formatDate(currentData.trade_date) }}</span>
          </div>
        </div>
        
        <div class="card-title">
          <span>历史趋势 (近30天)</span>
          <div class="trend-legend">
            <span class="legend-item">
              <span class="legend-dot" style="background: #E63935;"></span>
              极度恐惧
            </span>
            <span class="legend-item">
              <span class="legend-dot" style="background: #FF9800;"></span>
              恐惧
            </span>
            <span class="legend-item">
              <span class="legend-dot" style="background: #999999;"></span>
              中性
            </span>
            <span class="legend-item">
              <span class="legend-dot" style="background: #2E7D32;"></span>
              贪婪
            </span>
            <span class="legend-item">
              <span class="legend-dot" style="background: #1565C0;"></span>
              极度贪婪
            </span>
          </div>
        </div>
        <div class="trend-container" ref="trendChartRef"></div>
      </div>

      <!-- Factor Summary Grid -->
      <div class="factor-summary card">
        <div class="card-title">因子详情</div>
        <div class="factor-grid">
          <div 
            v-for="factor in factorConfigs" 
            :key="`summary-${factor.key}`"
            class="factor-detail"
          >
            <div class="factor-detail-header">
              <span class="factor-detail-label">{{ factor.label }}</span>
              <span 
                class="factor-detail-value"
                :style="{ color: getSentimentColor(getFactorValue(factor.key)) }"
              >
                {{ getFactorValue(factor.key).toFixed(2) }}
              </span>
            </div>
            <div class="factor-detail-bar">
              <div 
                class="factor-detail-fill"
                :style="{ 
                  width: `${getFactorValue(factor.key)}%`,
                  background: `linear-gradient(90deg, ${getSentimentColor(getFactorValue(factor.key))} 0%, ${getSentimentColor(getFactorValue(factor.key))}88 100%)`
                }"
              ></div>
            </div>
            <div class="factor-detail-desc">{{ factor.description }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div class="empty-state" v-else>
      <p>暂无数据</p>
    </div>
  </ErrorBoundary>
</div>
</template>

<style scoped>
.fear-greed {
  min-height: calc(100vh - 100px); /* Fallback for older browsers */
  min-height: calc(100dvh - 100px);
  padding: var(--spacing-md);
  background: var(--bg-system);
}

.skeleton-wrapper {
  background: var(--bg-card);
  border-radius: 8px;
  padding: var(--spacing-md);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
  padding-bottom: var(--spacing-md);
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
  gap: var(--spacing-md);
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

/* Content Wrapper */
.content-wrapper {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

/* Topology Section */
.topology-section {
  position: relative;
  width: 100%;
  height: 500px;
  background: var(--bg-card);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.topology-lines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 1;
}

.topology-line {
  stroke-dasharray: 2, 2;
  animation: dash 20s linear infinite;
}

@keyframes dash {
  to {
    stroke-dashoffset: -100;
  }
}

/* Center Card */
.center-card {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 280px;
  height: 280px;
  background: var(--bg-card);
  border-radius: 50%;
  box-shadow: 
    0 4px 20px rgba(0, 51, 153, 0.15),
    0 0 0 1px rgba(0, 51, 153, 0.1);
  z-index: var(--z-sticky);
  display: flex;
  align-items: center;
  justify-content: center;
}

.gauge-wrapper {
  width: 100%;
  height: 100%;
}

/* Satellite Cards */
.satellite-card {
  position: absolute;
  width: 140px;
  background: var(--bg-card);
  border-radius: 8px;
  padding: var(--spacing-sm) var(--spacing-md);
  box-shadow: 
    0 2px 8px rgba(0, 0, 0, 0.08),
    0 0 0 1px rgba(0, 51, 153, 0.08);
  z-index: 5;
  transition: all 0.3s ease;
  cursor: pointer;
}

.satellite-card:hover {
  transform: translate(-50%, -50%) scale(1.05);
  box-shadow: 
    0 4px 16px rgba(0, 51, 153, 0.2),
    0 0 0 2px rgba(0, 51, 153, 0.2);
}

.satellite-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.satellite-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.satellite-value {
  font-size: 16px;
  font-weight: 700;
  font-family: 'DIN Alternate', -apple-system, sans-serif;
}

.progress-bar {
  width: 100%;
  height: 4px;
  background: var(--bg-system);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 4px;
}

.progress-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.8s ease-out;
}

.satellite-desc {
  font-size: 11px;
  color: var(--text-muted);
}

/* Trend Section */
.trend-section {
  background: var(--bg-card);
  border-radius: 8px;
  padding: var(--spacing-md);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
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
  min-width: 80px;
}

.mobile-header-label {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
}

.mobile-header-value {
  font-size: 16px;
  font-weight: 700;
  font-family: 'DIN Alternate', -apple-system, sans-serif;
  color: var(--text-primary);
}

.mobile-header-status {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
}

.card-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-sm);
  border-bottom: 1px solid var(--border-line);
}

.trend-legend {
  display: flex;
  gap: var(--spacing-md);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.trend-container {
  width: 100%;
  height: 300px;
}

/* Factor Summary */
.factor-summary {
  background: var(--bg-card);
  border-radius: 8px;
  padding: var(--spacing-md);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.factor-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-md);
}

.factor-detail {
  padding: var(--spacing-sm);
  background: var(--bg-system);
  border-radius: 6px;
  transition: all 0.2s ease;
}

.factor-detail:hover {
  background: rgba(0, 51, 153, 0.04);
}

.factor-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.factor-detail-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.factor-detail-value {
  font-size: 18px;
  font-weight: 700;
  font-family: 'DIN Alternate', -apple-system, sans-serif;
}

.factor-detail-bar {
  width: 100%;
  height: 6px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 6px;
}

.factor-detail-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.8s ease-out;
}

.factor-detail-desc {
  font-size: 11px;
  color: var(--text-muted);
}

/* Empty State */
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
  .factor-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .topology-section {
    height: 600px;
  }
  
  .center-card {
    width: 220px;
    height: 220px;
  }
  
  .satellite-card {
    width: 110px;
    padding: 6px 10px;
  }
  
  .satellite-label {
    font-size: 11px;
  }
  
  .satellite-value {
    font-size: 14px;
  }
  
  .satellite-desc {
    font-size: 10px;
  }
  
  .factor-grid {
    grid-template-columns: 1fr;
  }
  
  .trend-legend {
    flex-wrap: wrap;
    gap: 8px;
  }
  
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .header-info {
    width: 100%;
    justify-content: space-between;
  }
}

@media (max-width: 480px) {
  .topology-section {
    height: 500px;
  }
  
  .center-card {
    width: 180px;
    height: 180px;
  }
  
  .satellite-card {
    width: 90px;
    padding: 4px 8px;
  }
}
</style>
