<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import type { ECharts } from 'echarts'
import { getFundIssueCalendar } from '@/api/fund'

// 基金发行数据类型
interface FundIssueItem {
  fund_code: string
  fund_name: string
  company: string
  subscribe_start: string
  subscribe_end: string
  status: '首发' | '即将发售' | '成立' | '退市'
  initial_scale: number | null
  fund_type: string
  manager: string
}

// 状态筛选选项
const statusOptions = [
  { label: '首发', value: '首发', color: '#003399' },
  { label: '即将发售', value: '即将发售', color: '#2E7D32' },
  { label: '成立', value: '成立', color: '#999999' },
  { label: '退市', value: '退市', color: '#E63935' },
]

// 当前选中的状态筛选
const selectedStatus = ref<string[]>([])

// 当前周的开始日期（周一）
const currentWeekStart = ref(getMonday(new Date()))

// 发行数据
const issueData = ref<FundIssueItem[]>([])
const loading = ref(false)

// ECharts 实例
let chartInstance: ECharts | null = null

// 获取周一日期
function getMonday(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  return new Date(d.setDate(diff))
}

// 格式化日期为 YYYY-MM-DD
function formatDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

// 获取本周的日期列表（周一至周日）
const weekDates = computed(() => {
  const dates: { date: Date; dateStr: string; dayName: string }[] = []
  const dayNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  
  for (let i = 0; i < 7; i++) {
    const d = new Date(currentWeekStart.value)
    d.setDate(d.getDate() + i)
    dates.push({
      date: d,
      dateStr: formatDate(d),
      dayName: dayNames[i],
    })
  }
  return dates
})

// 周范围显示文本
const weekRangeText = computed(() => {
  const start = weekDates.value[0].date
  const end = weekDates.value[6].date
  const startStr = `${start.getMonth() + 1}月${start.getDate()}日`
  const endStr = `${end.getMonth() + 1}月${end.getDate()}日`
  return `${startStr} - ${endStr}`
})

// 根据状态筛选后的数据
const filteredData = computed(() => {
  if (selectedStatus.value.length === 0) {
    return issueData.value
  }
  return issueData.value.filter(item => selectedStatus.value.includes(item.status))
})

// 按日期分组的发行数据
const dataByDate = computed(() => {
  const grouped: Record<string, FundIssueItem[]> = {}
  
  weekDates.value.forEach(d => {
    grouped[d.dateStr] = []
  })
  
  filteredData.value.forEach(item => {
    // 根据认购开始日期分组
    if (grouped[item.subscribe_start]) {
      grouped[item.subscribe_start].push(item)
    }
  })
  
  return grouped
})

// 统计数据
const statistics = computed(() => {
  const total = filteredData.value.length
  const byStatus: Record<string, number> = {}
  const byType: Record<string, number> = {}
  
  statusOptions.forEach(s => {
    byStatus[s.value] = 0
  })
  
  filteredData.value.forEach(item => {
    byStatus[item.status] = (byStatus[item.status] || 0) + 1
    byType[item.fund_type] = (byType[item.fund_type] || 0) + 1
  })
  
  return { total, byStatus, byType }
})

// 获取状态颜色
function getStatusColor(status: string): string {
  const option = statusOptions.find(o => o.value === status)
  return option ? option.color : '#999999'
}

// 格式化规模
function formatScale(val: number | null): string {
  if (val === null || val === undefined) return '-'
  return `${val.toFixed(2)}亿`
}

// 上一周
function prevWeek() {
  const d = new Date(currentWeekStart.value)
  d.setDate(d.getDate() - 7)
  currentWeekStart.value = getMonday(d)
  fetchIssueData()
}

// 下一周
function nextWeek() {
  const d = new Date(currentWeekStart.value)
  d.setDate(d.getDate() + 7)
  currentWeekStart.value = getMonday(d)
  fetchIssueData()
}

// 回到本周
function goToCurrentWeek() {
  currentWeekStart.value = getMonday(new Date())
  fetchIssueData()
}

