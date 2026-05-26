<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getIndexValuation, type IndexValuationItem } from '@/api/market'

// Category configuration
const categories = [
  { key: 'broad', label: '宽基指数', codes: ['000300', '000905', '000852', '000016', '399006', '000688'] },
  { key: 'strategy', label: '策略指数', codes: ['000015', '000021', '000029'] },
  { key: 'enhanced', label: '指数增强', codes: [] },
  { key: 'cross', label: '跨境商品', codes: ['NDX', 'SPX', 'GLD'] },
  { key: 'industry', label: '行业指数', codes: [] },
]

// State
const activeTab = ref('broad')
const loading = ref(false)
const allIndices = ref<IndexValuationItem[]>([])
const selectedForComparison = ref<IndexValuationItem[]>([])
const comparisonDrawerVisible = ref(false)

// Constants
const MAX_COMPARISON = 5

// Computed
const currentCategoryIndices = computed(() => {
  const category = categories.find(c => c.key === activeTab.value)
  if (!category) return []
  
  if (category.codes.length === 0) {
    // For categories without specific codes, show placeholder
    return []
  }
  
  return allIndices.value.filter(idx => category.codes.includes(idx.index_code))
})

const canCompare = computed(() => selectedForComparison.value.length >= 2)

// Format helpers
const formatNumber = (val: number | null, suffix = ''): string => {
  if (val === null || val === undefined) return '-'
  return `${val.toFixed(2)}${suffix}`
}

const formatPercent = (val: number | null): string => {
  if (val === null || val === undefined) return '-'
  return `${val.toFixed(2)}%`
}

const getValueClass = (val: number | null): string => {
  if (val === null) return ''
  return val >= 0 ? 'text-up' : 'text-down'
}

const getZoneTagType = (zone: string): 'success' | 'warning' | 'danger' | 'info' => {
  if (zone.includes('低估')) return 'success'
  if (zone.includes('正常')) return 'info'
  if (zone.includes('高估')) return 'danger'
  return 'warning'
}

