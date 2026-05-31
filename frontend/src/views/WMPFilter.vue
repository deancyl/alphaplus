<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  filterWMP,
  getWMPStatistics,
  formatYieldRate,
  formatDuration,
  formatMinAmount,
  getRiskLevelColor,
  type WMPFilterParams,
  type WMPItem,
  type WMPStatistics,
} from '@/api/wmp'
import SplitPanel from '@/components/SplitPanel.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyState from '@/components/EmptyState.vue'

// ==================== Reactive State ====================

const filterParams = ref<WMPFilterParams>({
  risk_levels: [],
  page: 1,
  page_size: 50,
  sort_by: 'yield_rate',
  sort_order: 'desc',
})

const tableData = ref<WMPItem[]>([])
const total = ref(0)
const loading = ref(false)
const filterTimeMs = ref<number | null>(null)
const statistics = ref<WMPStatistics | null>(null)

// Yield rate range slider
const yieldRange = ref<[number, number]>([0, 10])

// Duration range slider
const durationRange = ref<[number, number]>([7, 365])

// Risk level options
const riskLevelOptions = [
  { value: 'PR1', label: 'PR1 极低风险', description: '适合保守型投资者' },
  { value: 'PR2', label: 'PR2 较低风险', description: '适合稳健型投资者' },
  { value: 'PR3', label: 'PR3 中等风险', description: '适合平衡型投资者' },
  { value: 'PR4', label: 'PR4 较高风险', description: '适合进取型投资者' },
  { value: 'PR5', label: 'PR5 高风险', description: '适合激进型投资者' },
]

// Debounce timer
let filterDebounceTimer: ReturnType<typeof setTimeout> | null = null

// ==================== Computed Properties ====================

const averageYield = computed(() => {
  if (!statistics.value) return '-'
  return `${statistics.value.avg_yield_rate.toFixed(2)}%`
})

const averageDuration = computed(() => {
  if (!statistics.value) return '-'
  return formatDuration(statistics.value.avg_duration)
})

// ==================== Filter Functions ====================

const debouncedFilter = (delay = 300) => {
  if (filterDebounceTimer) {
    clearTimeout(filterDebounceTimer)
  }
  filterDebounceTimer = setTimeout(() => {
    handleFilter()
  }, delay)
}

const handleFilter = async () => {
  loading.value = true
  const startTime = performance.now()
  
  // Update filter params from sliders
  filterParams.value.yield_min = yieldRange.value[0]
  filterParams.value.yield_max = yieldRange.value[1]
  filterParams.value.duration_min = durationRange.value[0]
  filterParams.value.duration_max = durationRange.value[1]
  
  try {
    const response = await filterWMP(filterParams.value)
    tableData.value = response.products
    total.value = response.total
  } catch (error) {
    ElMessage.error('筛选失败，请重试')
  } finally {
    loading.value = false
    filterTimeMs.value = Math.round(performance.now() - startTime)
  }
}

const handleReset = () => {
  filterParams.value = {
    risk_levels: [],
    page: 1,
    page_size: 50,
    sort_by: 'yield_rate',
    sort_order: 'desc',
  }
  yieldRange.value = [0, 10]
  durationRange.value = [7, 365]
  handleFilter()
}

const handlePageChange = (page: number) => {
  filterParams.value.page = page
  handleFilter()
}

const handleSortChange = ({ prop, order }: { prop: string; order: string | null }) => {
  if (prop && order) {
    filterParams.value.sort_by = prop as WMPFilterParams['sort_by']
    filterParams.value.sort_order = order === 'ascending' ? 'asc' : 'desc'
    handleFilter()
  }
}

// ==================== Load Statistics ====================

const loadStatistics = async () => {
  try {
    statistics.value = await getWMPStatistics()
  } catch {
    // API interceptor already handled notification
    statistics.value = null
  }
}

// ==================== Utility Functions ====================

