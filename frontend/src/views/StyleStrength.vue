<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getStyleStrength } from '@/api/analytics'

// Style strength data type
interface StyleStrengthItem {
  trade_date: string
  index_code_num: string
  index_code_den: string
  ratio_value: number
  percentile_rank_3y: number | null
}

// Style dimension configuration
interface StyleDimension {
  key: string
  label: string
  numerator: string
  denominator: string
  description: string
}

const styleDimensions: StyleDimension[] = [
  { key: 'value_growth', label: '价值成长', numerator: '000300', denominator: '399006', description: '沪深300/创业板指' },
  { key: 'large_small', label: '大盘小盘', numerator: '000300', denominator: '000905', description: '沪深300/中证500' },
  { key: 'cycle_defense', label: '周期防御', numerator: '000932', denominator: '399932', description: '中证上游/中证消费' },
  { key: 'growth_quality', label: '成长质量', numerator: '399006', denominator: '399324', description: '创业板指/深证红利' },
  { key: 'momentum_value', label: '动量价值', numerator: '399376', denominator: '399371', description: '大盘动量/大盘价值' },
  { key: 'high_dividend', label: '高红利', numerator: '000922', denominator: '399006', description: '中证红利/创业板指' },
]

// Reactive state
const loading = ref(false)
const styleData = ref<StyleStrengthItem[]>([])
const radarChart = ref<echarts.ECharts | null>(null)
const timelineChart = ref<echarts.ECharts | null>(null)
const selectedDimension = ref<string>('value_growth')

// Chart DOM refs
const radarChartRef = ref<HTMLElement | null>(null)
const timelineChartRef = ref<HTMLElement | null>(null)

// Process data into dimensions
const dimensionData = computed(() => {
  const result: Record<string, StyleStrengthItem[]> = {}
  
  for (const dim of styleDimensions) {
    result[dim.key] = styleData.value.filter(
      item => item.index_code_num === dim.numerator && item.index_code_den === dim.denominator
    ).sort((a, b) => a.trade_date.localeCompare(b.trade_date))
  }
  
  return result
})

// Current dimension data
const currentDimensionData = computed(() => {
  return dimensionData.value[selectedDimension.value] || []
})

// Latest values for radar with Z-Score alerts
const latestStyleScores = computed(() => {
  const scores: number[] = []
  
  for (const dim of styleDimensions) {
    const data = dimensionData.value[dim.key]
    if (data.length > 0) {
      const latest = data[data.length - 1]
      // Convert ratio to 0-100 scale based on percentile
      const percentile = latest.percentile_rank_3y ?? 50
      scores.push(Math.max(0, Math.min(100, percentile)))
    } else {
      scores.push(50) // Default neutral
    }
  }
  
  return scores
})

// Z-Score for each dimension
const dimensionZScores = computed(() => {
  const zScores: { zScore: number; level: 'alert' | 'warning' | 'underflow' | 'normal'; label: string }[] = []
  
  for (const dim of styleDimensions) {
    const data = dimensionData.value[dim.key]
    if (data.length > 0) {
      const latest = data[data.length - 1]
      const percentile = latest.percentile_rank_3y ?? 50
      const historicalPercentiles = data.map(d => d.percentile_rank_3y ?? 50)
      const zScore = calculateZScore(percentile, historicalPercentiles)
      const level = getZScoreAlertLevel(zScore)
      const label = getZScoreLabel(zScore)
      zScores.push({ zScore, level, label })
    } else {
      zScores.push({ zScore: 0, level: 'normal', label: '正常' })
    }
  }
  
  return zScores
})

// Dominant style (highest percentile)
const dominantStyle = computed(() => {
  const scores = latestStyleScores.value
  const maxIndex = scores.indexOf(Math.max(...scores))
  return styleDimensions[maxIndex]
})

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

