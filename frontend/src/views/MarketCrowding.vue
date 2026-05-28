<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getCrowdingAnalysis, getRotationVectors } from '@/api/analytics'

// Crowding data type
interface CrowdingData {
  asset_code: string
  trade_date: string
  category: string
  crowding_score: number
  pe_percentile: number
  close_price: number | null
}

// Rotation vector type
interface RotationVector {
  asset_code: string
  asset_name: string
  t0_date: string
  t1_date: string
  t0_crowding: number
  t1_crowding: number
  t0_pe_percentile: number
  t1_pe_percentile: number
}

// Reactive state
const loading = ref(false)
const crowdingData = ref<CrowdingData[]>([])
const selectedCategory = ref('sector')

// Trajectory state
const trajectoryData = ref<RotationVector[]>([])
const trajectoryLoading = ref(false)
const t0Date = ref('')
const t1Date = ref('')
const isPlaying = ref(false)
const animationProgress = ref(0)
const animationSpeed = ref(1)
let animationInterval: ReturnType<typeof setInterval> | null = null

// Chart refs
const gaugeChart = ref<echarts.ECharts | null>(null)
const heatmapChart = ref<echarts.ECharts | null>(null)
const barChart = ref<echarts.ECharts | null>(null)
const trendChart = ref<echarts.ECharts | null>(null)
const trajectoryChart = ref<echarts.ECharts | null>(null)

// Chart DOM refs
const gaugeChartRef = ref<HTMLElement | null>(null)
const heatmapChartRef = ref<HTMLElement | null>(null)
const barChartRef = ref<HTMLElement | null>(null)
const trendChartRef = ref<HTMLElement | null>(null)
const trajectoryChartRef = ref<HTMLElement | null>(null)

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

// Z-Score calculation function
const calculateZScore = (value: number, historicalValues: number[]): number => {
  if (historicalValues.length === 0) return 0
  const mean = historicalValues.reduce((a, b) => a + b, 0) / historicalValues.length
  const variance = historicalValues.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / historicalValues.length
  const std = Math.sqrt(variance)
  return std > 0 ? (value - mean) / std : 0
}

// Z-Score alert level helper
const getZScoreAlertLevel = (zScore: number): 'alert' | 'warning' | 'underflow' | 'normal' => {
  if (zScore >= 2.0) return 'alert'      // HIGH ALERT - 极度拥挤
  if (zScore >= 1.5) return 'warning'    // WARNING - 拥挤警告
  if (zScore <= -2.0) return 'underflow' // UNDERFLOW - 极度冷清
  return 'normal'
}

const getZScoreLabel = (zScore: number): string => {
  const level = getZScoreAlertLevel(zScore)
  if (level === 'alert') return '极度拥挤'
  if (level === 'warning') return '拥挤警告'
  if (level === 'underflow') return '极度冷清'
  return '正常'
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
    .map(d => {
      // Calculate Z-Score for this asset
      const assetHistory = crowdingData.value.filter(item => item.asset_code === d.asset_code)
      const historicalScores = assetHistory.map(item => item.crowding_score)
      const zScore = calculateZScore(d.crowding_score, historicalScores)
      const zScoreLevel = getZScoreAlertLevel(zScore)
      const zScoreLabel = getZScoreLabel(zScore)
      
      return {
        asset_code: d.asset_code,
        crowding_score: d.crowding_score,
        pe_percentile: d.pe_percentile,
        zScore,
        zScoreLevel,
        zScoreLabel,
      }
    })
})

// Composite Z-Score for overall market
const compositeZScore = computed(() => {
  if (uniqueDates.value.length === 0 || uniqueDates.value.length < 10) return 0
  const historicalScores = uniqueDates.value.map(date => {
    const dayData = crowdingData.value.filter(d => d.trade_date === date)
    if (dayData.length === 0) return 0
    return dayData.reduce((sum, d) => sum + d.crowding_score, 0) / dayData.length
  })
  return calculateZScore(compositeScore.value, historicalScores)
})