const handleInputFocus = (e: FocusEvent) => {
  const target = e.target as HTMLElement
  if (target) {
    setTimeout(() => {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 100)
  }
}

// ==================== Watchers ====================

watch(
  () => [
    filterParams.value.risk_levels,
    yieldRange.value,
    durationRange.value,
  ],
  () => {
    debouncedFilter()
  },
  { deep: true }
)

// ==================== Lifecycle ====================

onMounted(() => {
  handleFilter()
  loadStatistics()
})
</script>

<template>
  <div class="wmp-filter">
    <SplitPanel
      :initial-left-size="320"
      :min-left-size="260"
      :max-left-size="480"
      storage-key="wmpfilter-panel-size"
    >
      <!-- Left Panel: Filter Conditions -->
      <template #left="{ collapsed }">
        <div class="filter-panel" :class="{ 'filter-panel--collapsed': collapsed }">
          <div class="panel-header">
            <h3 v-if="!collapsed">筛选条件</h3>
            <h3 v-else class="collapsed-title">筛选</h3>
          </div>
          
          <div v-if="!collapsed" class="filter-form">
            <!-- Quick Stats -->
            <div class="quick-stats" v-if="statistics">
              <div class="stat-item">
                <div class="stat-label">产品总数</div>
                <div class="stat-value">{{ statistics.total_products.toLocaleString() }}</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">平均收益</div>
                <div class="stat-value">{{ averageYield }}</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">平均期限</div>
                <div class="stat-value">{{ averageDuration }}</div>
              </div>
            </div>
            
            <!-- 收益率筛选 -->
            <div class="filter-section">
              <h4>收益率范围</h4>
              <div class="yield-slider-container">
                <el-slider
                  v-model="yieldRange"
                  range
                  :min="0"
                  :max="10"
                  :step="0.1"
                  :marks="{ 0: '0%', 2.5: '2.5%', 5: '5%', 7.5: '7.5%', 10: '10%' }"
                />
                <div class="range-display">
                  <span class="range-badge">{{ yieldRange[0].toFixed(2) }}%</span>
                  <span class="range-separator">—</span>
                  <span class="range-badge">{{ yieldRange[1].toFixed(2) }}%</span>
                </div>
              </div>
            </div>
            
            <!-- 风险等级筛选 -->
            <div class="filter-section">
              <h4>风险等级</h4>
              <div class="risk-level-grid">
                <div
                  v-for="option in riskLevelOptions"
                  :key="option.value"
                  class="risk-level-card"
                  :class="{ active: filterParams.risk_levels?.includes(option.value) }"
                  @click="() => {
                    if (!filterParams.risk_levels) filterParams.risk_levels = []
                    const index = filterParams.risk_levels.indexOf(option.value)
                    if (index > -1) {
                      filterParams.risk_levels.splice(index, 1)
                    } else {
                      filterParams.risk_levels.push(option.value)
                    }
                  }"
                >
                  <div class="risk-badge" :style="{ backgroundColor: getRiskLevelColor(option.value) }">
                    {{ option.value }}
                  </div>
                  <div class="risk-info">
                    <div class="risk-label">{{ option.label.split(' ')[1] }}</div>
                    <div class="risk-desc">{{ option.description }}</div>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- 产品期限筛选 -->
            <div class="filter-section">
              <h4>产品期限</h4>
              <div class="duration-slider-container">
                <el-slider
                  v-model="durationRange"
                  range
                  :min="7"
                  :max="365"
                  :step="7"
                  :marks="{ 7: '7天', 90: '3个月', 180: '半年', 365: '1年' }"
                />
                <div class="range-display">
                  <span class="range-badge">{{ formatDuration(durationRange[0]) }}</span>
                  <span class="range-separator">—</span>
                  <span class="range-badge">{{ formatDuration(durationRange[1]) }}</span>
                </div>
              </div>
            </div>
            
            <!-- 发行机构搜索 -->
            <div class="filter-section">
              <h4>发行机构</h4>
              <el-input
                v-model="filterParams.issuer"
                placeholder="搜索发行机构..."
                clearable
                @focus="handleInputFocus"
              >
                <template #prefix>
                  <span class="search-icon">🔍</span>
                </template>
              </el-input>
            </div>
            
            <!-- 操作按钮 -->
            <div class="filter-actions">
              <el-button type="primary" @click="handleFilter" :loading="loading" class="action-btn">
                筛选产品
              </el-button>
              <el-button @click="handleReset" class="action-btn">
                重置条件
              </el-button>
            </div>
          </div>
        </div>
      </template>
      
      <!-- Right Panel: Results Table -->
      <template #right>
        <div class="result-panel">
          <div class="panel-header">
            <div class="header-left">
              <h3>银行理财产品 <span class="result-count">({{ total }} 款)</span></h3>
              <span v-if="filterTimeMs !== null" class="filter-time">
                {{ filterTimeMs }}ms
              </span>
            </div>
            <div class="header-right">
              <el-tag type="info" size="small">
                净值型产品
              </el-tag>
            </div>
          </div>
          
          <!-- Skeleton table when loading -->
          <div v-if="loading" class="skeleton-table-wrapper">
            <SkeletonLoader variant="table" :rows="10" :columns="7" />
          </div>
          
          <!-- Empty state when no results -->
          <EmptyState
            v-else-if="!loading && tableData.length === 0"
            icon="search"
            title="未找到符合条件的产品"
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
            @sort-change="handleSortChange"
          >
            <el-table-column
              prop="product_code"
              label="产品代码"
              width="120"
              fixed
            >
              <template #default="{ row }">
                <div class="product-code">{{ row.product_code }}</div>
              </template>
            </el-table-column>
            
            <el-table-column
              prop="product_name"
              label="产品名称"
              min-width="200"
              fixed
            >
              <template #default="{ row }">
                <div class="product-name">
                  {{ row.product_name }}
                  <el-tag v-if="row.product_type" size="small" class="type-tag">
                    {{ row.product_type }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            
            <el-table-column
              prop="yield_rate"
              label="收益率"
              width="110"
              sortable="custom"
            >
              <template #default="{ row }">
                <div class="yield-cell">
                  <span class="yield-value">{{ formatYieldRate(row.yield_rate) }}</span>
                </div>
              </template>
            </el-table-column>
            
            <el-table-column
              prop="risk_level"
              label="风险等级"
              width="100"
            >
              <template #default="{ row }">
                <div
                  class="risk-badge-cell"
                  :style="{ backgroundColor: getRiskLevelColor(row.risk_level) }"
                >
                  {{ row.risk_level }}
                </div>
              </template>
            </el-table-column>
            
            <el-table-column
              prop="duration"
              label="产品期限"
              width="110"
              sortable="custom"
            >
              <template #default="{ row }">
                {{ formatDuration(row.duration) }}
              </template>
            </el-table-column>
            
            <el-table-column
              prop="min_amount"
              label="起购金额"
              width="100"
              sortable="custom"
            >
              <template #default="{ row }">
                <span class="amount-value">{{ formatMinAmount(row.min_amount) }}</span>
              </template>
            </el-table-column>
            
            <el-table-column
              prop="issuer"
              label="发行机构"
              min-width="140"
            >
              <template #default="{ row }">
                <div class="issuer-cell">
                  <span class="issuer-name">{{ row.issuer }}</span>
                </div>
              </template>
            </el-table-column>
          </el-table>
          
          <!-- Pagination -->
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
/* ==================== Main Container ==================== */
.wmp-filter {
  height: calc(100vh - 100px); /* Fallback for older browsers */
  height: calc(100dvh - 100px);
  padding: 0;
  background: var(--bg-system);
}

/* ==================== Filter Panel ==================== */
.filter-panel {
  height: 100%;
  background: var(--bg-card);
  border-radius: 4px;
  padding: var(--spacing-md);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.filter-panel--collapsed {
  padding: var(--spacing-sm);
  align-items: center;
}

.collapsed-title {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  font-size: 14px;
  letter-spacing: 2px;
}

/* ==================== Panel Header ==================== */
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-sm);
  border-bottom: 2px solid var(--brand-navy-dark);
  flex-shrink: 0;
}