// Current style recommendation
const styleRecommendation = computed(() => {
  const currentData = currentDimensionData.value
  if (currentData.length === 0) return null
  
  const latest = currentData[currentData.length - 1]
  const percentile = latest.percentile_rank_3y ?? 50
  const ratio = latest.ratio_value
  
  // Calculate Z-Score from historical percentiles
  const historicalPercentiles = currentData.map(d => d.percentile_rank_3y ?? 50)
  const zScore = calculateZScore(percentile, historicalPercentiles)
  const zScoreLevel = getZScoreAlertLevel(zScore)
  
  let recommendation = ''
  let strength = ''
  
  if (percentile >= 80) {
    recommendation = `${dominantStyle.value.label.split(/(?=[A-Z])/)[0]}极度强势`
    strength = 'extreme-strong'
  } else if (percentile >= 60) {
    recommendation = `${dominantStyle.value.label.split(/(?=[A-Z])/)[0]}偏强`
    strength = 'strong'
  } else if (percentile >= 40) {
    recommendation = '风格均衡'
    strength = 'neutral'
  } else if (percentile >= 20) {
    recommendation = `${dominantStyle.value.label.split(/(?=[A-Z])/)[1] || '对手方'}偏强`
    strength = 'weak'
  } else {
    recommendation = `${dominantStyle.value.label.split(/(?=[A-Z])/)[1] || '对手方'}极度强势`
    strength = 'extreme-weak'
  }
  
  return { recommendation, strength, percentile, ratio, zScore, zScoreLevel }
})

