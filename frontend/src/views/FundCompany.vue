<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import type { EChartsOption } from 'echarts'
import { getCompanyDistribution } from '@/api/fund'
import api from '@/api/index'
import { formatNumber } from '@/utils/formatters'

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

// Asset class color palette (matches design system)
const ASSET_CLASS_COLORS: Record<string, string> = {
  '股票型': '#E63935',
  '混合型': '#FF8C00',
  '债券型': '#2E7D32',
  '货币型': '#003399',
  '指数型': '#9C27B0',
  'QDII': '#00BCD4',
  'FOF': '#795548',
  '其他': '#607D8B',
}

// State
const companies = ref<CompanyItem[]>([])
const filteredCompanies = ref<CompanyItem[]>([])
const loading = ref(false)
const chartLoading = ref(false)
const hasError = ref(false)
const treemapEmpty = ref(false)
const selectedCompany = ref<CompanyItem | null>(null)
const selectedNavCompany = ref<string | null>(null)
const showDetailDialog = ref(false)

// Search filter for navigation tree
const navSearchText = ref('')

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
} as EChartsOption)

const barChartOption = ref<EChartsOption>({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'value' },
  yAxis: { type: 'category', data: [] },
  series: [{ type: 'bar', data: [] }],
} as EChartsOption)

// Treemap chart option for asset distribution
const treemapChartOption = ref<EChartsOption>({
  tooltip: {
    formatter: (params: any) => {
      if (params.data?.name) {
        const value = params.data.value || 0
        const percentage = params.treePathInfo?.[1]?.value
          ? ((value / params.treePathInfo[1].value) * 100).toFixed(2)
          : '0'
        return `${params.data.name}<br/>规模: ${value.toFixed(2)}亿<br/>占比: ${percentage}%`
      }
      return ''
    },
  },
  series: [{
    type: 'treemap',
    data: [],
    roam: false,
    nodeClick: 'link',
    breadcrumb: { show: true },
    label: {
      show: true,
      formatter: (params: any) => {
        const value = params.value || 0
        return `${params.name}\n${value.toFixed(0)}亿`
      },
      fontSize: 11,
      overflow: 'truncate',
    },
    upperLabel: { show: true, height: 28 },
    itemStyle: {
      borderWidth: 2,
      borderColor: '#fff',
      gapWidth: 2,
    },
    levels: [
      {
        itemStyle: { borderWidth: 0, borderColor: '#E5E8ED', gapWidth: 2 },
        label: { fontSize: 13, fontWeight: 'bold' },
      },
      {
        itemStyle: { borderWidth: 2, borderColor: '#fff', gapWidth: 2 },
        label: { fontSize: 11 },
      },
    ],
  }],
} as EChartsOption)

// Sort options
const sortOptions = [
  { label: '按总规模', value: 'total_scale' },
  { label: '按基金数量', value: 'fund_count' },
  { label: '按经理人数', value: 'manager_count' },
]

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

// Navigation tree - filtered by search
const navTreeData = computed(() => {
  let result = [...companies.value]
  
  // Filter by search text
  if (navSearchText.value) {
    const searchLower = navSearchText.value.toLowerCase()
    result = result.filter(c => c.company_name.toLowerCase().includes(searchLower))
  }
  
  // Sort by scale
  result.sort((a, b) => (b.total_scale || 0) - (a.total_scale || 0))
  
  return result
})

// Fetch data
const fetchData = async () => {
  loading.value = true
  hasError.value = false
  try {
    // 直接调用 API 以读取 _error，用于区分「请求失败」与「无数据」
    const response = await api.get<CompanyItem[]>('/fund/company')
    if (response._error || response.data === null) {
      hasError.value = true
      companies.value = []
      filteredCompanies.value = []
      return
    }
    companies.value = Array.isArray(response.data) ? response.data : []
    applyFilters()
  } catch {
    // 兜底：理论上 axios 层不会 reject，此处仅防止意外
    hasError.value = true
  } finally {
    loading.value = false
  }
}

// Apply filters and sorting
const applyFilters = async () => {
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
  await updateCharts()
}

