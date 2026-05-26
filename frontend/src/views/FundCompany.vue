<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import type { EChartsOption } from 'echarts'
import { getFundCompanies } from '@/api/fund'

// Types
interface CompanyItem {
  company_id: string
  company_name: string
  establish_date: string | null
  total_scale: number | null
  non_money_scale: number | null
  fund_count: number | null
  manager_count: number | null
}

interface FilterParams {
  scale_min: number | undefined
  scale_max: number | undefined
  fund_count_min: number | undefined
  fund_count_max: number | undefined
  sort_by: 'total_scale' | 'fund_count' | 'manager_count'
  sort_order: 'asc' | 'desc'
}

// State
const companies = ref<CompanyItem[]>([])
const filteredCompanies = ref<CompanyItem[]>([])
const loading = ref(false)
const selectedCompany = ref<CompanyItem | null>(null)
const showDetailDialog = ref(false)

// Filter params
const filterParams = ref<FilterParams>({
  scale_min: undefined,
  scale_max: undefined,
  fund_count_min: undefined,
  fund_count_max: undefined,
  sort_by: 'total_scale',
  sort_order: 'desc',
})

// Chart options - initialize with empty series data
const pieChartOption = ref<EChartsOption>({
  tooltip: { trigger: 'item' },
  legend: { orient: 'vertical', right: 10 },
  series: [{ type: 'pie', data: [] }],
})

const barChartOption = ref<EChartsOption>({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'value' },
  yAxis: { type: 'category', data: [] },
  series: [{ type: 'bar', data: [] }],
})

// Sort options
const sortOptions = [
  { label: '按总规模', value: 'total_scale' },
  { label: '按基金数量', value: 'fund_count' },
  { label: '按经理人数', value: 'manager_count' },
]

// Format helpers
const formatNumber = (val: number | null, suffix = ''): string => {
  if (val === null || val === undefined) return '-'
  return `${val.toFixed(2)}${suffix}`
}

const formatInteger = (val: number | null): string => {
  if (val === null || val === undefined) return '-'
  return String(val)
}

const formatDate = (date: string | null): string => {
  if (!date) return '-'
  return date.substring(0, 10)
}

// Statistics
const totalStats = computed(() => {
  const data = filteredCompanies.value
  if (data.length === 0) {
    return { totalScale: 0, totalFunds: 0, totalManagers: 0, avgScale: 0 }
  }
  const totalScale = data.reduce((sum, c) => sum + (c.total_scale || 0), 0)
  const totalFunds = data.reduce((sum, c) => sum + (c.fund_count || 0), 0)
  const totalManagers = data.reduce((sum, c) => sum + (c.manager_count || 0), 0)
  return {
    totalScale,
    totalFunds,
    totalManagers,
    avgScale: totalScale / data.length,
  }
})

// Fetch data
const fetchData = async () => {
  loading.value = true
  try {
    const response = await getFundCompanies()
    companies.value = response
    applyFilters()
  } catch (error) {
    ElMessage.error('获取基金公司数据失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// Apply filters and sorting
const applyFilters = () => {
  let result = [...companies.value]

  // Scale filter
  if (filterParams.value.scale_min !== undefined) {
    result = result.filter(c => (c.total_scale || 0) >= filterParams.value.scale_min!)
  }
  if (filterParams.value.scale_max !== undefined) {
    result = result.filter(c => (c.total_scale || 0) <= filterParams.value.scale_max!)
  }

  // Fund count filter
  if (filterParams.value.fund_count_min !== undefined) {
    result = result.filter(c => (c.fund_count || 0) >= filterParams.value.fund_count_min!)
  }
  if (filterParams.value.fund_count_max !== undefined) {
    result = result.filter(c => (c.fund_count || 0) <= filterParams.value.fund_count_max!)
  }

  // Sort
  const sortKey = filterParams.value.sort_by
  const sortOrder = filterParams.value.sort_order
  result.sort((a, b) => {
    const aVal = a[sortKey] || 0
    const bVal = b[sortKey] || 0
    return sortOrder === 'desc' ? bVal - aVal : aVal - bVal
  })

  filteredCompanies.value = result
  updateCharts()
}

// Update charts
const updateCharts = () => {
  const data = filteredCompanies.value

  // Pie chart - top 10 by scale
  const top10ForPie = data.slice(0, 10)
  const pieData = top10ForPie.map(c => ({
    name: c.company_name,
    value: c.total_scale || 0,
  }))
  
  // Add "其他" category if more than 10
  if (data.length > 10) {
    const otherScale = data.slice(10).reduce((sum, c) => sum + (c.total_scale || 0), 0)
    pieData.push({ name: '其他', value: otherScale })
  }

  pieChartOption.value = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}亿 ({d}%)',
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 10,
      top: 20,
      bottom: 20,
      textStyle: { fontSize: 12 },
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['40%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 4,
        borderColor: '#fff',
        borderWidth: 2,
      },
      label: { show: false },
      emphasis: {
        label: {
          show: true,
          fontSize: 14,
          fontWeight: 'bold',
        },
      },
      labelLine: { show: false },
      data: pieData,
    }],
  }

  // Bar chart - top 10 by AUM (horizontal)
  const top10ForBar = [...data]
    .sort((a, b) => (b.total_scale || 0) - (a.total_scale || 0))
    .slice(0, 10)
    .reverse()

  barChartOption.value = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    grid: {
      left: 120,
      right: 30,
      top: 20,
      bottom: 30,
    },
    xAxis: {
      type: 'value',
      name: '规模(亿)',
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'category',
      axisLabel: { fontSize: 11, width: 100, overflow: 'truncate' },
      data: top10ForBar.map(c => c.company_name),
    },
    series: [{
      type: 'bar',
      barWidth: '60%',
      itemStyle: {
        color: '#003399',
        borderRadius: [0, 4, 4, 0],
      },
      data: top10ForBar.map(c => c.total_scale || 0),
    }],
  }
}

