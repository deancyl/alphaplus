<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getCrowdingAnalysis } from '@/api/analytics'

// Crowding data type
interface CrowdingData {
  asset_code: string
  trade_date: string
  category: string
  crowding_score: number
  pe_percentile: number
  close_price: number | null
}

// Reactive state
const loading = ref(false)
const crowdingData = ref<CrowdingData[]>([])
const selectedCategory = ref('sector')

// Chart refs
const gaugeChart = ref<echarts.ECharts | null>(null)
const heatmapChart = ref<echarts.ECharts | null>(null)
const barChart = ref<echarts.ECharts | null>(null)
const trendChart = ref<echarts.ECharts | null>(null)

// Chart DOM refs
const gaugeChartRef = ref<HTMLElement | null>(null)
const heatmapChartRef = ref<HTMLElement | null>(null)
const barChartRef = ref<HTMLElement | null>(null)
const trendChartRef = ref<HTMLElement | null>(null)

// Category options
const categoryOptions = [
  { label: '行业板块', value: 'sector' },
  { label: '主题概念', value: 'concept' },
  { label: '宽基指数', value: 'index' },
]

// Crowding zone colors (from PRD)
const getCrowdingColor = (score: number): string => {
  if (score <= 30) return '#2E7D32' // 低拥挤 - green
  if (score <= 60) return '#999999' // 正常 - gray
  if (score <= 80) return '#FF9800' // 拥挤 - orange
  return '#E63935' // 极度拥挤 - red
}

const getCrowdingLabel = (score: number): string => {
  if (score <= 30) return '低拥挤'
  if (score <= 60) return '正常'
  if (score <= 80) return '拥挤'
  return '极度拥挤'
}

const getCrowdingBgClass = (score: number): string => {
  if (score <= 30) return 'status-low'
  if (score <= 60) return 'status-normal'
  if (score <= 80) return 'status-crowded'
  return 'status-extreme'
}

// Get unique dates (sorted)
const uniqueDates = computed(() => {
  const dates = [...new Set(crowdingData.value.map(d => d.trade_date))]
  return dates.sort()
})

// Get unique assets
const uniqueAssets = computed(() => {
  return [...new Set(crowdingData.value.map(d => d.asset_code))]
})

// Latest data (current crowding)
const latestData = computed(() => {
  if (uniqueDates.value.length === 0) return []
  const latestDate = uniqueDates.value[uniqueDates.value.length - 1]
  return crowdingData.value.filter(d => d.trade_date === latestDate)
})

// Composite crowding score (average of all assets)
const compositeScore = computed(() => {
  if (latestData.value.length === 0) return 0
  const sum = latestData.value.reduce((acc, d) => acc + d.crowding_score, 0)
  return Math.round(sum / latestData.value.length)
})

// Top 10 position concentration
const top10Concentration = computed(() => {
  if (latestData.value.length === 0) return []
  return [...latestData.value]
    .sort((a, b) => b.crowding_score - a.crowding_score)
    .slice(0, 10)
    .map(d => ({
      asset_code: d.asset_code,
      crowding_score: d.crowding_score,
      pe_percentile: d.pe_percentile,
    }))
})