.panel-header h3 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: 0.5px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.result-count {
  font-weight: 400;
  font-size: 14px;
  color: var(--text-regular);
}

.filter-time {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-system);
  padding: 2px 8px;
  border-radius: 10px;
  font-family: 'Courier New', monospace;
}

/* ==================== Quick Stats ==================== */
.quick-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-sm);
  background: linear-gradient(135deg, #F8F9FA 0%, #FFFFFF 100%);
  border-radius: 6px;
  border: 1px solid var(--border-line);
}

.stat-item {
  text-align: center;
}

.stat-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 2px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--brand-navy-dark);
}

/* ==================== Filter Sections ==================== */
.filter-section {
  margin-bottom: var(--spacing-lg);
}

.filter-section h4 {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-sm);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-left: 3px solid var(--brand-navy-dark);
  padding-left: var(--spacing-sm);
}

/* ==================== Yield Slider ==================== */
.yield-slider-container,
.duration-slider-container {
  padding: var(--spacing-sm);
  background: var(--bg-system);
  border-radius: 4px;
}

.range-display {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-sm);
}

.range-badge {
  display: inline-block;
  padding: 4px 12px;
  background: var(--brand-navy-dark);
  color: white;
  font-size: 13px;
  font-weight: 600;
  border-radius: 12px;
  min-width: 50px;
  text-align: center;
}

