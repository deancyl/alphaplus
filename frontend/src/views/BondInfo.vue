<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getBondYieldCurve } from '@/api/market'
import { formatNumber } from '@/utils/formatters'
import ErrorBoundary from '@/components/ErrorBoundary.vue'

// 债券类型
const bondTypes = [
  { label: '国债', value: '国债' },
  { label: '国开债', value: '国开债' },
  { label: '农发债', value: '农发债' },
  { label: '进出债', value: '进出债' },
  { label: '信用债', value: '信用债' },
]

// 状态
const selectedBondType = ref('国债')
const searchKeyword = ref('')
const loading = ref(false)
const yieldCurveData = ref<Record<string, Array<{ tenor: number; yield_ytm: number }>>>({})
const selectedBond = ref<BondDetail | null>(null)
const bondList = ref<BondItem[]>([])
const chartInstance = ref<echarts.ECharts | null>(null)
const chartContainer = ref<HTMLElement | null>(null)

// 债券详情接口
interface BondDetail {
  bond_code: string
  bond_name: string
  bond_type: string
  issuer: string
  credit_rating: string
  yield_ytm: number
  duration: number
  issue_amount: number
  maturity_date: string
  coupon_rate: number
}

// 债券列表项接口
interface BondItem {
  bond_code: string
  bond_name: string
  bond_type: string
  issuer: string
  credit_rating: string
  yield_ytm: number
  duration: number
  issue_amount: number
}

// 过滤后的债券列表
const filteredBondList = computed(() => {
  let result = bondList.value
  
  if (selectedBondType.value !== '信用债') {
    result = result.filter(bond => bond.bond_type === selectedBondType.value)
  } else {
    result = result.filter(bond => bond.bond_type === '信用债')
  }
  
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter(bond => 
      bond.bond_code.toLowerCase().includes(keyword) ||
      bond.bond_name.toLowerCase().includes(keyword) ||
      bond.issuer.toLowerCase().includes(keyword)
    )
  }
  
  return result
})

// 获取收益率曲线数据
const fetchYieldCurve = async () => {
  loading.value = true
  try {
    const data = await getBondYieldCurve(selectedBondType.value)
    yieldCurveData.value = data
    await nextTick()
    renderYieldCurveChart()
  } catch (error) {
    ElMessage.error('获取收益率曲线失败')
  } finally {
    loading.value = false
  }
}

// 渲染收益率曲线图表
const renderYieldCurveChart = () => {
  if (!chartContainer.value) return
  
  if (!chartInstance.value) {
    chartInstance.value = echarts.init(chartContainer.value)
  }
  
  const curveData = yieldCurveData.value[selectedBondType.value] || []
  const sortedData = [...curveData].sort((a, b) => a.tenor - b.tenor)
  
  const xData = sortedData.map(d => `${d.tenor}Y`)
  const yData = sortedData.map(d => d.yield_ytm)
  
  const option: echarts.EChartsOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: 'var(--border-line)',
      borderWidth: 1,
      textStyle: {
        color: 'var(--text-primary)',
        fontSize: 12,
      },
      formatter: (params: unknown) => {
        const p = params as Array<{ axisValue: string; value: number }>
        if (!p || p.length === 0) return ''
        return `<div style="font-weight:600">${p[0].axisValue}</div>
                <div>收益率: <span style="color:var(--brand-navy-dark);font-weight:600">${p[0].value.toFixed(2)}%</span></div>`
      },
    },
    grid: {
      left: 50,
      right: 20,
      top: 30,
      bottom: 40,
    },
    xAxis: {
      type: 'category',
      data: xData,
      axisLine: {
        lineStyle: {
          color: 'var(--border-line)',
        },
      },
      axisTick: {
        show: false,
      },
      axisLabel: {
        color: 'var(--text-regular)',
        fontSize: 11,
      },
    },
    yAxis: {
      type: 'value',
      name: '收益率(%)',
      nameTextStyle: {
        color: 'var(--text-muted)',
        fontSize: 11,
        padding: [0, 0, 0, -10],
      },
      axisLine: {
        show: false,
      },
      axisTick: {
        show: false,
      },
      splitLine: {
        lineStyle: {
          color: 'var(--border-line)',
          type: 'dashed',
        },
      },
      axisLabel: {
        color: 'var(--text-regular)',
        fontSize: 11,
        formatter: '{value}',
      },
    },
    series: [
      {
        name: '收益率曲线',
        type: 'line',
        data: yData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: {
          color: 'var(--brand-navy-dark)',
          width: 2,
        },
        itemStyle: {
          color: 'var(--brand-navy-dark)',
          borderColor: '#fff',
          borderWidth: 2,
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 51, 153, 0.15)' },
            { offset: 1, color: 'rgba(0, 51, 153, 0.02)' },
          ]),
        },
      },
    ],
  }
  
  chartInstance.value.setOption(option)
}