// Handle filter
const handleFilter = () => {
  applyFilters()
}

// Reset filters
const handleReset = () => {
  filterParams.value = {
    scale_min: undefined,
    scale_max: undefined,
    fund_count_min: undefined,
    fund_count_max: undefined,
    sort_by: 'total_scale',
    sort_order: 'desc',
  }
  applyFilters()
}

// Handle row click
const handleRowClick = (row: CompanyItem) => {
  selectedCompany.value = row
  showDetailDialog.value = true
}

// Handle sort change
const handleSortChange = ({ prop, order }: { prop: string; order: string | null }) => {
  if (prop && ['total_scale', 'fund_count', 'manager_count'].includes(prop)) {
    filterParams.value.sort_by = prop as FilterParams['sort_by']
    filterParams.value.sort_order = order === 'ascending' ? 'asc' : 'desc'
    applyFilters()
  }
}

// Watch filter params
watch(
  () => filterParams.value.sort_by,
  () => applyFilters()
)

watch(
  () => filterParams.value.sort_order,
  () => applyFilters()
)

onMounted(() => {
  fetchData()
})
</script>

<template>
  <div class="fund-company">
    <!-- Header Stats -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-value">{{ formatNumber(totalStats.totalScale, '亿') }}</div>
        <div class="stat-label">总管理规模</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ formatInteger(totalStats.totalFunds) }}</div>
        <div class="stat-label">基金总数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ formatInteger(totalStats.totalManagers) }}</div>
        <div class="stat-label">基金经理</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ formatNumber(totalStats.avgScale, '亿') }}</div>
        <div class="stat-label">平均规模</div>
      </div>
    </div>

    <div class="main-content">
      <!-- Left: Filter Panel -->
      <div class="filter-panel">
        <div class="panel-header">
          <h3>筛选条件</h3>
        </div>

        <div class="filter-form">
          <div class="filter-section">
            <h4>规模范围 (亿)</h4>
            <div class="range-input">
              <el-input-number
                v-model="filterParams.scale_min"
                :min="0"
                :controls="false"
                placeholder="最小"
                size="small"
              />
              <span class="separator">-</span>
              <el-input-number
                v-model="filterParams.scale_max"
                :min="0"
                :controls="false"
                placeholder="最大"
                size="small"
              />
            </div>
          </div>

          <div class="filter-section">
            <h4>基金数量范围</h4>
            <div class="range-input">
              <el-input-number
                v-model="filterParams.fund_count_min"
                :min="0"
                :controls="false"
                placeholder="最小"
                size="small"
              />
              <span class="separator">-</span>
              <el-input-number
                v-model="filterParams.fund_count_max"
                :min="0"
                :controls="false"
                placeholder="最大"
                size="small"
              />
            </div>
          </div>

          <div class="filter-section">
            <h4>排序方式</h4>
            <el-select v-model="filterParams.sort_by" size="small" style="width: 100%">
              <el-option
                v-for="opt in sortOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
            <div class="sort-order">
              <el-radio-group v-model="filterParams.sort_order" size="small">
                <el-radio-button label="desc">降序</el-radio-button>
                <el-radio-button label="asc">升序</el-radio-button>
              </el-radio-group>
            </div>
          </div>

          <div class="filter-actions">
            <el-button type="primary" size="small" @click="handleFilter">
              筛选
            </el-button>
            <el-button size="small" @click="handleReset">
              重置
            </el-button>
          </div>
        </div>
      </div>

      <!-- Center: Company Table -->
      <div class="table-panel">
        <div class="panel-header">
          <h3>基金公司列表 ({{ filteredCompanies.length }} 家)</h3>
        </div>

        <el-table
          :data="filteredCompanies"
          :loading="loading"
          stripe
          height="calc(100vh - 320px)"
          @row-click="handleRowClick"
          @sort-change="handleSortChange"
        >
          <el-table-column
            type="index"
            label="排名"
            width="60"
          />
          <el-table-column
            prop="company_name"
            label="公司名称"
            min-width="180"
            fixed
          >
            <template #default="{ row }">
              <span class="company-name">{{ row.company_name }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="total_scale"
            label="总规模(亿)"
            width="120"
            sortable="custom"
          >
            <template #default="{ row }">
              <span class="scale-value">{{ formatNumber(row.total_scale) }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="non_money_scale"
            label="非货规模(亿)"
            width="120"
          >
            <template #default="{ row }">
              {{ formatNumber(row.non_money_scale) }}
            </template>
          </el-table-column>
          <el-table-column
            prop="fund_count"
            label="基金数量"
            width="100"
            sortable="custom"
          >
            <template #default="{ row }">
              {{ formatInteger(row.fund_count) }}
            </template>
          </el-table-column>
          <el-table-column
            prop="manager_count"
            label="经理人数"
            width="100"
            sortable="custom"
          >
            <template #default="{ row }">
              {{ formatInteger(row.manager_count) }}
            </template>
          </el-table-column>
          <el-table-column
            prop="establish_date"
            label="成立日期"
            width="120"
          >
            <template #default="{ row }">
              {{ formatDate(row.establish_date) }}
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- Right: Charts Panel -->
      <div class="charts-panel">
        <div class="chart-card">
          <div class="panel-header">
            <h3>规模分布 (TOP 10)</h3>
          </div>
          <EChartsWrapper
            :option="pieChartOption"
            :loading="loading"
            height="280px"
          />
        </div>

        <div class="chart-card">
          <div class="panel-header">
            <h3>管理规模 TOP 10</h3>
          </div>
          <EChartsWrapper
            :option="barChartOption"
            :loading="loading"
            height="280px"
          />
        </div>
      </div>
    </div>

    <!-- Company Detail Dialog -->
    <el-dialog
      v-model="showDetailDialog"
      :title="selectedCompany?.company_name || '公司详情'"
      width="600px"
      destroy-on-close
    >
      <div v-if="selectedCompany" class="company-detail">
        <div class="detail-row">
          <span class="detail-label">公司名称:</span>
          <span class="detail-value">{{ selectedCompany.company_name }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">成立日期:</span>
          <span class="detail-value">{{ formatDate(selectedCompany.establish_date) }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">总管理规模:</span>
          <span class="detail-value highlight">{{ formatNumber(selectedCompany.total_scale, '亿') }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">非货规模:</span>
          <span class="detail-value">{{ formatNumber(selectedCompany.non_money_scale, '亿') }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">基金数量:</span>
          <span class="detail-value">{{ formatInteger(selectedCompany.fund_count) }} 只</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">基金经理:</span>
          <span class="detail-value">{{ formatInteger(selectedCompany.manager_count) }} 人</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">平均单只规模:</span>
          <span class="detail-value">
            {{ selectedCompany.fund_count && selectedCompany.fund_count > 0
              ? formatNumber((selectedCompany.total_scale || 0) / selectedCompany.fund_count, '亿')
              : '-' }}
          </span>
        </div>
        <div class="detail-row">
          <span class="detail-label">人均管理规模:</span>
          <span class="detail-value">
            {{ selectedCompany.manager_count && selectedCompany.manager_count > 0
              ? formatNumber((selectedCompany.total_scale || 0) / selectedCompany.manager_count, '亿')
              : '-' }}
          </span>
        </div>
      </div>
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.fund-company {
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--brand-navy-dark);
  margin-bottom: 4px;
}

.stat-label {
  font-size: 13px;
  color: var(--text-muted);
}

.main-content {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.filter-panel {
  width: 260px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  overflow-y: auto;
}

.table-panel {
  flex: 1;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.charts-panel {
  width: 380px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chart-card {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-line);
}

.panel-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.filter-section {
  margin-bottom: 16px;
}

.filter-section h4 {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.range-input {
  display: flex;
  align-items: center;
  gap: 4px;
}

.range-input .el-input-number {
  flex: 1;
}

.separator {
  color: var(--text-muted);
  font-size: 12px;
}

.sort-order {
  margin-top: 8px;
}

.filter-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.company-name {
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
}

.company-name:hover {
  color: var(--brand-navy-active);
}

.scale-value {
  font-weight: 600;
  color: var(--brand-navy-dark);
}

.company-detail {
  padding: 8px 0;
}

.detail-row {
  display: flex;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-line);
}

.detail-row:last-child {
  border-bottom: none;
}

.detail-label {
  width: 120px;
  flex-shrink: 0;
  color: var(--text-muted);
  font-size: 14px;
}

.detail-value {
  flex: 1;
  color: var(--text-primary);
  font-size: 14px;
}

.detail-value.highlight {
  font-weight: 600;
  color: var(--brand-navy-dark);
  font-size: 16px;
}

:deep(.el-table__row) {
  cursor: pointer;
}

:deep(.el-table__row:hover) {
  background-color: #f5f7fa;
}

@media (max-width: 1400px) {
  .charts-panel {
    width: 320px;
  }
}

@media (max-width: 1200px) {
  .main-content {
    flex-wrap: wrap;
  }

  .filter-panel {
    width: 100%;
    order: 1;
  }

  .table-panel {
    width: 100%;
    order: 2;
  }

  .charts-panel {
    width: 100%;
    flex-direction: row;
    order: 3;
  }

  .chart-card {
    flex: 1;
  }
}
</style>
