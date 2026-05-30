<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { filterFunds, getFundNavTrend, type FundFilterParams, type FundItem } from '@/api/fund'
import { useFilterTemplates } from '@/composables/useFilterTemplates'
import SplitPanel from '@/components/SplitPanel.vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import EmptyState from '@/components/EmptyState.vue'
import JargonTooltip from '@/components/JargonTooltip.vue'
import type { EChartsOption } from 'echarts'
import jargonData from '@/data/jargon.json'

const {
  templates,
  defaultTemplateKey,
  loading: templatesLoading,
  offlineMode,
  loadTemplates,
  saveTemplate,
  deleteTemplate,
  setDefault,
  loadTemplateParams,
} = useFilterTemplates()

const selectedTemplateKey = ref<string>('')

const templateOptions = computed(() => {
  return templates.value.map(t => ({
    label: t.is_default ? `${t.name} (默认)` : t.name,
    value: t.key,
  }))
})

// 筛选条件
const filterParams = ref<FundFilterParams>({
  fund_types: [],
  setup_year_min: undefined,
  setup_year_max: undefined,
  scale_min: undefined,
  scale_max: undefined,
  return_1y_min: undefined,
  return_1y_max: undefined,
  max_drawdown_1y_max: undefined,
  sharpe_1y_min: undefined,
  new_high_ratio_min: undefined,
  page: 1,
  page_size: 50,
  sort_by: 'return_1y',
  sort_order: 'desc',
})

// 基金类型选项
const fundTypes = [
  '股票型', '混合型', '债券型', '指数型', 'ETF', 'LOF',
  'QDII', 'FOF', '货币型', '理财型',
]

// 结果数据
const tableData = ref<FundItem[]>([])
const total = ref(0)
const loading = ref(false)
const filterTimeMs = ref<number | null>(null)
const splitPanelRef = ref<InstanceType<typeof SplitPanel> | null>(null)

// Sparkline cache and loading states
const sparklineCache = ref<Map<string, { option: EChartsOption; isSimulated: boolean }>>(new Map())
const sparklineLoading = ref<Set<string>>(new Set())

// Debounce timer for filter
let filterDebounceTimer: ReturnType<typeof setTimeout> | null = null

// Debounced filter execution
const debouncedFilter = (delay = 300) => {
  if (filterDebounceTimer) {
    clearTimeout(filterDebounceTimer)
  }
  filterDebounceTimer = setTimeout(() => {
    handleFilter()
  }, delay)
}

// 执行筛选
const handleFilter = async () => {
  loading.value = true
  const startTime = performance.now()
  try {
    const response = await filterFunds(filterParams.value)
    if (response && response.funds) {
      tableData.value = response.funds
      total.value = response.total
    }
  } catch {
    // API interceptor already handled notification
  } finally {
    loading.value = false
    filterTimeMs.value = Math.round(performance.now() - startTime)
  }
}

// 重置筛选
const handleReset = () => {
  filterParams.value = {
    fund_types: [],
    page: 1,
    page_size: 50,
    sort_by: 'return_1y',
    sort_order: 'desc',
  }
  handleFilter()
}

// 分页切换
const handlePageChange = (page: number) => {
  filterParams.value.page = page
  handleFilter()
}

const handleSaveTemplate = async () => {
  try {
    const { value: name } = await ElMessageBox.prompt('请输入模板名称', '保存筛选模板', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputPattern: /^.{1,30}$/,
      inputErrorMessage: '模板名称长度为 1-30 个字符',
    })
    
    if (name) {
      const key = await saveTemplate(name, filterParams.value)
      selectedTemplateKey.value = key
    }
  } catch {
  }
}

const handleLoadTemplate = (key: string) => {
  if (!key) return
  
  const params = loadTemplateParams(key)
  if (params) {
    filterParams.value = { ...params, page: 1 }
    handleFilter()
    
    const template = templates.value.find(t => t.key === key)
    ElMessage.success(`已加载模板 "${template?.name || '未知'}"`)
  }
}