const compositeZScoreLevel = computed(() => getZScoreAlertLevel(compositeZScore.value))
const compositeZScoreLabel = computed(() => getZScoreLabel(compositeZScore.value))

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
        const zScoreInfo = item?.zScoreLevel !== 'normal' 
          ? `<div style="color: ${item?.zScoreLevel === 'alert' ? '#E63935' : item?.zScoreLevel === 'warning' ? '#FFB300' : '#2E7D32'};">⚠️ Z-Score: ${item?.zScore.toFixed(2)} (${item?.zScoreLabel})</div>`
          : ''
        return `
          <div style="padding: 8px;">
            <div style="font-weight: 600; margin-bottom: 4px;">${p[0].name}</div>
            <div>${p[0].marker} 拥挤度: <strong>${p[0].value}</strong></div>
            <div>PE分位: ${item?.pe_percentile.toFixed(1) || '-'}%</div>
            ${zScoreInfo}
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
        formatter: (value: string) => {
          const item = data.find(d => d.asset_code === value)
          if (item && item.zScoreLevel !== 'normal') {
            return `${value} ⚠️`
          }
          return value
        },
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

// Initialize trajectory chart (phase space visualization)
const initTrajectoryChart = () => {
  if (!trajectoryChartRef.value) return

  if (trajectoryChart.value) {
    trajectoryChart.value.dispose()
  }

  trajectoryChart.value = echarts.init(trajectoryChartRef.value)

  // Build lines data from rotation vectors
  const linesData: Array<{
    coords: [[number, number], [number, number]]
    lineStyle?: { color: string; width: number }
  }> = trajectoryData.value.map((vector) => ({
    coords: [
      [vector.t0_crowding, vector.t0_pe_percentile],
      [vector.t1_crowding, vector.t1_pe_percentile],
    ] as [[number, number], [number, number]],
    lineStyle: {
      color: getCrowdingColor(vector.t1_crowding),
      width: 2,
    },
  }))

  // Build scatter data for start points (blue) and end points (red with glow)
  const startPoints = trajectoryData.value.map(vector => ({
    value: [vector.t0_crowding, vector.t0_pe_percentile, vector.asset_name],
    itemStyle: {
      color: '#3B82F6',
    },
  }))

  const endPoints = trajectoryData.value.map(vector => ({
    value: [vector.t1_crowding, vector.t1_pe_percentile, vector.asset_name],
    itemStyle: {
      color: '#E63935',
      shadowBlur: 10,
      shadowColor: 'rgba(230, 57, 53, 0.5)',
    },
  }))

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#E5E8ED',
      borderWidth: 1,
      textStyle: {
        color: '#1A1A1A',
      },
      formatter: (params: unknown) => {
        const p = params as { data: { value: [number, number, string] }; seriesName: string }
        if (!p || !p.data) return ''
        const [crowding, pe, name] = p.data.value
        return `
          <div style="padding: 8px;">
            <div style="font-weight: 600; margin-bottom: 4px;">${name}</div>
            <div>拥挤度: <strong>${crowding.toFixed(1)}</strong></div>
            <div>PE分位: <strong>${pe.toFixed(1)}%</strong></div>
            <div style="color: ${getCrowdingColor(crowding)};">${getCrowdingLabel(crowding)}</div>
          </div>
        `
      },
    },
    grid: {
      left: '8%',
      right: '4%',
      bottom: '12%',
      top: '8%',
      containLabel: true,
    },
    xAxis: {
      type: 'value',
      name: '拥挤度',
      nameLocation: 'middle',
      nameGap: 30,
      nameTextStyle: {
        color: '#4A4A4A',
        fontSize: 12,
      },
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
      type: 'value',
      name: 'PE分位 (%)',
      nameLocation: 'middle',
      nameGap: 40,
      nameTextStyle: {
        color: '#4A4A4A',
        fontSize: 12,
      },
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
    series: [
      // Four quadrant shading (using scatter with large symbol)
      {
        type: 'scatter',
        data: [
          // 低估+低拥挤 (bottom-left)
          { value: [25, 25], symbol: 'rect', symbolSize: 1000, itemStyle: { color: 'rgba(46, 125, 50, 0.08)' } },
          // 高估+低拥挤 (top-left)
          { value: [25, 75], symbol: 'rect', symbolSize: 1000, itemStyle: { color: 'rgba(255, 192, 105, 0.08)' } },
          // 低估+高拥挤 (bottom-right)
          { value: [75, 25], symbol: 'rect', symbolSize: 1000, itemStyle: { color: 'rgba(11, 60, 195, 0.08)' } },
          // 高估+高拥挤 (top-right)
          { value: [75, 75], symbol: 'rect', symbolSize: 1000, itemStyle: { color: 'rgba(230, 57, 53, 0.08)' } },
        ] as any,
        silent: true,
      },
      // Quadrant divider lines
      {
        type: 'line',
        data: [
          { coord: [50, 0] },
          { coord: [50, 100] },
        ] as any,
        lineStyle: {
          color: '#999999',
          width: 1,
          type: 'dashed',
        },
        silent: true,
      },
      {
        type: 'line',
        data: [
          { coord: [0, 50] },
          { coord: [100, 50] },
        ] as any,
        lineStyle: {
          color: '#999999',
          width: 1,
          type: 'dashed',
        },
        silent: true,
      },
      // Quadrant labels
      {
        type: 'scatter',
        data: [
          { value: [15, 15], label: { show: true, formatter: '低估+低拥挤', color: '#2E7D32', fontSize: 11 } },
          { value: [15, 85], label: { show: true, formatter: '高估+低拥挤', color: '#FF9800', fontSize: 11 } },
          { value: [85, 15], label: { show: true, formatter: '低估+高拥挤', color: '#0B3CC3', fontSize: 11 } },
          { value: [85, 85], label: { show: true, formatter: '高估+高拥挤', color: '#E63935', fontSize: 11 } },
        ],
        symbol: 'none',
        z: 10,
      },
      // Trajectory lines with arrows
      {
        type: 'lines',
        name: 'trajectory',
        coordinateSystem: 'cartesian2d',
        data: linesData,
        symbol: ['none', 'arrow'],
        symbolSize: [0, 8],
        lineStyle: {
          curveness: 0,
        },
        z: 5,
      },
      // Start points (blue)
      {
        type: 'scatter',
        name: 'start',
        data: startPoints,
        symbol: 'circle',
        symbolSize: 8,
        z: 6,
      },
      // End points (red with glow)
      {
        type: 'scatter',
        name: 'end',
        data: endPoints as any,
        symbol: 'circle',
        symbolSize: 10,
      },
    ] as any,
    graphic: [
      // Vertical line at x=50
      {
        type: 'line',
        z: 2,
        left: 'center',
        shape: {
          x1: trajectoryChartRef.value.offsetWidth / 2,
          y1: 40,
          x2: trajectoryChartRef.value.offsetWidth / 2,
          y2: trajectoryChartRef.value.offsetHeight - 40,
        },
        style: {
          stroke: '#999999',
          lineWidth: 1,
          lineDash: [5, 5],
        },
        silent: true,
      },
      // Horizontal line at y=50
      {
        type: 'line',
        z: 2,
        left: 'center',
        shape: {
          x1: 60,
          y1: trajectoryChartRef.value.offsetHeight / 2,
          x2: trajectoryChartRef.value.offsetWidth - 40,
          y2: trajectoryChartRef.value.offsetHeight / 2,
        },
        style: {
          stroke: '#999999',
          lineWidth: 1,
          lineDash: [5, 5],
        },
        silent: true,
      },
    ],
  }

  trajectoryChart.value.setOption(option)
}

// Fetch rotation vectors
const fetchRotationVectors = async () => {
  if (!t0Date.value || !t1Date.value) {
    // Set default dates if not set
    if (uniqueDates.value.length >= 2) {
      t0Date.value = uniqueDates.value[uniqueDates.value.length - 2]
      t1Date.value = uniqueDates.value[uniqueDates.value.length - 1]
    } else {
      return
    }
  }

  trajectoryLoading.value = true
  try {
    const response = await getRotationVectors(t0Date.value, t1Date.value, selectedCategory.value)
    trajectoryData.value = response
    
    setTimeout(() => {
      initTrajectoryChart()
    }, 100)
  } catch (error) {
    ElMessage.error('获取轨迹向量数据失败')
  } finally {
    trajectoryLoading.value = false
  }
}

// Animation controls
const togglePlay = () => {
  isPlaying.value = !isPlaying.value
  if (isPlaying.value) {
    startAnimation()
  } else {
    stopAnimation()
  }
}

const startAnimation = () => {
  if (animationInterval) {
    clearInterval(animationInterval)
  }
  
  const step = animationSpeed.value * 2
  animationInterval = setInterval(() => {
    animationProgress.value += step
    if (animationProgress.value >= 100) {
      animationProgress.value = 0
    }
    updateTrajectoryAnimation()
  }, 50)
}

const stopAnimation = () => {
  if (animationInterval) {
    clearInterval(animationInterval)
    animationInterval = null
  }
}

const updateTrajectoryAnimation = () => {
  if (!trajectoryChart.value || trajectoryData.value.length === 0) return
  
  const progress = animationProgress.value / 100
  
  // Interpolate positions based on progress
  const animatedLinesData = trajectoryData.value.map(vector => {
    const currentCrowding = vector.t0_crowding + (vector.t1_crowding - vector.t0_crowding) * progress
    const currentPe = vector.t0_pe_percentile + (vector.t1_pe_percentile - vector.t0_pe_percentile) * progress
    
    return {
      coords: [
        [vector.t0_crowding, vector.t0_pe_percentile],
        [currentCrowding, currentPe],
      ] as [[number, number], [number, number]],
      lineStyle: {
        color: getCrowdingColor(currentCrowding),
        width: 2,
      },
    }
  })
  
  trajectoryChart.value.setOption({
    series: [
      { type: 'lines', data: animatedLinesData },
    ],
  })
}

const handleSpeedChange = (speed: number) => {
  animationSpeed.value = speed
  if (isPlaying.value) {
    stopAnimation()
    startAnimation()
  }
}

const handleProgressChange = (progress: number) => {
  animationProgress.value = progress
  updateTrajectoryAnimation()
}

// Watch date changes
watch([t0Date, t1Date], () => {
  if (t0Date.value && t1Date.value) {
    fetchRotationVectors()
  }
})

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
      // Fetch rotation vectors after crowding data is loaded
      fetchRotationVectors()
    }, 100)
  } catch (error) {
    ElMessage.error('获取市场拥挤度数据失败')
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
  trajectoryChart.value?.resize()
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
  trajectoryChart.value?.dispose()
  stopAnimation()
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
      <div class="summary-card" :class="[`z-score-${compositeZScoreLevel}`]">
        <div class="summary-label">
          Z-Score
          <el-tooltip 
            content="Z-Score表示当前拥挤度偏离历史均值的标准差倍数。≥2.0表示极度异常拥挤，≤-2.0表示极度冷清。"
            placement="top"
          >
            <el-icon class="help-icon"><QuestionFilled /></el-icon>
          </el-tooltip>
        </div>
        <div class="summary-value" :class="`z-score-value-${compositeZScoreLevel}`">
          {{ compositeZScore.toFixed(2) }}
          <span v-if="compositeZScoreLevel !== 'normal'" class="warning-icon">⚠️</span>
        </div>
        <el-tag 
          v-if="compositeZScoreLevel !== 'normal'"
          :class="['z-score-tag', `z-score-tag-${compositeZScoreLevel}`]"
          size="small"
        >
          {{ compositeZScoreLabel }}
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

      <!-- Phase Space Trajectory -->
      <div class="trajectory-section card">
        <div class="card-title">
          <span>相空间轨迹分析</span>
          <div class="trajectory-controls">
            <el-date-picker
              v-model="t0Date"
              type="date"
              placeholder="起始日期"
              format="YYYY-MM-DD"
              value-format="YYYYMMDD"
              size="small"
              style="width: 130px;"
              :disabled-date="(date: Date) => date > new Date()"
            />
            <span class="date-separator">→</span>
            <el-date-picker
              v-model="t1Date"
              type="date"
              placeholder="结束日期"
              format="YYYY-MM-DD"
              value-format="YYYYMMDD"
              size="small"
              style="width: 130px;"
              :disabled-date="(date: Date) => date > new Date()"
            />
            <el-button
              :type="isPlaying ? 'danger' : 'primary'"
              size="small"
              @click="togglePlay"
              :icon="isPlaying ? 'VideoPause' : 'VideoPlay'"
            >
              {{ isPlaying ? '暂停' : '播放' }}
            </el-button>
            <el-select
              v-model="animationSpeed"
              size="small"
              style="width: 80px;"
              @change="handleSpeedChange"
            >
              <el-option label="0.5x" :value="0.5" />
              <el-option label="1x" :value="1" />
              <el-option label="2x" :value="2" />
            </el-select>
          </div>
        </div>
        <div class="trajectory-container" ref="trajectoryChartRef" v-loading="trajectoryLoading"></div>
        <div class="trajectory-progress" v-if="isPlaying">
          <el-slider
            v-model="animationProgress"
            :min="0"
            :max="100"
            :format-tooltip="(val: number) => `${val}%`"
            @change="handleProgressChange"
          />
        </div>
        <div class="trajectory-legend">
          <div class="legend-item">
            <span class="legend-dot" style="background: #3B82F6;"></span>
            <span>起始点 (T₀)</span>
          </div>
          <div class="legend-item">
            <span class="legend-dot" style="background: #E63935; box-shadow: 0 0 8px rgba(230, 57, 53, 0.5);"></span>
            <span>终点 (T₁)</span>
          </div>
          <div class="legend-item">
            <span class="legend-arrow">→</span>
            <span>旋转方向</span>
          </div>
        </div>
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

/* Z-Score Alert Styles */
.summary-card.z-score-alert {
  background: rgba(230, 57, 53, 0.1);
  border: 2px solid #E63935;
  animation: pulse 1.5s ease-in-out infinite;
}

.summary-card.z-score-warning {
  background: rgba(255, 179, 0, 0.1);
  border: 2px solid #FFB300;
}

.summary-card.z-score-underflow {
  background: rgba(46, 125, 50, 0.1);
  border: 2px solid #2E7D32;
}

.z-score-value-alert {
  color: #E63935 !important;
  font-weight: 700;
}

.z-score-value-warning {
  color: #FFB300 !important;
  font-weight: 600;
}

.z-score-value-underflow {
  color: #2E7D32 !important;
  font-weight: 600;
}

.z-score-tag {
  font-weight: 600;
  border: none;
  margin-top: 8px;
}

.z-score-tag-alert {
  background-color: #E63935;
  color: white;
}

.z-score-tag-warning {
  background-color: #FFB300;
  color: white;
}

.z-score-tag-underflow {
  background-color: #2E7D32;
  color: white;
}

.warning-icon {
  font-size: 18px;
  margin-left: 4px;
}

.help-icon {
  font-size: 14px;
  margin-left: 4px;
  color: var(--text-muted);
  cursor: help;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
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

/* Trajectory */
.trajectory-section {
  grid-column: 1 / -1;
}

.trajectory-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.date-separator {
  color: var(--text-muted);
  font-size: 13px;
}

.trajectory-container {
  width: 100%;
  height: 400px;
}

.trajectory-progress {
  padding: 8px 0;
  margin-top: 12px;
  border-top: 1px solid var(--border-line);
}

.trajectory-legend {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-line);
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 4px;
}

.legend-arrow {
  color: var(--brand-navy-dark);
  font-weight: bold;
  margin-right: 4px;
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