// 获取发行数据
async function fetchIssueData() {
  loading.value = true
  try {
    const startDate = weekDates.value[0].dateStr
    const endDate = weekDates.value[6].dateStr
    
    const data = await getFundIssueCalendar()
    
    // Filter by date range and transform API response to match component interface
    const filteredByDate = data.filter(item => {
      const subStart = item.subscribe_start_date
      return subStart >= startDate && subStart <= endDate
    })
    
    // Map API response fields to component interface
    issueData.value = filteredByDate.map(item => ({
      fund_code: item.fund_code,
      fund_name: item.fund_name,
      company: item.company,
      subscribe_start: item.subscribe_start_date,
      subscribe_end: item.subscribe_end_date,
      status: item.status as FundIssueItem['status'],
      initial_scale: item.initial_scale,
      fund_type: '', // API doesn't provide this field
      manager: '', // API doesn't provide this field
    }))
    
    // 更新图表
    updateChart()
  } catch (error) {
    ElMessage.error('获取发行数据失败，请重试')
    issueData.value = []
    updateChart()
  } finally {
    loading.value = false
  }
}

// 初始化图表
function initChart() {
  const chartDom = document.getElementById('issue-timeline-chart')
  if (!chartDom) return
  
  chartInstance = echarts.init(chartDom)
  
  // 监听窗口大小变化
  window.addEventListener('resize', () => {
    chartInstance?.resize()
  })
}

// 更新图表
function updateChart() {
  if (!chartInstance) return
  
  // 按日期统计发行数量
  const dateCounts: number[] = weekDates.value.map(d => {
    return dataByDate.value[d.dateStr]?.length || 0
  })
  
  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#E5E8ED',
      textStyle: {
        color: '#1A1A1A',
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
      data: weekDates.value.map(d => d.dayName),
      axisLine: {
        lineStyle: {
          color: '#E5E8ED',
        },
      },
      axisLabel: {
        color: '#4A4A4A',
      },
    },
    yAxis: {
      type: 'value',
      name: '发行数量',
      nameTextStyle: {
        color: '#999999',
      },
      axisLine: {
        show: false,
      },
      axisLabel: {
        color: '#4A4A4A',
      },
      splitLine: {
        lineStyle: {
          color: '#E5E8ED',
          type: 'dashed',
        },
      },
    },
    series: [
      {
        name: '新发基金',
        type: 'bar',
        data: dateCounts,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#0B3CC3' },
            { offset: 1, color: '#003399' },
          ]),
          borderRadius: [4, 4, 0, 0],
        },
        emphasis: {
          itemStyle: {
            color: '#0B3CC3',
          },
        },
      },
    ],
  }
  
  chartInstance.setOption(option)
}

// 监听筛选变化，更新图表
watch(selectedStatus, () => {
  updateChart()
})

onMounted(() => {
  fetchIssueData()
  initChart()
})
</script>

<template>
  <div class="fund-issue">
    <!-- 统计摘要 -->
    <div class="summary-section">
      <div class="summary-card">
        <div class="summary-title">本周发行</div>
        <div class="summary-value">{{ statistics.total }}</div>
        <div class="summary-unit">只基金</div>
      </div>
      
      <div class="summary-card">
        <div class="summary-title">首发</div>
        <div class="summary-value status-primary">{{ statistics.byStatus['首发'] || 0 }}</div>
        <div class="summary-unit">只</div>
      </div>
      
      <div class="summary-card">
        <div class="summary-title">即将发售</div>
        <div class="summary-value status-success">{{ statistics.byStatus['即将发售'] || 0 }}</div>
        <div class="summary-unit">只</div>
      </div>
      
      <div class="summary-card">
        <div class="summary-title">已成立</div>
        <div class="summary-value status-muted">{{ statistics.byStatus['成立'] || 0 }}</div>
        <div class="summary-unit">只</div>
      </div>
      
      <div class="summary-card">
        <div class="summary-title">退市</div>
        <div class="summary-value status-danger">{{ statistics.byStatus['退市'] || 0 }}</div>
        <div class="summary-unit">只</div>
      </div>
    </div>
    
    <!-- 筛选和导航 -->
    <div class="filter-section">
      <div class="week-navigation">
        <el-button size="small" @click="prevWeek">
          <el-icon><arrow-left /></el-icon>
          上一周
        </el-button>
        <span class="week-range">{{ weekRangeText }}</span>
        <el-button size="small" @click="nextWeek">
          下一周
          <el-icon><arrow-right /></el-icon>
        </el-button>
        <el-button size="small" type="primary" plain @click="goToCurrentWeek">
          本周
        </el-button>
      </div>
      
      <div class="status-filter">
        <span class="filter-label">状态筛选：</span>
        <el-checkbox-group v-model="selectedStatus" size="small">
          <el-checkbox
            v-for="status in statusOptions"
            :key="status.value"
            :label="status.value"
          >
            <span
              class="status-badge"
              :style="{ backgroundColor: status.color }"
            >
              {{ status.label }}
            </span>
          </el-checkbox>
        </el-checkbox-group>
      </div>
    </div>
    
    <!-- 周历视图 -->
    <div class="calendar-section">
      <div class="calendar-header">
        <div
          v-for="day in weekDates"
          :key="day.dateStr"
          class="calendar-header-cell"
        >
          <div class="day-name">{{ day.dayName }}</div>
          <div class="day-date">{{ day.date.getDate() }}日</div>
        </div>
      </div>
      
      <div class="calendar-body">
        <div
          v-for="day in weekDates"
          :key="day.dateStr"
          class="calendar-column"
        >
          <div
            v-for="fund in dataByDate[day.dateStr]"
            :key="fund.fund_code"
            class="fund-card"
          >
            <div class="fund-header">
              <span class="fund-code">{{ fund.fund_code }}</span>
              <span
                class="fund-status"
                :style="{ backgroundColor: getStatusColor(fund.status) }"
              >
                {{ fund.status }}
              </span>
            </div>
            <div class="fund-name">{{ fund.fund_name }}</div>
            <div class="fund-info">
              <span class="fund-company">{{ fund.company }}</span>
            </div>
            <div class="fund-detail">
              <span class="fund-type">{{ fund.fund_type }}</span>
              <span class="fund-scale">{{ formatScale(fund.initial_scale) }}</span>
            </div>
            <div class="fund-dates">
              认购: {{ fund.subscribe_start }} ~ {{ fund.subscribe_end }}
            </div>
          </div>
          
          <div v-if="!dataByDate[day.dateStr]?.length" class="empty-day">
            暂无发行
          </div>
        </div>
      </div>
    </div>
    
    <!-- 发行趋势图 -->
    <div class="chart-section">
      <div class="section-title">本周发行趋势</div>
      <div id="issue-timeline-chart" class="chart-container"></div>
    </div>
  </div>