// Update charts
const updateCharts = async () => {
  const data = filteredCompanies.value

  // Pie chart - top 10 by scale
  const top10ForPie = data.slice(0, 10)
  const pieData = top10ForPie.map(c => ({
    name: c.company_name,
    value: c.total_scale || 0,
  }))
  
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
  } as EChartsOption

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
  } as EChartsOption

  // Treemap - fetch real per-company asset distribution from API and aggregate
  chartLoading.value = true
  try {
    const treemapData = await generateTreemapData(data)
    if (treemapData && treemapData.length > 0) {
      treemapEmpty.value = false
      treemapChartOption.value = {
        ...treemapChartOption.value,
        series: [{
          type: 'treemap',
          data: treemapData,
        }],
      } as EChartsOption
    } else {
      // 无可用的真实资产配置数据，展示空状态而非伪造数据
      treemapEmpty.value = true
      treemapChartOption.value = {
        ...treemapChartOption.value,
        series: [{
          type: 'treemap',
          data: [],
        }],
      } as EChartsOption
    }
  } catch {
    // 异常时同样展示空状态，避免误渲染
    treemapEmpty.value = true
  } finally {
    chartLoading.value = false
  }
}

// Generate treemap data by aggregating real per-company asset distributions
const generateTreemapData = async (companies: CompanyItem[]) => {
  // 仅使用有规模数据的公司，按规模降序取前 30 家以控制请求量
  const candidates = companies
    .filter(c => c.total_scale && c.total_scale > 0)
    .sort((a, b) => (b.total_scale || 0) - (a.total_scale || 0))
    .slice(0, 30)

  const results: Array<{ company: CompanyItem; items: Array<{ item_name: string; weight: number }> }> = []

  // 分块并发（每批 8 个）拉取各公司真实资产配置
  const CHUNK_SIZE = 8
  for (let i = 0; i < candidates.length; i += CHUNK_SIZE) {
    const chunk = candidates.slice(i, i + CHUNK_SIZE)
    const settled = await Promise.all(chunk.map(async (company) => {
      const response = await getCompanyDistribution(company.company_id, 'asset_class')
      if (response && !response.is_simulated && Array.isArray(response.items) && response.items.length > 0) {
        return { company, items: response.items }
      }
      return null
    }))
    settled.forEach(r => { if (r) results.push(r) })
  }

  // 全部公司均无真实数据时返回 null，由调用方展示空状态
  if (results.length === 0) {
    return null
  }

  // 按资产类别聚合（以公司规模加权）
  const classMap = new Map<string, { value: number; children: Map<string, number> }>()
  for (const { company, items } of results) {
    for (const item of items) {
      const contribution = (company.total_scale || 0) * (item.weight / 100)
      if (contribution <= 0) continue
      let entry = classMap.get(item.item_name)
      if (!entry) {
        entry = { value: 0, children: new Map() }
        classMap.set(item.item_name, entry)
      }
      entry.value += contribution
      entry.children.set(company.company_name, (entry.children.get(company.company_name) || 0) + contribution)
    }
  }

  return Array.from(classMap.entries()).map(([name, entry]) => ({
    name,
    value: entry.value,
    itemStyle: { color: ASSET_CLASS_COLORS[name] || '#607D8B' },
    children: Array.from(entry.children.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([childName, childValue]) => ({
        name: childName,
        value: childValue,
        itemStyle: { color: ASSET_CLASS_COLORS[name] || '#607D8B' },
      })),
  }))
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

// Handle sort change (表格排序)
const handleSortChange = ({ prop, order }: { prop: string; order: string | null }) => {
  if (prop && ['total_scale', 'fund_count', 'manager_count'].includes(prop)) {
    filterParams.value.sort_by = prop as FilterParams['sort_by']
    filterParams.value.sort_order = order === 'ascending' ? 'asc' : 'desc'
    // 仅在此处调用一次 applyFilters，避免与 watch 重复请求
    applyFilters()
  }
}

// Handle navigation tree click
const handleNavClick = (company: CompanyItem) => {
  selectedNavCompany.value = company.company_id
  
  // Filter to show only this company
  filteredCompanies.value = [company]
  updateCharts()
}

// Reset navigation filter
const handleNavReset = () => {
  selectedNavCompany.value = null
  applyFilters()
}

// Handle treemap drill-down
const handleTreemapClick = (params: any) => {
  if (params.data?.name) {
    const companyName = params.data.name
    const company = companies.value.find(c => c.company_name === companyName)
    if (company) {
      selectedCompany.value = company
      showDetailDialog.value = true
    }
  }
}

// 排序变更统一由 handleSortChange 处理；筛选面板的排序通过「筛选」按钮触发，
// 不再使用 watch 监听，避免与 handleSortChange 重复请求。

onMounted(() => {
  fetchData()
})
</script>

<template>
  <div class="fund-company">
    <!-- Header Stats -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-value">{{ hasError ? '—' : formatNumber(totalStats.totalScale, 2, '亿') }}</div>
        <div class="stat-label">总管理规模</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ hasError ? '—' : formatInteger(totalStats.totalFunds) }}</div>
        <div class="stat-label">基金总数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ hasError ? '—' : formatInteger(totalStats.totalManagers) }}</div>
        <div class="stat-label">基金经理</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ hasError ? '—' : formatNumber(totalStats.avgScale, 2, '亿') }}</div>
        <div class="stat-label">平均规模</div>
      </div>
    </div>

    <div class="main-content">
      <!-- Left: Company Navigation Tree -->
      <div class="nav-tree-panel">
        <div class="panel-header">
          <h3>公司导航</h3>
          <el-button
            v-if="selectedNavCompany"
            size="small"
            text
            type="primary"
            @click="handleNavReset"
          >
            重置
          </el-button>
        </div>

        <!-- Search input -->
        <div class="nav-search">
          <el-input
            v-model="navSearchText"
            placeholder="搜索公司..."
            size="small"
            clearable
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>

        <!-- Company list -->
        <div class="nav-tree-list" v-loading="loading">
          <div
            v-for="company in navTreeData"
            :key="company.company_id"
            class="nav-tree-item"
            :class="{ 'is-selected': selectedNavCompany === company.company_id }"
            @click="handleNavClick(company)"
          >
            <div class="nav-item-name">{{ company.company_name }}</div>
            <div class="nav-item-scale">{{ formatNumber(company.total_scale) }}亿</div>
          </div>
          <div v-if="navTreeData.length === 0" class="nav-empty">
            暂无匹配公司
          </div>
        </div>
      </div>

      <!-- Center: Charts Panel -->
      <div class="center-panel">
        <!-- Treemap Chart -->
        <div class="chart-card chart-large">
          <div class="panel-header">
            <h3>资产配置分布 (Treemap)</h3>
            <span class="chart-hint">点击矩形查看公司详情</span>
          </div>
          <EChartsWrapper
            v-if="!treemapEmpty"
            :option="treemapChartOption"
            :loading="chartLoading"
            height="320px"
            @click="handleTreemapClick"
          />
          <div v-else class="chart-empty">该分析所需数据源暂未提供</div>
          <div v-if="chartLoading" class="chart-skeleton">
            <div class="skeleton-block"></div>
          </div>
          <div class="chart-legend">
            <div class="legend-item">
              <span class="legend-dot" style="background: #E63935"></span>
              <span>股票型</span>
            </div>
            <div class="legend-item">
              <span class="legend-dot" style="background: #FF8C00"></span>
              <span>混合型</span>
            </div>
            <div class="legend-item">
              <span class="legend-dot" style="background: #2E7D32"></span>
              <span>债券型</span>
            </div>
            <div class="legend-item">
              <span class="legend-dot" style="background: #003399"></span>
              <span>货币型</span>
            </div>
            <div class="legend-item">
              <span class="legend-dot" style="background: #9C27B0"></span>
              <span>指数型</span>
            </div>
          </div>
        </div>

        <!-- Manager Quadrant Analysis - 数据源暂未提供 -->
        <div class="chart-card chart-large">
          <div class="panel-header">
            <h3>基金经理四象限分析</h3>
          </div>
          <div class="chart-empty">该分析所需数据源暂未提供</div>
        </div>
      </div>

      <!-- Right: Existing Charts & Table -->
      <div class="right-panel">
        <!-- Filter Panel -->
        <div class="filter-panel-compact">
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

        <!-- Pie Chart -->
        <div class="chart-card">
          <div class="panel-header">
            <h3>规模分布 (TOP 10)</h3>
          </div>
          <EChartsWrapper
            :option="pieChartOption"
            :loading="loading"
            height="240px"
          />
        </div>

        <!-- Bar Chart -->
        <div class="chart-card">
          <div class="panel-header">
            <h3>管理规模 TOP 10</h3>
          </div>
          <EChartsWrapper
            :option="barChartOption"
            :loading="loading"
            height="240px"
          />
        </div>
      </div>
    </div>

    <!-- Company Table (Full Width) -->
    <div class="table-panel">
      <div class="panel-header">
        <h3>基金公司列表 ({{ filteredCompanies.length }} 家)</h3>
      </div>

      <el-table
        :data="filteredCompanies"
        :loading="loading"
        stripe
        height="calc(100dvh - 680px)"
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
          <span class="detail-value highlight">{{ formatNumber(selectedCompany.total_scale, 2, '亿') }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">非货规模:</span>
          <span class="detail-value">{{ formatNumber(selectedCompany.non_money_scale, 2, '亿') }}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">基金数量:</span>
          <span class="detail-value">{{ formatInteger(selectedCompany.fund_count as number | null) }} 只</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">基金经理:</span>
          <span class="detail-value">{{ formatInteger(selectedCompany.manager_count as number | null) }} 人</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">平均单只规模:</span>
          <span class="detail-value">
            {{ selectedCompany.fund_count && selectedCompany.fund_count > 0
              ? formatNumber((selectedCompany.total_scale || 0) / (selectedCompany.fund_count as number), 2, '亿')
              : '-' }}
          </span>
        </div>
        <div class="detail-row">
          <span class="detail-label">人均管理规模:</span>
          <span class="detail-value">
            {{ selectedCompany.manager_count && selectedCompany.manager_count > 0
              ? formatNumber((selectedCompany.total_scale || 0) / (selectedCompany.manager_count as number), 2, '亿')
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
  height: calc(100vh - 100px); /* Fallback for older browsers */
  height: calc(100dvh - 100px);
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
  margin-bottom: 16px;
}

/* Navigation Tree Panel */
.nav-tree-panel {
  width: 220px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.nav-search {
  margin-bottom: 12px;
}

.nav-tree-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.nav-tree-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  margin-bottom: 4px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.nav-tree-item:hover {
  background: var(--bg-system);
}

.nav-tree-item.is-selected {
  background: rgba(0, 51, 153, 0.1);
  border-left: 3px solid var(--brand-navy-dark);
}

.nav-item-name {
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.nav-item-scale {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: 8px;
  flex-shrink: 0;
}

.nav-empty {
  text-align: center;
  padding: 20px;
  color: var(--text-muted);
  font-size: 13px;
}

/* Center Panel */
.center-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.chart-large {
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* Right Panel */
.right-panel {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.filter-panel-compact {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.table-panel {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.chart-card {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  position: relative;
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

.chart-hint {
  font-size: 11px;
  color: var(--text-muted);
}

.chart-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  color: var(--text-muted);
  font-size: 13px;
}

.chart-skeleton {
  position: absolute;
  top: 50px;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
}

.skeleton-block {
  width: 80%;
  height: 200px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 4px;
}

@keyframes skeleton-loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.filter-section {
  margin-bottom: 12px;
}

.filter-section h4 {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
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
  margin-top: 12px;
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

/* Chart Legends */
.chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px solid var(--border-line);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 2px;
}

/* Quadrant Legend removed - manager quadrant analysis data source unavailable */

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

@media (max-width: 1600px) {
  .nav-tree-panel {
    width: 180px;
  }
  
  .right-panel {
    width: 280px;
  }
}

@media (max-width: 1400px) {
  .main-content {
    flex-wrap: wrap;
  }
  
  .nav-tree-panel {
    width: 100%;
    order: 1;
    max-height: 200px;
  }
  
  .center-panel {
    width: 100%;
    order: 2;
    flex-direction: row;
  }
  
  .right-panel {
    width: 100%;
    order: 3;
    flex-direction: row;
  }
  
  .filter-panel-compact {
    flex: 1;
  }
  
  .right-panel .chart-card {
    flex: 1;
  }
}

@media (max-width: 768px) {
  .center-panel {
    flex-direction: column;
  }
  
  .right-panel {
    flex-direction: column;
  }
  
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