// Format date
const formatDate = (dateStr: string): string => {
  if (!dateStr || dateStr.length < 8) return dateStr
  return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`
}

// Initialize gauge chart (crowding score 0-100)
const initGaugeChart = () => {
  if (!gaugeChartRef.value) return

  if (gaugeChart.value) {
    gaugeChart.value.dispose()
  }

  gaugeChart.value = echarts.init(gaugeChartRef.value)
  const score = compositeScore.value
  const color = getCrowdingColor(score)

  const option: echarts.EChartsOption = {
    series: [
      {
        type: 'gauge',
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        splitNumber: 4,
        radius: '100%',
        center: ['50%', '70%'],
        axisLine: {
          lineStyle: {
            width: 24,
            color: [
              [0.3, '#2E7D32'],
              [0.6, '#999999'],
              [0.8, '#FF9800'],
              [1, '#E63935'],
            ],
          },
        },
        pointer: {
          width: 6,
          length: '60%',
          itemStyle: {
            color: color,
          },
        },
        axisTick: {
          distance: -24,
          length: 6,
          lineStyle: {
            color: '#999',
            width: 1,
          },
        },
        splitLine: {
          distance: -24,
          length: 14,
          lineStyle: {
            color: '#999',
            width: 2,
          },
        },
        axisLabel: {
          distance: -40,
          color: '#4A4A4A',
          fontSize: 12,
          formatter: (value: number) => {
            if (value === 0) return '低拥挤'
            if (value === 30) return '正常'
            if (value === 60) return '拥挤'
            if (value === 80) return '极度拥挤'
            if (value === 100) return ''
            return ''
          },
        },
        detail: {
          valueAnimation: true,
          formatter: '{value}',
          fontSize: 40,
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

// Initialize heatmap chart (sector crowding over time)
const initHeatmapChart = () => {
  if (!heatmapChartRef.value || crowdingData.value.length === 0) return

  if (heatmapChart.value) {
    heatmapChart.value.dispose()
  }

  heatmapChart.value = echarts.init(heatmapChartRef.value)

  const dates = uniqueDates.value.slice(-20) // Last 20 dates
  const assets = uniqueAssets.value

  // Build heatmap data
  const heatmapData: Array<[number, number, number]> = []
  assets.forEach((asset, assetIndex) => {
    dates.forEach((date, dateIndex) => {
      const item = crowdingData.value.find(
        d => d.asset_code === asset && d.trade_date === date
      )
      heatmapData.push([dateIndex, assetIndex, item ? item.crowding_score : 0])
    })
  })

  const option: echarts.EChartsOption = {
    tooltip: {
      position: 'top',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#E5E8ED',
      borderWidth: 1,
      textStyle: {
        color: '#1A1A1A',
      },
      formatter: (params: unknown) => {
        const p = params as { data: [number, number, number] }
        const date = formatDate(dates[p.data[0]])
        const asset = assets[p.data[1]]
        const score = p.data[2]
        return `
          <div style="padding: 8px;">
            <div style="font-weight: 600; margin-bottom: 4px;">${date}</div>
            <div>${asset}: <strong>${score}</strong></div>
            <div style="color: ${getCrowdingColor(score)};">${getCrowdingLabel(score)}</div>
          </div>
        `
      },
    },
    grid: {
      left: '12%',
      right: '10%',
      bottom: '15%',
      top: '5%',
    },
    xAxis: {
      type: 'category',
      data: dates.map(d => formatDate(d).slice(5)),
      splitArea: {
        show: true,
      },
      axisLabel: {
        color: '#4A4A4A',
        fontSize: 10,
        rotate: 45,
      },
      axisLine: {
        lineStyle: {
          color: '#E5E8ED',
        },
      },
    },
    yAxis: {
      type: 'category',
      data: assets,
      splitArea: {
        show: true,
      },
      axisLabel: {
        color: '#4A4A4A',
        fontSize: 10,
      },
      axisLine: {
        lineStyle: {
          color: '#E5E8ED',
        },
      },
    },
    visualMap: {
      min: 0,
      max: 100,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '0%',
      inRange: {
        color: ['#2E7D32', '#8BC34A', '#FFEB3B', '#FF9800', '#E63935'],
      },
      text: ['极度拥挤', '低拥挤'],
      textStyle: {
        color: '#4A4A4A',
      },
    },
    series: [
      {
        type: 'heatmap',
        data: heatmapData,
        label: {
          show: false,
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
      },
    ],
  }

  heatmapChart.value.setOption(option)
}

// Initialize bar chart (stock position concentration)
const initBarChart = () => {
  if (!barChartRef.value || top10Concentration.value.length === 0) return

  if (barChart.value) {
    barChart.value.dispose()
  }

  barChart.value = echarts.init(barChartRef.value)

  const data = top10Concentration.value.slice().reverse()
  const labels = data.map(d => d.asset_code)
  const scores = data.map(d => d.crowding_score)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#E5E8ED',
      borderWidth: 1,
      textStyle: {
        color: '#1A1A1A',
      },
      formatter: (params: unknown) => {
        const p = params as Array<{ name: string; value: number; marker: string }>
        if (!p || p.length === 0) return ''
        const item = data.find(d => d.asset_code === p[0].name)
        return `
          <div style="padding: 8px;">
            <div style="font-weight: 600; margin-bottom: 4px;">${p[0].name}</div>
            <div>${p[0].marker} 拥挤度: <strong>${p[0].value}</strong></div>
            <div>PE分位: ${item?.pe_percentile.toFixed(1) || '-'}%</div>
          </div>
        `
      },
    },
    grid: {
      left: '3%',
      right: '8%',
      bottom: '3%',
      top: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLine: {
        lineStyle: {
          color: '#E5E8ED',
        },
      },
      axisLabel: {
        color: '#4A4A4A',
        fontSize: 11,
      },
      splitLine: {
        lineStyle: {
          color: '#E5E8ED',
          type: 'dashed',
        },
      },
    },
    yAxis: {
      type: 'category',
      data: labels,
      axisLine: {
        lineStyle: {
          color: '#E5E8ED',
        },
      },
      axisLabel: {
        color: '#4A4A4A',
        fontSize: 11,
      },
    },
    series: [
      {
        type: 'bar',
        data: scores.map(score => ({
          value: score,
          itemStyle: {
            color: getCrowdingColor(score),
          },
        })),
        barWidth: '60%',
        label: {
          show: true,
          position: 'right',
          color: '#4A4A4A',
          fontSize: 11,
          formatter: '{c}',
        },
      },
    ],
  }

  barChart.value.setOption(option)
}

// Initialize trend chart (historical crowding)
const initTrendChart = () => {
  if (!trendChartRef.value || crowdingData.value.length === 0) return

  if (trendChart.value) {
    trendChart.value.dispose()
  }

  trendChart.value = echarts.init(trendChartRef.value)

  // Calculate average crowding by date
  const dates = uniqueDates.value
  const avgScores = dates.map(date => {
    const dayData = crowdingData.value.filter(d => d.trade_date === date)
    if (dayData.length === 0) return 0
    return dayData.reduce((sum, d) => sum + d.crowding_score, 0) / dayData.length
  })

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
        const score = Math.round(p[0].value)
        return `
          <div style="padding: 8px;">
            <div style="font-weight: 600; margin-bottom: 4px;">${p[0].axisValue}</div>
            <div>${p[0].marker} 平均拥挤度: <strong>${score}</strong></div>
            <div style="color: ${getCrowdingColor(score)};">${getCrowdingLabel(score)}</div>
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
      data: dates.map(d => formatDate(d)),
      boundaryGap: false,
      axisLine: {
        lineStyle: {
          color: '#E5E8ED',
        },
      },
      axisLabel: {
        color: '#4A4A4A',
        fontSize: 10,
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
        { lte: 30, color: '#2E7D32' },
        { gt: 30, lte: 60, color: '#999999' },
        { gt: 60, lte: 80, color: '#FF9800' },
        { gt: 80, color: '#E63935' },
      ],
    },
    series: [
      {
        type: 'line',
        data: avgScores,
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: {
          width: 2,
          color: '#003399',
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 51, 153, 0.3)' },
            { offset: 1, color: 'rgba(0, 51, 153, 0.05)' },
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
            { yAxis: 30, lineStyle: { color: '#2E7D32' }, label: { formatter: '低拥挤', position: 'end' } },
            { yAxis: 60, lineStyle: { color: '#999999' }, label: { formatter: '正常', position: 'end' } },
            { yAxis: 80, lineStyle: { color: '#FF9800' }, label: { formatter: '拥挤', position: 'end' } },
          ],
        },
      },
    ],
  }

  trendChart.value.setOption(option)
}