</template>

<style scoped>
.fund-issue {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: calc(100vh - 100px); /* Fallback for older browsers */
  height: calc(100dvh - 100px);
  overflow-y: auto;
}

/* 统计摘要 */
.summary-section {
  display: flex;
  gap: 16px;
}

.summary-card {
  flex: 1;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.summary-title {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.summary-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
}

.summary-value.status-primary {
  color: var(--brand-navy-dark);
}

.summary-value.status-success {
  color: var(--market-down);
}

.summary-value.status-muted {
  color: var(--market-flat);
}

.summary-value.status-danger {
  color: var(--market-up);
}

.summary-unit {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

/* 筛选和导航 */
.filter-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 12px 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.week-navigation {
  display: flex;
  align-items: center;
  gap: 12px;
}

.week-range {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  min-width: 160px;
  text-align: center;
}

.status-filter {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 13px;
  color: var(--text-regular);
}

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 12px;
  color: #fff;
}

/* 周历视图 */
.calendar-section {
  background: var(--bg-card);
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.calendar-header {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  background: #fafafa;
  border-bottom: 1px solid var(--border-line);
}

.calendar-header-cell {
  padding: 12px 8px;
  text-align: center;
  border-right: 1px solid var(--border-line);
}

.calendar-header-cell:last-child {
  border-right: none;
}

.day-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.day-date {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.calendar-body {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  min-height: 200px;
}

.calendar-column {
  padding: 8px;
  border-right: 1px solid var(--border-line);
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 200px;
  max-height: 400px;
  overflow-y: auto;
}

.calendar-column:last-child {
  border-right: none;
}

.fund-card {
  background: #fafafa;
  border-radius: 4px;
  padding: 10px;
  border: 1px solid var(--border-line);
  transition: all 0.2s;
}

.fund-card:hover {
  border-color: var(--brand-navy-active);
  box-shadow: 0 2px 8px rgba(0, 51, 153, 0.1);
}

.fund-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.fund-code {
  font-size: 12px;
  font-weight: 600;
  color: var(--brand-navy-dark);
}

.fund-status {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 2px;
  color: #fff;
}

.fund-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fund-info {
  font-size: 11px;
  color: var(--text-regular);
  margin-bottom: 4px;
}

.fund-detail {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.fund-dates {
  font-size: 10px;
  color: var(--text-muted);
}

.empty-day {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100px;
  color: var(--text-muted);
  font-size: 12px;
}

/* 图表区域 */
.chart-section {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-line);
}

.chart-container {
  height: 250px;
  width: 100%;
}
</style>