const handleDeleteTemplate = async (key: string) => {
  if (!key) return
  
  const template = templates.value.find(t => t.key === key)
  const name = template?.name || '此模板'
  
  try {
    await ElMessageBox.confirm(
      `确定要删除模板 "${name}" 吗？`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    await deleteTemplate(key)
    
    if (selectedTemplateKey.value === key) {
      selectedTemplateKey.value = ''
    }
  } catch {
  }
}

const handleSetDefault = async (key: string) => {
  if (!key) return
  await setDefault(key)
}

// 格式化数字
const formatNumber = (val: number | null, suffix = ''): string => {
  if (val === null || val === undefined) return '-'
  return `${val.toFixed(2)}${suffix}`
}

// 获取涨跌样式
const getValueClass = (val: number | null): string => {
  if (val === null) return ''
  return val >= 0 ? 'text-up' : 'text-down'
}

// 导出CSV - 零后端债务实现
// 纯前端Blob API，带BOM头防止Excel中文乱码
const handleExportCSV = () => {
  if (!tableData.value || tableData.value.length === 0) {
    ElMessage.warning('暂无数据可导出')
    return
  }

  // CSV列定义
  const headers = [
    '基金代码',
    '基金名称',
    '基金类型',
    '基金经理',
    '成立日期',
    '基金规模(亿)',
    '近1年收益(%)',
    '最大回撤(%)',
    '夏普比率',
    '内含新高率(%)',
    '重仓行业',
    '基金公司',
  ]

  const keys: (keyof FundItem)[] = [
    'fund_code',
    'fund_name',
    'fund_type',
    'manager',
    'setup_date',
    'scale',
    'return_1y',
    'max_drawdown_1y',
    'sharpe_1y',
    'new_high_ratio_1y',
    'heavy_sector',
    'company_name',
  ]

  // 构建CSV行
  const csvRows: string[] = []

  // 添加表头
  csvRows.push(headers.join(','))

  // 添加数据行
  for (const fund of tableData.value) {
    const row = keys.map((key) => {
      const value = fund[key]

      // 处理null/undefined
      if (value === null || value === undefined) {
        return ''
      }

      // 数字格式化
      if (typeof value === 'number') {
        return value.toFixed(2)
      }

      // 字符串转义（处理逗号、引号、换行）
      const str = String(value)
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`
      }

      return str
    })

    csvRows.push(row.join(','))
  }

  // 添加BOM头（UTF-8 with BOM）防止Excel中文乱码
  const BOM = '\uFEFF'
  const csvContent = BOM + csvRows.join('\n')

  // 创建Blob并下载
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)

  // 生成文件名（带时间戳）
  const now = new Date()
  const timestamp = now.toISOString().slice(0, 19).replace(/[T:]/g, '-')
  const filename = `fund-filter-${timestamp}.csv`

  // 创建下载链接
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()

  // 清理
  document.body.removeChild(link)
  URL.revokeObjectURL(url)

  ElMessage.success(`已导出 ${tableData.value.length} 条记录`)
}

// Generate sparkline option for fund return trend
const getSparklineOption = (fund: FundItem): EChartsOption | null => {
  // Check cache first
  const cached = sparklineCache.value.get(fund.fund_code)
  if (cached) {
    return cached.option
  }
  
  // If loading, return null (will show skeleton)
  if (sparklineLoading.value.has(fund.fund_code)) {
    return null
  }
  
  // Fetch data in background
  fetchSparklineData(fund.fund_code)
  
  // Return null to show loading state
  return null
}

// Fetch sparkline data from API
const fetchSparklineData = async (fundCode: string) => {
  if (sparklineLoading.value.has(fundCode) || sparklineCache.value.has(fundCode)) {
    return
  }
  
  sparklineLoading.value.add(fundCode)
  
  try {
    const response = await getFundNavTrend(fundCode, 30)
    
    if (response.nav_values?.length > 0) {
      const firstValue = response.nav_values[0]
      const lastValue = response.nav_values[response.nav_values.length - 1]
      const isUp = lastValue >= firstValue
      const lineColor = isUp ? '#2E7D32' : '#E63935'
      
      const option: EChartsOption = {
        xAxis: { type: 'category' as const, show: false },
        yAxis: { type: 'value' as const, show: false },
        grid: { left: 0, right: 0, top: 0, bottom: 0 },
        series: [{
          type: 'line' as const,
          data: response.nav_values,
          lineStyle: { color: lineColor, width: 1.5 },
          areaStyle: {
            color: {
              type: 'linear' as const,
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: isUp ? 'rgba(46, 125, 50, 0.3)' : 'rgba(230, 57, 53, 0.3)' },
                { offset: 1, color: 'rgba(255, 255, 255, 0)' }
              ]
            }
          },
          symbol: 'none',
        }]
      }
      
      sparklineCache.value.set(fundCode, { option, isSimulated: response.is_simulated })
    } else {
      // Fallback to simulated data
      const fallbackOption = createFallbackSparkline(fundCode)
      sparklineCache.value.set(fundCode, { option: fallbackOption, isSimulated: true })
    }
  } catch {
    // Graceful degradation - use fallback sparkline
    const fallbackOption = createFallbackSparkline(fundCode)
    sparklineCache.value.set(fundCode, { option: fallbackOption, isSimulated: true })
  } finally {
    sparklineLoading.value.delete(fundCode)
  }
}

// Create fallback sparkline when API fails
const createFallbackSparkline = (fundCode: string): EChartsOption => {
  const data: number[] = []
  for (let i = 0; i < 30; i++) {
    data.push(1 + (Math.random() - 0.5) * 0.1)
  }
  
  return {
    xAxis: { type: 'category' as const, show: false },
    yAxis: { type: 'value' as const, show: false },
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    series: [{
      type: 'line' as const,
      data,
      lineStyle: { color: '#999', width: 1 },
      areaStyle: {
        color: {
          type: 'linear' as const,
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(150, 150, 150, 0.2)' },
            { offset: 1, color: 'rgba(255, 255, 255, 0)' }
          ]
        }
      },
      symbol: 'none',
    }]
  }
}

// Check if sparkline is simulated
const isSparklineSimulated = (fundCode: string): boolean => {
  const cached = sparklineCache.value.get(fundCode)
  return cached?.isSimulated ?? false
}

// Handle input focus with scroll for keyboard occlusion
const handleInputFocus = (e: FocusEvent) => {
  const target = e.target as HTMLElement
  if (target) {
    setTimeout(() => {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 100)
  }
}

// Watch filter params for auto-filter with debounce
watch(
  () => [
    filterParams.value.fund_types,
    filterParams.value.setup_year_min,
    filterParams.value.setup_year_max,
    filterParams.value.scale_min,
    filterParams.value.scale_max,
    filterParams.value.return_1y_min,
    filterParams.value.return_1y_max,
    filterParams.value.max_drawdown_1y_max,
    filterParams.value.sharpe_1y_min,
    filterParams.value.new_high_ratio_min,
  ],
  () => {
    debouncedFilter()
  },
  { deep: true }
)

onMounted(async () => {
  await loadTemplates()
  
  if (defaultTemplateKey.value) {
    const params = loadTemplateParams(defaultTemplateKey.value)
    if (params) {
      filterParams.value = { ...params }
      selectedTemplateKey.value = defaultTemplateKey.value
    }
  }
  
  handleFilter()
})
</script>

<template>
  <div class="fund-filter">
    <SplitPanel
      ref="splitPanelRef"
      :initial-left-size="320"
      :min-left-size="260"
      :max-left-size="480"
      storage-key="fundfilter-panel-size"
    >
      <!-- Left Panel: Filter Conditions -->
      <template #left="{ collapsed }">
        <div class="filter-panel" :class="{ 'filter-panel--collapsed': collapsed }">
          <div class="panel-header">
            <h3 v-if="!collapsed">筛选条件</h3>
            <h3 v-else class="collapsed-title">筛选</h3>
          </div>
          
          <div v-if="!collapsed" class="filter-form">
            <!-- 基础信息 -->
            <div class="filter-section">
              <h4>基础信息</h4>
              <div class="form-item">
                <label>基金类型</label>
                <el-checkbox-group v-model="filterParams.fund_types">
                  <el-checkbox
                    v-for="type in fundTypes"
                    :key="type"
                    :label="type"
                  />
                </el-checkbox-group>
              </div>
              
              <div class="form-item">
                <label>成立年限</label>
                <div class="range-input">
                  <el-input-number
                    v-model="filterParams.setup_year_min"
                    :min="0"
                    :max="20"
                    placeholder="最小"
                    @focus="handleInputFocus"
                  />
                  <span>-</span>
                  <el-input-number
                    v-model="filterParams.setup_year_max"
                    :min="0"
                    :max="20"
                    placeholder="最大"
                    @focus="handleInputFocus"
                  />
                </div>
              </div>
              
              <div class="form-item">
                <label>基金规模 (亿)</label>
                <div class="range-input">
                  <el-input-number
                    v-model="filterParams.scale_min"
                    :min="0"
                    placeholder="最小"
                    @focus="handleInputFocus"
                  />
                  <span>-</span>
                  <el-input-number
                    v-model="filterParams.scale_max"
                    :min="0"
                    placeholder="最大"
                    @focus="handleInputFocus"
                  />
                </div>
              </div>
            </div>
            
            <!-- 收益风险 -->
            <div class="filter-section">
              <h4>收益风险</h4>
              <div class="form-item">
                <label>近1年收益 (%)</label>
                <div class="range-input">
                  <el-input-number
                    v-model="filterParams.return_1y_min"
                    placeholder="最小"
                    @focus="handleInputFocus"
                  />
                  <span>-</span>
                  <el-input-number
                    v-model="filterParams.return_1y_max"
                    placeholder="最大"
                    @focus="handleInputFocus"
                  />
                </div>
              </div>
              
              <div class="form-item">
                <label>最大回撤 ≤ (%)</label>
                <el-input-number
                  v-model="filterParams.max_drawdown_1y_max"
                  :min="0"
                  :max="100"
                  @focus="handleInputFocus"
                />
              </div>
              
              <div class="form-item">
                <label>夏普比率 ≥</label>
                <el-input-number
                  v-model="filterParams.sharpe_1y_min"
                  :step="0.1"
                  @focus="handleInputFocus"
                />
              </div>
              
              <div class="form-item">
                <label>内含新高率 (近1年) ≥</label>
                <el-slider
                  v-model="filterParams.new_high_ratio_min"
                  :min="0"
                  :max="100"
                  :step="5"
                  :marks="{ 0: '0%', 50: '50%', 80: '80%', 100: '100%' }"
                  show-input
                />
              </div>
            </div>
            
            <!-- 操作按钮 -->
            <div class="filter-actions">
              <el-button type="primary" @click="handleFilter" :loading="loading">
                筛选
              </el-button>
              <el-button @click="handleReset">
                重置
              </el-button>
              <el-button @click="handleSaveTemplate">
                保存模板
              </el-button>
            </div>
            
            <!-- 模板选择 -->
            <div v-if="templates.length > 0" class="template-section">
              <div class="template-header">
                <label>筛选模板</label>
                <span v-if="offlineMode" class="offline-badge">离线</span>
              </div>
              <div class="template-controls">
                <el-select
                  v-model="selectedTemplateKey"
                  placeholder="选择模板"
                  size="small"
                  @change="handleLoadTemplate"
                >
                  <el-option
                    v-for="opt in templateOptions"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
                <div class="template-actions">
                  <el-button
                    size="small"
                    :disabled="!selectedTemplateKey"
                    @click="handleSetDefault(selectedTemplateKey)"
                  >
                    设为默认
                  </el-button>
                  <el-button
                    size="small"
                    type="danger"
                    :disabled="!selectedTemplateKey"
                    @click="handleDeleteTemplate(selectedTemplateKey)"
                  >
                    删除
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
      
      <!-- Right Panel: Results Table -->
      <template #right>
        <div class="result-panel">
          <div class="panel-header">
            <div class="header-left">
              <h3>筛选结果 <span class="result-count">({{ total }} 只)</span></h3>
              <span v-if="filterTimeMs !== null" class="filter-time">
                {{ filterTimeMs }}ms
              </span>
            </div>
            <div class="header-actions">
              <el-button 
                size="small" 
                :disabled="!tableData || tableData.length === 0"
                @click="handleExportCSV"
              >
                导出CSV
              </el-button>
            </div>
          </div>
          
          <!-- Skeleton table when loading -->
          <div v-if="loading" class="skeleton-table-wrapper">
            <SkeletonLoader variant="table" :rows="10" :columns="10" />
          </div>
          
          <!-- Empty state when no results -->
          <EmptyState
            v-else-if="!loading && tableData?.length === 0"
            icon="search"
            title="未找到符合条件的基金"
            description="请尝试调整筛选条件或重置筛选器"
            action-text="重置筛选"
            :action-handler="handleReset"
          />
          
          <!-- Actual table when data loaded -->
          <el-table
            v-else
            :data="tableData"
            stripe
            height="calc(100dvh - 220px)"
          >
            <el-table-column
              prop="fund_code"
              label="代码"
              width="100"
              fixed
            />
            <el-table-column
              prop="fund_name"
              label="名称"
              min-width="160"
              fixed
            />
            <el-table-column
              prop="fund_type"
              label="类型"
              width="90"
            />
            <el-table-column
              prop="manager"
              label="经理"
              width="80"
            />
            <el-table-column
              prop="scale"
              label="规模(亿)"
              width="90"
            >
              <template #default="{ row }">
                {{ formatNumber(row.scale) }}
              </template>
            </el-table-column>
            <el-table-column
              label="收益趋势"
              width="120"
            >
              <template #default="{ row }">
                <div class="sparkline-cell">
                  <EChartsWrapper
                    v-if="getSparklineOption(row)"
                    :option="getSparklineOption(row)!"
                    :is-sparkline="true"
                    height="40px"
                  />
                  <div v-else class="sparkline-skeleton"></div>
                  <span v-if="isSparklineSimulated(row.fund_code)" class="simulated-badge-mini">模拟</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column
              prop="return_1y"
              label="近1年%"
              width="100"
              sortable
            >
              <template #default="{ row }">
                <span :class="getValueClass(row.return_1y)">
                  {{ formatNumber(row.return_1y) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column
              prop="max_drawdown_1y"
              width="105"
              sortable
            >
              <template #header>
                <JargonTooltip
                  term="最大回撤%"
                  :definition="jargonData.max_drawdown"
                  position="top"
                />
              </template>
              <template #default="{ row }">
                <span :class="getValueClass(-row.max_drawdown_1y)">
                  {{ formatNumber(row.max_drawdown_1y) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column
              prop="sharpe_1y"
              width="75"
              sortable
            >
              <template #header>
                <JargonTooltip
                  term="夏普"
                  :definition="jargonData.sharpe_ratio"
                  position="top"
                />
              </template>
              <template #default="{ row }">
                {{ formatNumber(row.sharpe_1y) }}
              </template>
            </el-table-column>
            <el-table-column
              prop="new_high_ratio_1y"
              width="100"
              sortable
            >
              <template #header>
                <JargonTooltip
                  term="内含新高率"
                  :definition="jargonData.new_high_ratio"
                  position="top"
                />
              </template>
              <template #default="{ row }">
                <span
                  :class="{
                    'text-green-600': row.new_high_ratio_1y >= 80,
                    'text-gray-500': row.new_high_ratio_1y < 80 || !row.new_high_ratio_1y
                  }"
                >
                  {{ row.new_high_ratio_1y ? `${row.new_high_ratio_1y.toFixed(1)}%` : '-' }}
                </span>
              </template>
            </el-table-column>
          </el-table>
          
          <!-- 分页 -->
          <div class="pagination">
            <el-pagination
              :current-page="filterParams.page"
              :page-size="filterParams.page_size"
              :total="total"
              layout="total, prev, pager, next, jumper"
              @current-change="handlePageChange"
            />
          </div>
        </div>
      </template>
    </SplitPanel>
  </div>
</template>

<style scoped>
.fund-filter {
  height: calc(100vh - 100px); /* Fallback for older browsers */
  height: calc(100dvh - 100px);
  padding: 0;
}

.filter-panel {
  height: 100%;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.filter-panel--collapsed {
  padding: 12px 8px;
  align-items: center;
}

.collapsed-title {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  font-size: 14px;
  letter-spacing: 2px;
}

.result-panel {
  height: 100%;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-line);
  flex-shrink: 0;
}

.panel-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-count {
  font-weight: 400;
  color: var(--text-regular);
}

.filter-time {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-system);
  padding: 2px 8px;
  border-radius: 4px;
}

.filter-section {
  margin-bottom: 20px;
}

.filter-section h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.form-item {
  margin-bottom: 12px;
}

.form-item label {
  display: block;
  font-size: 13px;
  color: var(--text-regular);
  margin-bottom: 6px;
}

.range-input {
  display: flex;
  align-items: center;
  gap: 8px;
}

.range-input span {
  color: var(--text-muted);
}

.sparkline-cell {
  position: relative;
}

.skeleton-table-wrapper {
  min-height: 400px;
  background: var(--bg-card);
  border-radius: 4px;
}

.sparkline-skeleton {
  width: 80px;
  height: 40px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 2px;
}

@keyframes skeleton-loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.simulated-badge-mini {
  position: absolute;
  top: 0;
  right: 0;
  font-size: 9px;
  color: #FF8C00;
  background: rgba(255, 140, 0, 0.1);
  padding: 1px 3px;
  border-radius: 2px;
}

.filter-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
}

.template-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-line);
}

.template-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.template-header label {
  font-size: 13px;
  color: var(--text-regular);
  font-weight: 500;
}

.offline-badge {
  font-size: 11px;
  color: var(--color-warning, #E6A23C);
  background: rgba(230, 162, 60, 0.1);
  padding: 2px 6px;
  border-radius: 3px;
}

.template-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.template-actions {
  display: flex;
  gap: 8px;
}

@media (min-width: 400px) {
  .template-controls {
    flex-direction: row;
    align-items: center;
  }
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  flex-shrink: 0;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .fund-filter {
    height: auto;
    min-height: calc(100vh - 100px); /* Fallback for older browsers */
    min-height: calc(100dvh - 100px);
  }
  
  .filter-panel {
    max-height: 40vh;
    overflow-y: auto;
  }
  
  .result-panel {
    min-height: 50vh;
  }
  
  .el-table {
    font-size: 12px;
  }
}
</style>