// Fetch data from API
const fetchData = async () => {
  loading.value = true
  try {
    const response = await getCrowdingAnalysis(selectedCategory.value)
    crowdingData.value = response.sort((a, b) => 
      a.trade_date.localeCompare(b.trade_date)
    )
    
    // Initialize charts after data is loaded
    setTimeout(() => {
      initGaugeChart()
      initHeatmapChart()
      initBarChart()
      initTrendChart()
    }, 100)
  } catch (error) {
    ElMessage.error('获取市场拥挤度数据失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// Handle category change
const handleCategoryChange = () => {
  fetchData()
}

// Handle window resize
const handleResize = () => {
  gaugeChart.value?.resize()
  heatmapChart.value?.resize()
  barChart.value?.resize()
  trendChart.value?.resize()
}

// Latest date
const latestDate = computed(() => {
  if (uniqueDates.value.length === 0) return ''
  return formatDate(uniqueDates.value[uniqueDates.value.length - 1])
})

onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  gaugeChart.value?.dispose()
  heatmapChart.value?.dispose()
  barChart.value?.dispose()
  trendChart.value?.dispose()
})
</script>

<template>
  <div class="market-crowding" v-loading="loading">
    <!-- Header -->
    <div class="page-header">
      <h2>市场拥挤度分析</h2>
      <div class="header-actions">
        <span class="update-time" v-if="latestDate">
          更新时间: {{ latestDate }}
        </span>
        <el-select
          v-model="selectedCategory"
          placeholder="选择分类"
          size="default"
          @change="handleCategoryChange"
          style="width: 140px;"
        >
          <el-option
            v-for="opt in categoryOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </div>
    </div>

    <!-- Summary cards -->
    <div class="summary-cards">
      <div class="summary-card">
        <div class="summary-label">综合拥挤度</div>
        <div class="summary-value" :style="{ color: getCrowdingColor(compositeScore) }">
          {{ compositeScore }}
        </div>
        <el-tag :class="['status-tag', getCrowdingBgClass(compositeScore)]" size="small">
          {{ getCrowdingLabel(compositeScore) }}
        </el-tag>
      </div>
      <div class="summary-card">
        <div class="summary-label">监控资产数</div>
        <div class="summary-value">{{ uniqueAssets.length }}</div>
        <div class="summary-desc">个{{ categoryOptions.find(o => o.value === selectedCategory)?.label }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">高拥挤资产</div>
        <div class="summary-value text-warning">
          {{ latestData.filter(d => d.crowding_score > 60).length }}
        </div>
        <div class="summary-desc">拥挤度 &gt; 60</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">低拥挤资产</div>
        <div class="summary-value text-success">
          {{ latestData.filter(d => d.crowding_score <= 30).length }}
        </div>
        <div class="summary-desc">拥挤度 &le; 30</div>
      </div>
    </div>

    <!-- Main content -->
    <div class="content-grid" v-if="crowdingData.length > 0">
      <!-- Left: Gauge chart -->
      <div class="gauge-section card">
        <div class="card-title">综合拥挤度指数</div>
        <div class="gauge-container" ref="gaugeChartRef"></div>
        <div class="gauge-legend">
          <div class="legend-item">
            <span class="legend-color" style="background: #2E7D32;"></span>
            <span>低拥挤 (0-30)</span>
          </div>
          <div class="legend-item">
            <span class="legend-color" style="background: #999999;"></span>
            <span>正常 (30-60)</span>
          </div>
          <div class="legend-item">
            <span class="legend-color" style="background: #FF9800;"></span>
            <span>拥挤 (60-80)</span>
          </div>
          <div class="legend-item">
            <span class="legend-color" style="background: #E63935;"></span>
            <span>极度拥挤 (80-100)</span>
          </div>
        </div>
      </div>

      <!-- Right: Bar chart (Top 10 concentration) -->
      <div class="bar-section card">
        <div class="card-title">TOP10 拥挤度排名</div>
        <div class="bar-container" ref="barChartRef"></div>
      </div>

      <!-- Middle: Heatmap -->
      <div class="heatmap-section card">
        <div class="card-title">板块拥挤度热力图</div>
        <div class="heatmap-container" ref="heatmapChartRef"></div>
      </div>

      <!-- Bottom: Trend chart -->
      <div class="trend-section card">
        <div class="card-title">历史拥挤度趋势</div>
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
.market-crowding {
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.update-time {
  font-size: 13px;
  color: var(--text-muted);
}

/* Summary cards */
.summary-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.summary-card {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  text-align: center;
}

.summary-label {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.summary-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.summary-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.status-tag {
  font-weight: 600;
  border: none;
  margin-top: 8px;
}

.status-low {
  background-color: rgba(46, 125, 50, 0.15);
  color: #2E7D32;
}

.status-normal {
  background-color: rgba(153, 153, 153, 0.15);
  color: #666666;
}

.status-crowded {
  background-color: rgba(255, 152, 0, 0.15);
  color: #FF9800;
}

.status-extreme {
  background-color: rgba(230, 57, 53, 0.15);
  color: #E63935;
}

.text-success {
  color: #2E7D32;
}

.text-warning {
  color: #FF9800;
}

/* Content grid */
.content-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto auto auto;
  gap: 16px;
}

.gauge-section,
.bar-section,
.heatmap-section {
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

/* Gauge */
.gauge-container {
  width: 100%;
  height: 260px;
}

.gauge-legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 16px;
  margin-top: 12px;
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

/* Bar */
.bar-container {
  width: 100%;
  height: 320px;
}

/* Heatmap */
.heatmap-section {
  grid-column: 1 / -1;
}

.heatmap-container {
  width: 100%;
  height: 360px;
}

/* Trend */
.trend-container {
  width: 100%;
  height: 280px;
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
  color: var(--text-muted);
}

/* Responsive */
@media (max-width: 1400px) {
  .summary-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .content-grid {
    grid-template-columns: 1fr;
  }
  
  .trend-section {
    grid-column: 1;
  }
  
  .heatmap-section {
    grid-column: 1;
  }
}

@media (max-width: 768px) {
  .summary-cards {
    grid-template-columns: 1fr;
  }
  
  .header-actions {
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
  }
}
</style>