.range-separator {
  color: var(--text-muted);
  font-weight: 300;
}

/* ==================== Risk Level Grid ==================== */
.risk-level-grid {
  display: grid;
  grid-template-columns: repeat(1, 1fr);
  gap: var(--spacing-xs);
}

.risk-level-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--bg-system);
  border: 2px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  min-height: var(--touch-target-min);
  touch-action: manipulation;
}

.risk-level-card:hover {
  background: #F0F4F8;
}

.risk-level-card.active {
  background: #E8F0F8;
  border-color: var(--brand-navy-dark);
}

.risk-badge {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.risk-info {
  flex: 1;
  min-width: 0;
}

.risk-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.risk-desc {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

/* ==================== Issuer Search ==================== */
.search-icon {
  font-size: 14px;
}

/* ==================== Filter Actions ==================== */
.filter-actions {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-lg);
}

.action-btn {
  width: 100%;
  height: var(--touch-target-min);
  font-weight: 600;
}

/* ==================== Result Panel ==================== */
.result-panel {
  height: 100%;
  background: var(--bg-card);
  border-radius: 4px;
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

/* ==================== Table Styles ==================== */
.skeleton-table-wrapper {
  min-height: 400px;
  background: var(--bg-card);
  border-radius: 4px;
}

.product-code {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 600;
}

.product-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.4;
}

.type-tag {
  margin-left: var(--spacing-xs);
  font-size: 10px;
}

.yield-cell {
  display: flex;
  flex-direction: column;
}

.yield-value {
  font-size: 15px;
  font-weight: 700;
  color: var(--market-up);
}

.risk-badge-cell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 12px;
  border-radius: 12px;
  color: white;
  font-size: 11px;
  font-weight: 700;
  min-width: 50px;
}

.amount-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.issuer-cell {
  display: flex;
  flex-direction: column;
}

.issuer-name {
  font-size: 12px;
  color: var(--text-regular);
}

/* ==================== Pagination ==================== */
.pagination {
  margin-top: var(--spacing-md);
  display: flex;
  justify-content: center;
  flex-shrink: 0;
}

/* ==================== Mobile Responsive ==================== */
@media (max-width: 768px) {
  .wmp-filter {
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
  
  .quick-stats {
    grid-template-columns: 1fr;
    gap: var(--spacing-xs);
  }
  
  .stat-item {
    padding: var(--spacing-xs) 0;
  }
  
  .risk-level-grid {
    grid-template-columns: repeat(1, 1fr);
  }
  
  .el-table {
    font-size: 12px;
  }
  
  .panel-header h3 {
    font-size: 16px;
  }
  
  .yield-value {
    font-size: 14px;
  }
  
  .range-badge {
    font-size: 12px;
    padding: 3px 10px;
  }
}

@media (max-width: 480px) {
  .filter-panel {
    padding: var(--spacing-sm);
  }
  
  .quick-stats {
    grid-template-columns: repeat(3, 1fr);
  }
  
  .filter-section h4 {
    font-size: 12px;
  }
}

/* ==================== 4K Responsive (3840px) ==================== */
@media (min-width: 2560px) {
  .panel-header h3 {
    font-size: 22px;
  }
  
  .filter-section h4 {
    font-size: 16px;
  }
  
  .stat-value {
    font-size: 20px;
  }
  
  .el-table {
    font-size: 15px;
  }
  
  .yield-value {
    font-size: 18px;
  }
  
  .risk-badge {
    width: 44px;
    height: 44px;
    font-size: 14px;
  }
}

/* ==================== Custom Scrollbar ==================== */
.filter-panel::-webkit-scrollbar {
  width: 6px;
}

.filter-panel::-webkit-scrollbar-track {
  background: transparent;
}

.filter-panel::-webkit-scrollbar-thumb {
  background: #C1C1C1;
  border-radius: 3px;
}

.filter-panel::-webkit-scrollbar-thumb:hover {
  background: #A8A8A8;
}
</style>