// Format date
const formatDate = (dateStr: string): string => {
  if (!dateStr || dateStr.length < 8) return dateStr
  return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`
}

// Initialize radar chart
const initRadarChart = () => {
  if (!radarChartRef.value) return

  if (radarChart.value) {
    radarChart.value.dispose()
  }

  radarChart.value = echarts.init(radarChartRef.value)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#E5E8ED',
      borderWidth: 1,
      textStyle: { color: '#1A1A1A' },
    },
    radar: {
      indicator: styleDimensions.map(dim => ({
        name: dim.label,
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
        lineStyle: { color: '#E5E8ED' },
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(255, 255, 255, 0)', 'rgba(0, 51, 153, 0.03)'],
        },
      },
      axisLine: {
        lineStyle: { color: '#E5E8ED' },
      },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: latestStyleScores.value,
            name: '风格强度',
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

// Initialize timeline chart
const initTimelineChart = () => {
  if (!timelineChartRef.value || currentDimensionData.value.length === 0) return

  if (timelineChart.value) {
    timelineChart.value.dispose()
  }

  timelineChart.value = echarts.init(timelineChartRef.value)

  const data = currentDimensionData.value
  const dates = data.map(d => formatDate(d.trade_date))
  const ratios = data.map(d => d.ratio_value)
  const percentiles = data.map(d => d.percentile_rank_3y ?? 50)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#E5E8ED',
      borderWidth: 1,
      textStyle: { color: '#1A1A1A' },
      axisPointer: { type: 'cross' },
      formatter: (params: unknown) => {
        const p = params as Array<{ axisValue: string; value: number; seriesName: string; marker: string }>
        if (!p || p.length === 0) return ''
        return `
          <div style="padding: 8px;">
            <div style="font-weight: 600; margin-bottom: 4px;">${p[0].axisValue}</div>
            ${p.map(item => `
              <div>${item.marker} ${item.seriesName}: <strong>${item.value.toFixed(2)}</strong></div>
            `).join('')}
          </div>
        `
      },
    },
    legend: {
      data: ['相对比值', '3年分位数'],
      top: 10,
      textStyle: { color: '#4A4A4A', fontSize: 12 },
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
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#E5E8ED' } },
      axisLabel: { color: '#4A4A4A', fontSize: 11, rotate: 45 },
      axisTick: { show: false },
    },
    yAxis: [
      {
        type: 'value',
        name: '相对比值',
        position: 'left',
        splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } },
        axisLine: { show: false },
        axisLabel: { color: '#4A4A4A', fontSize: 11 },
      },
      {
        type: 'value',
        name: '分位数(%)',
        min: 0,
        max: 100,
        position: 'right',
        splitLine: { show: false },
        axisLine: { show: false },
        axisLabel: { color: '#4A4A4A', fontSize: 11 },
      },
    ],
    series: [
      {
        name: '相对比值',
        type: 'line',
        data: ratios,
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { width: 2, color: '#003399' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 51, 153, 0.3)' },
            { offset: 1, color: 'rgba(0, 51, 153, 0.05)' },
          ]),
        },
      },
      {
        name: '3年分位数',
        type: 'line',
        yAxisIndex: 1,
        data: percentiles,
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { width: 2, color: '#E63935', type: 'dashed' },
        itemStyle: { color: '#E63935' },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { type: 'dotted', width: 1 },
          data: [
            { yAxis: 20, lineStyle: { color: '#2E7D32' }, label: { formatter: '低估值区', position: 'end' } },
            { yAxis: 80, lineStyle: { color: '#E63935' }, label: { formatter: '高估值区', position: 'end' } },
          ],
        },
      },
    ],
  }

  timelineChart.value.setOption(option)
}

// Fetch data from API
const fetchData = async () => {
  loading.value = true
  try {
    const response = await getStyleStrength()
    styleData.value = response
    
    // Initialize charts after data is loaded
    setTimeout(() => {
      initRadarChart()
      initTimelineChart()
    }, 100)
  } catch (error) {
    ElMessage.error('获取市场风格强度数据失败')
  } finally {
    loading.value = false
  }
}

// Handle dimension change
const handleDimensionChange = (key: string) => {
  selectedDimension.value = key
  setTimeout(() => {
    initTimelineChart()
  }, 50)
}

// Handle window resize
const handleResize = () => {
  radarChart.value?.resize()
  timelineChart.value?.resize()
}

// Watch for dimension data changes
watch(currentDimensionData, () => {
  setTimeout(() => {
    initTimelineChart()
  }, 50)
})

onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  radarChart.value?.dispose()
  timelineChart.value?.dispose()
})
</script>

<template>
  <div class="style-strength" v-loading="loading">
    <!-- Header -->
    <div class="page-header">
      <h2>市场风格强度</h2>
      <div class="header-info">
        <span class="update-time" v-if="currentDimensionData.length > 0">
          更新时间: {{ formatDate(currentDimensionData[currentDimensionData.length - 1].trade_date) }}
        </span>
        <el-tag 
          v-if="styleRecommendation"
          :class="['recommendation-tag', `tag-${styleRecommendation.strength}`, `z-score-tag-${styleRecommendation.zScoreLevel}`]"
          size="large"
        >
          <span v-if="styleRecommendation.zScoreLevel !== 'normal'" class="tag-warning-icon">⚠️</span>
          {{ styleRecommendation.recommendation }}
          <el-tooltip 
            v-if="styleRecommendation.zScoreLevel !== 'normal'"
            :content="`Z-Score: ${styleRecommendation.zScore.toFixed(2)} (${styleRecommendation.zScoreLevel === 'alert' ? '极度拥挤' : styleRecommendation.zScoreLevel === 'warning' ? '拥挤警告' : '极度冷清'})`"
            placement="bottom"
          >
            <el-icon class="info-icon"><QuestionFilled /></el-icon>
          </el-tooltip>
        </el-tag>
      </div>
    </div>

    <!-- Main content -->
    <div class="content-grid" v-if="currentDimensionData.length > 0">
      <!-- Left: Radar chart -->
      <div class="radar-section card">
        <div class="card-title">风格强度雷达</div>
        <div class="radar-container" ref="radarChartRef"></div>
        <div class="dominant-style">
          <span class="label">当前主导风格:</span>
          <span class="value">{{ dominantStyle.label }}</span>
        </div>
      </div>

      <!-- Right: Style dimensions -->
      <div class="dimensions-section card">
        <div class="card-title">风格维度选择</div>
        <div class="dimension-list">
          <div 
            v-for="(dim, index) in styleDimensions" 
            :key="dim.key"
            :class="['dimension-item', { active: selectedDimension === dim.key, [`z-score-${dimensionZScores[index].level}`]: dimensionZScores[index].level !== 'normal' }]"
            @click="handleDimensionChange(dim.key)"
          >
            <div class="dimension-header">
              <span class="dimension-label">{{ dim.label }}</span>
              <span class="dimension-score">
                {{ latestStyleScores[index].toFixed(0) }}%
                <el-tooltip 
                  v-if="dimensionZScores[index].level !== 'normal'"
                  :content="`Z-Score: ${dimensionZScores[index].zScore.toFixed(2)} - ${dimensionZScores[index].label}。Z-Score表示当前值偏离历史均值的标准差倍数，≥2.0表示极度异常。`"
                  placement="top"
                >
                  <span class="warning-icon">⚠️</span>
                </el-tooltip>
              </span>
            </div>
            <div class="dimension-desc">{{ dim.description }}</div>
            <div class="dimension-bar">
              <div 
                class="bar-fill" 
                :style="{ width: `${latestStyleScores[index]}%` }"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Style rotation matrix -->
      <div class="rotation-section card">
        <div class="card-title">风格轮动矩阵</div>
        <div class="rotation-grid">
          <div 
            v-for="dim in styleDimensions.slice(0, 4)" 
            :key="dim.key"
            :class="['rotation-cell', `strength-${Math.floor(latestStyleScores[styleDimensions.findIndex(d => d.key === dim.key)] / 20)}`]"
          >
            <div class="cell-label">{{ dim.label }}</div>
            <div class="cell-value">
              {{ latestStyleScores[styleDimensions.findIndex(d => d.key === dim.key)].toFixed(0) }}
            </div>
            <div class="cell-status">
              {{ latestStyleScores[styleDimensions.findIndex(d => d.key === dim.key)] >= 60 ? '强' : 
                 latestStyleScores[styleDimensions.findIndex(d => d.key === dim.key)] >= 40 ? '中' : '弱' }}
            </div>
          </div>
        </div>
        <div class="rotation-legend">
          <span class="legend-item"><span class="dot strong"></span>强势 (≥60)</span>
          <span class="legend-item"><span class="dot neutral"></span>均衡 (40-60)</span>
          <span class="legend-item"><span class="dot weak"></span>弱势 (&lt;40)</span>
        </div>
      </div>

      <!-- Bottom: Timeline chart -->
      <div class="timeline-section card">
        <div class="card-title">
          历史趋势 - {{ styleDimensions.find(d => d.key === selectedDimension)?.label }}
        </div>
        <div class="timeline-container" ref="timelineChartRef"></div>
      </div>
    </div>

    <!-- Empty state -->
    <div class="empty-state" v-else-if="!loading">
      <p>暂无数据</p>
    </div>
  </div>
</template>

<style scoped>
.style-strength {
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

.update-time {
  font-size: 13px;
  color: var(--text-muted);
}

.recommendation-tag {
  font-weight: 600;
  border: none;
}

.tag-extreme-strong {
  background-color: rgba(230, 57, 53, 0.15);
  color: #E63935;
}

.tag-strong {
  background-color: rgba(255, 152, 0, 0.15);
  color: #FF9800;
}

.tag-neutral {
  background-color: rgba(153, 153, 153, 0.15);
  color: #666666;
}

.tag-weak {
  background-color: rgba(46, 125, 50, 0.15);
  color: #2E7D32;
}

.tag-extreme-weak {
  background-color: rgba(21, 101, 192, 0.15);
  color: #1565C0;
}

.content-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto auto auto;
  gap: 16px;
}

.card {
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

.radar-section,
.dimensions-section {
  min-height: 380px;
}

.radar-container {
  width: 100%;
  height: 260px;
}

.dominant-style {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border-line);
}

.dominant-style .label {
  font-size: 13px;
  color: var(--text-regular);
}

.dominant-style .value {
  font-size: 15px;
  font-weight: 600;
  color: #003399;
}

.dimension-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 300px;
  overflow-y: auto;
}

.dimension-item {
  padding: 12px;
  background: var(--bg-system);
  border-radius: 4px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.2s ease;
}

.dimension-item:hover {
  background: var(--bg-system);
  border-color: #003399;
}

.dimension-item.active {
  border-color: #003399;
  background: rgba(0, 51, 153, 0.05);
}

.dimension-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.dimension-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.dimension-score {
  font-size: 14px;
  font-weight: 600;
  color: #003399;
}

.dimension-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.dimension-bar {
  height: 4px;
  background: #E5E8ED;
  border-radius: 2px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #003399, #1565C0);
  border-radius: 2px;
  transition: width 0.3s ease;
}

/* Z-Score Alert Styles */
.dimension-item.z-score-alert {
  background: rgba(230, 57, 53, 0.1);
  border-color: #E63935 !important;
  animation: pulse 1.5s ease-in-out infinite;
}

.dimension-item.z-score-warning {
  background: rgba(255, 179, 0, 0.1);
  border-color: #FFB300 !important;
}

.dimension-item.z-score-underflow {
  background: rgba(46, 125, 50, 0.1);
  border-color: #2E7D32 !important;
}

.warning-icon {
  font-size: 16px;
  margin-left: 4px;
  cursor: help;
}

.tag-warning-icon {
  margin-right: 4px;
}

.info-icon {
  margin-left: 4px;
  font-size: 14px;
  cursor: help;
}

.z-score-tag-alert {
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.rotation-section {
  grid-column: 1 / -1;
}

.rotation-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.rotation-cell {
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  transition: transform 0.2s ease;
}

.rotation-cell:hover {
  transform: scale(1.02);
}

.strength-0, .strength-1 {
  background: linear-gradient(135deg, rgba(21, 101, 192, 0.15), rgba(21, 101, 192, 0.05));
  border: 1px solid rgba(21, 101, 192, 0.3);
}

.strength-2 {
  background: linear-gradient(135deg, rgba(153, 153, 153, 0.15), rgba(153, 153, 153, 0.05));
  border: 1px solid rgba(153, 153, 153, 0.3);
}

.strength-3, .strength-4 {
  background: linear-gradient(135deg, rgba(230, 57, 53, 0.15), rgba(230, 57, 53, 0.05));
  border: 1px solid rgba(230, 57, 53, 0.3);
}

.cell-label {
  font-size: 13px;
  color: var(--text-regular);
  margin-bottom: 8px;
}

.cell-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.cell-status {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 12px;
  display: inline-block;
}

.strength-0 .cell-status, .strength-1 .cell-status {
  background: rgba(21, 101, 192, 0.2);
  color: #1565C0;
}

.strength-2 .cell-status {
  background: rgba(153, 153, 153, 0.2);
  color: #666666;
}

.strength-3 .cell-status, .strength-4 .cell-status {
  background: rgba(230, 57, 53, 0.2);
  color: #E63935;
}

.rotation-legend {
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
  gap: 6px;
  font-size: 12px;
  color: var(--text-regular);
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.dot.strong {
  background: #E63935;
}

.dot.neutral {
  background: #999999;
}

.dot.weak {
  background: #1565C0;
}

.timeline-section {
  grid-column: 1 / -1;
}

.timeline-container {
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
  
  .rotation-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .rotation-grid {
    grid-template-columns: 1fr;
  }
}
</style>
