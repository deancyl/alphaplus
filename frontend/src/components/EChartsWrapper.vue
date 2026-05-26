<script setup lang="ts">
import { ref, shallowRef, onMounted, onUnmounted, watch, computed } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

interface Props {
  option: EChartsOption
  loading?: boolean
  height?: string
  manualUpdate?: boolean
  /**
   * Sparkline mode for table-embedded micro charts
   * When true: hides axes, grid, legend; sets compact dimensions
   */
  isSparkline?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  height: '400px',
  manualUpdate: false,
  isSparkline: false,
})

const chartRef = ref<HTMLDivElement | null>(null)
const chart = shallowRef<echarts.ECharts | null>(null)

/**
 * Compute effective height based on sparkline mode
 */
const effectiveHeight = computed(() => {
  return props.isSparkline ? '40px' : props.height
})

/**
 * Apply sparkline mode transformations to chart option
 */
const applySparklineMode = (option: EChartsOption): EChartsOption => {
  if (!props.isSparkline) return option

  // Build sparkline-specific options
  const sparklineOverrides: Partial<EChartsOption> = {
    // Hide grid lines and set zero margins
    grid: {
      left: 0,
      right: 0,
      top: 0,
      bottom: 0,
      containLabel: false,
    },
    // Hide X axis
    xAxis: {
      show: false,
    } as any,
    // Hide Y axis
    yAxis: {
      show: false,
    } as any,
    // Disable tooltip
    tooltip: { show: false },
    // Disable legend
    legend: { show: false },
  }

  // Apply sparkline styling to series
  if (Array.isArray(option.series)) {
    sparklineOverrides.series = option.series.map(s => ({
      ...s,
      lineStyle: {
        width: 1.5,
        ...((s as any).lineStyle || {}),
      },
      symbol: 'none', // Hide data points
      animation: false, // Disable animation for performance
    }))
  }

  // Merge: start with option, then apply sparkline overrides
  return { ...option, ...sparklineOverrides }
}

/**
 * Process the final chart option with all transformations
 */
const processedOption = computed(() => {
  let option = { ...props.option }
  option = applySparklineMode(option)
  return option
})

// 初始化图表
const initChart = () => {
  if (!chartRef.value) return
  
  chart.value = echarts.init(chartRef.value)
  
  if (!props.manualUpdate) {
    chart.value.setOption(processedOption.value)
  }
}

// 手动更新图表
const updateChart = (option: EChartsOption) => {
  if (chart.value) {
    chart.value.setOption(option, { notMerge: false })
  }
}

// 响应式调整
const handleResize = () => {
  chart.value?.resize()
}

// 监听option变化
watch(
  () => props.option,
  () => {
    if (chart.value && !props.manualUpdate) {
      chart.value.setOption(processedOption.value, { notMerge: false })
    }
  },
  { deep: true }
)

// 监听isSparkline变化
watch(
  () => props.isSparkline,
  () => {
    if (chart.value && !props.manualUpdate) {
      chart.value.setOption(processedOption.value, { notMerge: true })
    }
  }
)

// 监听loading状态
watch(
  () => props.loading,
  (isLoading) => {
    if (chart.value) {
      if (isLoading) {
        chart.value.showLoading({
          text: '加载中...',
          color: '#003399',
          maskColor: 'rgba(255, 255, 255, 0.8)',
        })
      } else {
        chart.value.hideLoading()
      }
    }
  }
)

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  chart.value?.dispose()
  window.removeEventListener('resize', handleResize)
})

// 暴露方法
defineExpose({
  updateChart,
  getChartInstance: () => chart.value,
})
</script>

<template>
  <div
    ref="chartRef"
    class="echarts-container"
    :style="{ height: effectiveHeight }"
  />
</template>

<style scoped>
.echarts-container {
  width: 100%;
  min-height: 200px;
}
</style>
