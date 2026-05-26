<script setup lang="ts">
import { ref, shallowRef, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

interface Props {
  option: EChartsOption
  loading?: boolean
  height?: string
  manualUpdate?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  height: '400px',
  manualUpdate: false,
})

const chartRef = ref<HTMLDivElement | null>(null)
const chart = shallowRef<echarts.ECharts | null>(null)

// 初始化图表
const initChart = () => {
  if (!chartRef.value) return
  
  chart.value = echarts.init(chartRef.value)
  
  if (!props.manualUpdate) {
    chart.value.setOption(props.option)
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
  (newOption) => {
    if (chart.value && !props.manualUpdate) {
      chart.value.setOption(newOption, { notMerge: false })
    }
  },
  { deep: true }
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
    :style="{ height }"
  />
</template>

<style scoped>
.echarts-container {
  width: 100%;
  min-height: 200px;
}
</style>