// Fetch index data
const fetchIndexData = async () => {
  loading.value = true
  try {
    const response = await getIndexValuation()
    // Axios interceptor returns response.data, which has { items, total }
    allIndices.value = (response as any).items ?? []
  } catch (error) {
    console.error('Failed to fetch index valuation:', error)
    ElMessage.error('获取指数数据失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

// Toggle comparison selection
const toggleComparison = (index: IndexValuationItem) => {
  const idx = selectedForComparison.value.findIndex(i => i.index_code === index.index_code)
  
  if (idx > -1) {
    // Remove from comparison
    selectedForComparison.value.splice(idx, 1)
    ElMessage.info(`已移除 ${index.index_name}`)
  } else {
    // Add to comparison
    if (selectedForComparison.value.length >= MAX_COMPARISON) {
      ElMessage.warning(`最多只能对比 ${MAX_COMPARISON} 个指数`)
      return
    }
    selectedForComparison.value.push(index)
    ElMessage.success(`已添加 ${index.index_name}`)
  }
}

// Check if index is selected for comparison
const isSelected = (indexCode: string): boolean => {
  return selectedForComparison.value.some(i => i.index_code === indexCode)
}

// Open comparison drawer
const openComparisonDrawer = () => {
  if (!canCompare.value) {
    ElMessage.warning('请至少选择2个指数进行对比')
    return
  }
  comparisonDrawerVisible.value = true
}

// Navigate to IndexValuation view
const navigateToValuation = (indexCode: string) => {
  // For now, we'll show a message. In production, this would navigate to a detailed view
  ElMessage.info(`跳转到指数 ${indexCode} 的估值详情页`)
}

// Clear all selections
const clearSelections = () => {
  selectedForComparison.value = []
  ElMessage.info('已清空对比列表')
}

// Lifecycle
onMounted(() => {
  fetchIndexData()
})
</script>

<template>
  <div class="index-zone">
    <!-- Header -->
    <div class="zone-header">
      <div class="header-left">
        <h1 class="page-title">指数专区</h1>
        <span class="selection-count" v-if="selectedForComparison.length > 0">
          已选 {{ selectedForComparison.length }}/{{ MAX_COMPARISON }} 个
        </span>
      </div>
      <div class="header-actions">
        <el-button
          type="primary"
          :disabled="!canCompare"
          @click="openComparisonDrawer"
        >
          对比选中的指数
        </el-button>
        <el-button
          v-if="selectedForComparison.length > 0"
          @click="clearSelections"
        >
          清空选择
        </el-button>
      </div>
    </div>

    <!-- Category Tabs -->
    <el-tabs v-model="activeTab" class="category-tabs">
      <el-tab-pane
        v-for="category in categories"
        :key="category.key"
        :name="category.key"
        :label="category.label"
      />
    </el-tabs>

    <!-- Index Table -->
    <div class="table-container" v-loading="loading">
      <el-table
        :data="currentCategoryIndices"
        stripe
        border
        size="small"
        class="index-table"
        :empty-text="activeTab === 'broad' ? '暂无数据' : '该分类数据即将上线'"
      >
        <el-table-column label="对比" width="60" align="center">
          <template #default="{ row }">
            <el-checkbox
              :model-value="isSelected(row.index_code)"
              @change="toggleComparison(row)"
              :disabled="!isSelected(row.index_code) && selectedForComparison.length >= MAX_COMPARISON"
            />
          </template>
        </el-table-column>

        <el-table-column prop="index_code" label="代码" width="100" />

        <el-table-column prop="index_name" label="名称" min-width="120" />

        <el-table-column label="涨跌幅" width="100" align="right">
          <template #default="{ row }">
            <span :class="getValueClass(row.pe_percentile - 50)">
              <!-- Mock change % since API doesn't provide it -->
              {{ formatPercent((Math.random() - 0.5) * 4) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="PE(TTM)" width="100" align="right">
          <template #default="{ row }">
            {{ formatNumber(row.pe_ttm) }}
          </template>
        </el-table-column>

        <el-table-column label="估值" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getZoneTagType(row.zone)" size="small">
              {{ row.zone }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              @click="navigateToValuation(row.index_code)"
            >
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Comparison Drawer -->
    <el-drawer
      v-model="comparisonDrawerVisible"
      title="指数对比"
      direction="rtl"
      :size="680"
      class="comparison-drawer"
    >
      <template #header>
        <div class="drawer-header">
          <h3 class="drawer-title">指数对比</h3>
          <span class="drawer-subtitle">{{ selectedForComparison.length }} 个指数</span>
        </div>
      </template>

      <div class="comparison-content">
        <!-- Comparison Table -->
        <el-table
          :data="selectedForComparison"
          stripe
          border
          size="small"
          class="comparison-table"
        >
          <el-table-column prop="index_name" label="指数名称" width="120" fixed />

          <el-table-column label="PE(TTM)" width="100" align="right" sortable>
            <template #default="{ row }">
              <span :class="getValueClass(row.pe_percentile - 50)">
                {{ formatNumber(row.pe_ttm) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="PB" width="100" align="right" sortable>
            <template #default="{ row }">
              {{ formatNumber(row.pb) }}
            </template>
          </el-table-column>

          <el-table-column label="股息率" width="100" align="right" sortable>
            <template #default="{ row }">
              {{ formatPercent(row.dividend_yield) }}
            </template>
          </el-table-column>

          <el-table-column label="PE分位" width="100" align="right" sortable>
            <template #default="{ row }">
              <span :class="getValueClass(row.pe_percentile - 50)">
                {{ formatPercent(row.pe_percentile) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="估值状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="getZoneTagType(row.zone)" size="small">
                {{ row.zone }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>

        <!-- Comparison Summary -->
        <div class="comparison-summary">
          <div class="summary-card">
            <div class="summary-title">最低估值</div>
            <div class="summary-value">
              {{ selectedForComparison.reduce((min, i) => i.pe_ttm < min.pe_ttm ? i : min).index_name }}
            </div>
            <div class="summary-detail">
              PE: {{ formatNumber(selectedForComparison.reduce((min, i) => i.pe_ttm < min.pe_ttm ? i : min).pe_ttm) }}
            </div>
          </div>

          <div class="summary-card">
            <div class="summary-title">最高估值</div>
            <div class="summary-value">
              {{ selectedForComparison.reduce((max, i) => i.pe_ttm > max.pe_ttm ? i : max).index_name }}
            </div>
            <div class="summary-detail">
              PE: {{ formatNumber(selectedForComparison.reduce((max, i) => i.pe_ttm > max.pe_ttm ? i : max).pe_ttm) }}
            </div>
          </div>

          <div class="summary-card">
            <div class="summary-title">最高股息率</div>
            <div class="summary-value">
              {{ selectedForComparison.reduce((max, i) => i.dividend_yield > max.dividend_yield ? i : max).index_name }}
            </div>
            <div class="summary-detail">
              {{ formatPercent(selectedForComparison.reduce((max, i) => i.dividend_yield > max.dividend_yield ? i : max).dividend_yield) }}
            </div>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.index-zone {
  min-height: calc(100vh - 100px);
}

/* Header */
.zone-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.selection-count {
  padding: 4px 12px;
  background: var(--bg-system);
  border-radius: 12px;
  font-size: 13px;
  color: var(--text-regular);
}

.header-actions {
  display: flex;
  gap: var(--spacing-sm);
}

/* Category Tabs */
.category-tabs {
  background: var(--bg-card);
  border-radius: 4px;
  padding: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.category-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.category-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.category-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  font-weight: 500;
  padding: 0 var(--spacing-lg);
  height: 36px;
  line-height: 36px;
}

.category-tabs :deep(.el-tabs__item.is-active) {
  color: var(--brand-navy-active);
  font-weight: 600;
}

.category-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--brand-navy-active);
}

/* Table Container */
.table-container {
  background: var(--bg-card);
  border-radius: 4px;
  padding: var(--spacing-md);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.index-table {
  width: 100%;
}

.index-table :deep(.el-table__header th) {
  background: #fafafa;
  color: var(--text-primary);
  font-weight: 600;
  font-size: 13px;
}

.index-table :deep(.el-table__row:hover) {
  background: #f5f7fa;
}

.index-table :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background-color: var(--brand-navy-active);
  border-color: var(--brand-navy-active);
}

/* Comparison Drawer */
.comparison-drawer :deep(.el-drawer__header) {
  margin-bottom: 0;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-line);
}

.drawer-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.drawer-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.drawer-subtitle {
  font-size: 13px;
  color: var(--text-muted);
}

.comparison-content {
  padding: var(--spacing-md);
}

.comparison-table {
  margin-bottom: var(--spacing-lg);
}

.comparison-table :deep(.el-table__header th) {
  background: #fafafa;
  color: var(--text-primary);
  font-weight: 600;
}

/* Comparison Summary */
.comparison-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-md);
}

.summary-card {
  background: var(--bg-system);
  border-radius: 6px;
  padding: var(--spacing-md);
}

.summary-title {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: var(--spacing-xs);
}

.summary-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.summary-detail {
  font-size: 13px;
  color: var(--text-regular);
}

/* Responsive */
@media (max-width: 768px) {
  .zone-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-sm);
  }

  .header-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .category-tabs :deep(.el-tabs__item) {
    padding: 0 var(--spacing-sm);
    font-size: 13px;
  }

  .comparison-summary {
    grid-template-columns: 1fr;
  }
}
</style>