// 选择债券
const handleSelectBond = (bond: BondItem) => {
  selectedBond.value = {
    ...bond,
    maturity_date: '2029-12-31',
    coupon_rate: bond.yield_ytm - 0.1,
  }
}

// 获取评级样式
const getRatingClass = (rating: string): string => {
  if (rating === 'AAA') return 'rating-aaa'
  if (rating.startsWith('AA')) return 'rating-aa'
  if (rating.startsWith('A')) return 'rating-a'
  return 'rating-bbb'
}

// 窗口大小变化时重绘图表
const handleResize = () => {
  chartInstance.value?.resize()
}

// 监听债券类型变化
watch(selectedBondType, () => {
  fetchYieldCurve()
  selectedBond.value = null
})

onMounted(() => {
  fetchYieldCurve()
  window.addEventListener('resize', handleResize)
})
</script>

<template>
  <ErrorBoundary error-message="债券信息加载失败">
    <div class="bond-info">
    <!-- 顶部搜索和类型选择 -->
    <div class="top-bar">
      <div class="search-box">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索债券代码/名称/发行人"
          clearable
          prefix-icon="Search"
          style="width: 300px"
        />
      </div>
      <div class="bond-type-tabs">
        <el-radio-group v-model="selectedBondType" size="default">
          <el-radio-button
            v-for="type in bondTypes"
            :key="type.value"
            :label="type.value"
          >
            {{ type.label }}
          </el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧：收益率曲线 -->
      <div class="yield-curve-panel">
        <div class="panel-header">
          <h3>{{ selectedBondType }}收益率曲线</h3>
          <span class="update-time">数据更新: 今日</span>
        </div>
        <div ref="chartContainer" class="chart-container" />
      </div>

      <!-- 右侧：债券详情 -->
      <div class="detail-panel">
        <div class="panel-header">
          <h3>债券详情</h3>
        </div>
        
        <div v-if="selectedBond" class="bond-detail-card">
          <div class="detail-header">
            <div class="bond-title">
              <span class="bond-name">{{ selectedBond.bond_name }}</span>
              <span class="bond-code">{{ selectedBond.bond_code }}</span>
            </div>
            <span :class="['rating-badge', getRatingClass(selectedBond.credit_rating)]">
              {{ selectedBond.credit_rating }}
            </span>
          </div>
          
          <div class="detail-grid">
            <div class="detail-item">
              <label>债券类型</label>
              <span class="value">{{ selectedBond.bond_type }}</span>
            </div>
            <div class="detail-item">
              <label>发行人</label>
              <span class="value">{{ selectedBond.issuer }}</span>
            </div>
            <div class="detail-item highlight">
              <label>到期收益率</label>
              <span class="value text-up">{{ formatNumber(selectedBond.yield_ytm, 2, '%') }}</span>
            </div>
            <div class="detail-item highlight">
              <label>久期</label>
              <span class="value">{{ formatNumber(selectedBond.duration, 2, '年') }}</span>
            </div>
            <div class="detail-item">
              <label>票面利率</label>
              <span class="value">{{ formatNumber(selectedBond.coupon_rate, 2, '%') }}</span>
            </div>
            <div class="detail-item">
              <label>发行规模</label>
              <span class="value">{{ selectedBond.issue_amount }}亿</span>
            </div>
            <div class="detail-item">
              <label>到期日</label>
              <span class="value">{{ selectedBond.maturity_date }}</span>
            </div>
          </div>
        </div>
        
        <div v-else class="empty-detail">
          <el-icon :size="48" color="var(--text-muted)">
            <svg viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
              <path fill="currentColor" d="M880 112H144c-17.7 0-32 14.3-32 32v736c0 17.7 14.3 32 32 32h736c17.7 0 32-14.3 32-32V144c0-17.7-14.3-32-32-32zm-40 728H184V184h656v656z"/>
              <path fill="currentColor" d="M492 400h-80c-4.4 0-8 3.6-8 8v240c0 4.4 3.6 8 8 8h80c4.4 0 8-3.6 8-8V408c0-4.4-3.6-8-8-8zm-40 224a24 24 0 1 1 0-48 24 24 0 0 1 0 48z"/>
            </svg>
          </el-icon>
          <p>请从下方列表选择债券查看详情</p>
        </div>
      </div>
    </div>

    <!-- 底部：债券列表 -->
    <div class="bond-list-panel">
      <div class="panel-header">
        <h3>{{ selectedBondType }}列表 ({{ filteredBondList.length }} 只)</h3>
      </div>
      
      <el-table
        :data="filteredBondList"
        :loading="loading"
        stripe
        height="280"
        @row-click="handleSelectBond"
      >
        <el-table-column
          prop="bond_code"
          label="债券代码"
          width="120"
          fixed
        ></el-table-column>
        <el-table-column
          prop="bond_name"
          label="债券名称"
          min-width="140"
          fixed
        ></el-table-column>
        <el-table-column
          prop="issuer"
          label="发行人"
          min-width="120"
        ></el-table-column>
        <el-table-column
          prop="credit_rating"
          label="信用评级"
          width="100"
        >
          <template #default="{ row }">
            <span :class="['rating-badge-small', getRatingClass(row.credit_rating)]">
              {{ row.credit_rating }}
            </span>
          </template>
        </el-table-column>
        <el-table-column
          prop="yield_ytm"
          label="到期收益率(%)"
          width="120"
          sortable
        >
          <template #default="{ row }">
            <span class="text-up">{{ formatNumber(row.yield_ytm) }}</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="duration"
          label="久期(年)"
          width="100"
          sortable
        >
          <template #default="{ row }">
            {{ formatNumber(row.duration) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="issue_amount"
          label="发行规模(亿)"
          width="120"
        >
          <template #default="{ row }">
            {{ row.issue_amount }}
          </template>
        </el-table-column>
        </el-table>
      </div>
    </div>
  </ErrorBoundary>
</template>

<style scoped>
.bond-info {
  height: calc(100vh - 100px); /* Fallback for older browsers */
  height: calc(100dvh - 100px);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 12px 16px;
}

.search-box {
  display: flex;
  align-items: center;
}

.bond-type-tabs {
  display: flex;
}

.main-content {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.yield-curve-panel {
  flex: 1;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.detail-panel {
  width: 360px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-line);
}

.panel-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.update-time {
  font-size: 12px;
  color: var(--text-muted);
}

.chart-container {
  flex: 1;
  min-height: 200px;
}

.bond-detail-card {
  flex: 1;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-line);
}

.bond-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bond-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.bond-code {
  font-size: 12px;
  color: var(--text-muted);
}

.rating-badge {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.rating-badge-small {
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
}

.rating-aaa {
  background: rgba(46, 125, 50, 0.1);
  color: #2E7D32;
}

.rating-aa {
  background: rgba(11, 60, 195, 0.1);
  color: #0B3CC3;
}

.rating-a {
  background: rgba(255, 152, 0, 0.1);
  color: #FF9800;
}

.rating-bbb {
  background: rgba(158, 158, 158, 0.1);
  color: #9E9E9E;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-item label {
  font-size: 12px;
  color: var(--text-muted);
}

.detail-item .value {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.detail-item.highlight .value {
  font-size: 16px;
  font-weight: 600;
}

.empty-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  gap: 12px;
}

.empty-detail p {
  font-size: 13px;
}

.bond-list-panel {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
}

:deep(.el-table) {
  --el-table-header-bg-color: #fafafa;
  --el-table-header-text-color: var(--text-primary);
  --el-table-row-hover-bg-color: #f5f7fa;
}

:deep(.el-table__row) {
  cursor: pointer;
}

:deep(.el-radio-button__inner) {
  padding: 8px 16px;
}

:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background-color: var(--brand-navy-dark);
  border-color: var(--brand-navy-dark);
}
</style>
