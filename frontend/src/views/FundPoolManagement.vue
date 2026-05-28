<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  ElTabs,
  ElTabPane,
  ElButton,
  ElTag,
  ElBadge,
  ElDropdown,
  ElDropdownMenu,
  ElDropdownItem,
  ElMessageBox,
  ElMessage,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
} from 'element-plus'
import { Plus, Star, Delete, Rank, ArrowRight } from '@element-plus/icons-vue'
import { poolApi, type PoolFund, type PoolAddRequest } from '@/api/pool'
import type { Favorite } from '@/api/favorites'

// Route
const route = useRoute()

// Pool types with metadata
const poolTypes = [
  { key: 'entry', label: '准入池', subLabel: '备选池', icon: '📋', color: '#0B3CC3' },
  { key: 'focus', label: '重点池', subLabel: '核心池', icon: '⭐', color: '#E63935' },
  { key: 'exit', label: '出池', subLabel: '已清退', icon: '📤', color: '#999999' },
]

// State
const activeTab = ref('entry')
const pools = ref<Record<string, PoolFund[]>>({
  entry: [],
  focus: [],
  exit: [],
})
const loading = ref(false)
const draggedFund = ref<PoolFund | null>(null)
const dragSourcePool = ref<string | null>(null)

// Add fund dialog
const addDialogVisible = ref(false)
const addForm = ref<PoolAddRequest>({
  pool_type: 'entry',
  fund_code: '',
  fund_name: '',
  notes: '',
})
const addFormLoading = ref(false)

// Computed
const currentPoolFunds = computed(() => pools.value[activeTab.value] || [])
const poolCounts = computed(() => ({
  entry: pools.value.entry.filter(f => f.status === 'active').length,
  focus: pools.value.focus.filter(f => f.status === 'active').length,
  exit: pools.value.exit.length,
}))

// Load all pools
const loadAllPools = async () => {
  loading.value = true
  try {
    const [entryRes, focusRes, exitRes] = await Promise.all([
      poolApi.list('entry', 'active'),
      poolApi.list('focus', 'active'),
      poolApi.list('exit'),
    ])
    pools.value = {
      entry: entryRes.funds,
      focus: focusRes.funds,
      exit: exitRes.funds,
    }
  } catch (error) {
    console.error('Failed to load pools:', error)
    ElMessage.error('加载基金池失败')
  } finally {
    loading.value = false
  }
}

// Load single pool
const loadPool = async (poolType: string | number) => {
  const poolTypeStr = String(poolType)
  try {
    const status = poolTypeStr === 'exit' ? undefined : 'active'
    const response = await poolApi.list(poolTypeStr, status)
    pools.value[poolTypeStr] = response.funds
  } catch (error) {
    console.error(`Failed to load ${poolTypeStr} pool:`, error)
  }
}

// Format number
const formatNumber = (val: number | null | undefined, suffix = ''): string => {
  if (val === null || val === undefined) return '-'
  return `${val.toFixed(2)}${suffix}`
}

// Get return class
const getReturnClass = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return ''
  return val >= 0 ? 'text-up' : 'text-down'
}

// Format date
const formatDate = (dateStr: string): string => {
  if (!dateStr) return '-'
  return dateStr.split('T')[0]
}

// Open add dialog
const openAddDialog = () => {
  addForm.value = {
    pool_type: activeTab.value,
    fund_code: '',
    fund_name: '',
    notes: '',
  }
  addDialogVisible.value = true
}

// Add fund to pool
const handleAddFund = async () => {
  if (!addForm.value.fund_code || !addForm.value.fund_name) {
    ElMessage.warning('请填写基金代码和名称')
    return
  }
  
  addFormLoading.value = true
  try {
    await poolApi.add(addForm.value)
    ElMessage.success('添加成功')
    addDialogVisible.value = false
    await loadPool(addForm.value.pool_type)
  } catch (error) {
    console.error('Failed to add fund:', error)
    ElMessage.error('添加失败')
  } finally {
    addFormLoading.value = false
  }
}

// Transfer fund between pools
const handleTransfer = async (fund: PoolFund, targetPool: string) => {
  try {
    await ElMessageBox.confirm(
      `确定将「${fund.fund_name}」转移到${poolTypes.find(p => p.key === targetPool)?.label}吗？`,
      '转移确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info',
      }
    )
    
    await poolApi.transfer({ id: fund.id, new_pool_type: targetPool })
    ElMessage.success('转移成功')
    await loadAllPools()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to transfer fund:', error)
      ElMessage.error('转移失败')
    }
  }
}

// Remove fund from pool
const handleRemove = async (fund: PoolFund) => {
  try {
    await ElMessageBox.confirm(
      `确定将「${fund.fund_name}」移出基金池吗？`,
      '移除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    await poolApi.remove(fund.id)
    ElMessage.success('移除成功')
    await loadPool(fund.pool_type)
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to remove fund:', error)
      ElMessage.error('移除失败')
    }
  }
}

// Add to favorites
const handleAddToFavorites = (fund: PoolFund) => {
  const favorite: Favorite = {
    product_type: 'funds',
    product_code: fund.fund_code,
    product_name: fund.fund_name,
    sort_order: 1,
  }
  
  // Load existing favorites
  const stored = localStorage.getItem('alphaplus_favorites')
  const favorites = stored ? JSON.parse(stored) : { funds: [], stocks: [], wmps: [], insurance: [] }
  
  // Check if already exists
  const exists = favorites.funds?.some((f: Favorite) => f.product_code === fund.fund_code)
  if (exists) {
    ElMessage.info('该基金已在自选中')
    return
  }
  
  // Add to favorites
  favorites.funds = favorites.funds || []
  favorite.sort_order = favorites.funds.length + 1
  favorites.funds.push(favorite)
  
  localStorage.setItem('alphaplus_favorites', JSON.stringify(favorites))
  ElMessage.success('已添加到自选')
}

// Drag and drop handlers
const handleDragStart = (fund: PoolFund, sourcePool: string) => {
  draggedFund.value = fund
  dragSourcePool.value = sourcePool
}

const handleDragEnd = () => {
  draggedFund.value = null
  dragSourcePool.value = null
}

const handleDragOver = (e: DragEvent) => {
  e.preventDefault()
}

const handleDrop = async (targetPool: string) => {
  if (!draggedFund.value || dragSourcePool.value === targetPool) {
    return
  }
  
  const fund = draggedFund.value
  draggedFund.value = null
  dragSourcePool.value = null
  
  await handleTransfer(fund, targetPool)
}

// Bulk add from FundFilter (route param)
const handleBulkAddFromFilter = () => {
  // This would open a dialog to select funds from filter results
  // For now, show a placeholder message
  ElMessage.info('请从基金筛选页面选择基金后添加')
}

// Handle route query params (from FundFilter)
watch(() => route.query, (query) => {
  if (query.addToPool && query.fundCode && query.fundName) {
    const poolType = (query.poolType as string) || 'entry'
    addForm.value = {
      pool_type: poolType,
      fund_code: query.fundCode as string,
      fund_name: query.fundName as string,
      notes: (query.notes as string) || '',
    }
    addDialogVisible.value = true
  }
}, { immediate: true })

// Load on mount
onMounted(() => {
  loadAllPools()
})
</script>

<template>
  <div class="fund-pool-management">
    <!-- Header -->
    <div class="pool-header">
      <div class="header-left">
        <h2 class="page-title">基金池管理</h2>
        <span class="pool-subtitle">管理准入、重点、清退基金池</span>
      </div>
      <div class="header-actions">
        <ElButton type="primary" :icon="Plus" @click="openAddDialog">
          添加基金
        </ElButton>
        <ElButton :icon="Rank" @click="handleBulkAddFromFilter">
          从筛选结果添加
        </ElButton>
      </div>
    </div>

    <!-- Tabs -->
    <ElTabs v-model="activeTab" class="pool-tabs" @tab-change="loadPool">
      <ElTabPane
        v-for="poolType in poolTypes"
        :key="poolType.key"
        :name="poolType.key"
      >
        <template #label>
          <div
            class="tab-label-wrapper"
            @dragover="handleDragOver"
            @drop="handleDrop(poolType.key)"
          >
            <span class="tab-icon">{{ poolType.icon }}</span>
            <span class="tab-text">{{ poolType.label }}</span>
            <span class="tab-sub">({{ poolType.subLabel }})</span>
            <ElBadge
              :value="poolCounts[poolType.key as keyof typeof poolCounts]"
              :max="99"
              class="tab-badge"
              :type="poolType.key === 'exit' ? 'info' : 'primary'"
            />
          </div>
        </template>

        <!-- Cards Grid -->
        <div
          class="pool-cards-grid"
          :class="{ 'is-dragging': draggedFund }"
        >
          <div
            v-for="fund in currentPoolFunds"
            :key="fund.id"
            class="fund-card"
            :class="{ 'is-removed': fund.status === 'removed' }"
            draggable="true"
            @dragstart="handleDragStart(fund, activeTab)"
            @dragend="handleDragEnd"
          >
            <!-- Card Header -->
            <div class="card-header">
              <div class="fund-identity">
                <h4 class="fund-name">{{ fund.fund_name }}</h4>
                <span class="fund-code">{{ fund.fund_code }}</span>
              </div>
              <ElTag
                :type="fund.status === 'active' ? 'success' : 'info'"
                size="small"
                effect="light"
              >
                {{ fund.status === 'active' ? '活跃' : '已移除' }}
              </ElTag>
            </div>

            <!-- Card Metrics -->
            <div class="card-metrics">
              <div class="metric-item">
                <span class="metric-label">近1年收益</span>
                <span
                  class="metric-value"
                  :class="getReturnClass(fund.return_1y)"
                >
                  {{ formatNumber(fund.return_1y, '%') }}
                </span>
              </div>
              <div class="metric-item">
                <span class="metric-label">规模</span>
                <span class="metric-value">{{ formatNumber(fund.scale, '亿') }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">经理</span>
                <span class="metric-value">{{ fund.manager || '-' }}</span>
              </div>
            </div>

            <!-- Card Info -->
            <div class="card-info">
              <div class="info-row">
                <span class="info-label">加入日期</span>
                <span class="info-value">{{ formatDate(fund.added_date) }}</span>
              </div>
              <div v-if="fund.removed_date" class="info-row">
                <span class="info-label">移除日期</span>
                <span class="info-value">{{ formatDate(fund.removed_date) }}</span>
              </div>
              <div v-if="fund.notes" class="info-row notes">
                <span class="info-label">备注</span>
                <span class="info-value">{{ fund.notes }}</span>
              </div>
            </div>

            <!-- Card Actions -->
            <div class="card-actions">
              <!-- Transfer Dropdown -->
              <ElDropdown
                v-if="fund.status === 'active'"
                trigger="click"
                @command="(cmd: string) => handleTransfer(fund, cmd)"
              >
                <ElButton size="small" :icon="ArrowRight">
                  转移
                </ElButton>
                <template #dropdown>
                  <ElDropdownMenu>
                    <ElDropdownItem
                      v-for="pt in poolTypes.filter(p => p.key !== fund.pool_type)"
                      :key="pt.key"
                      :command="pt.key"
                    >
                      {{ pt.icon }} {{ pt.label }}
                    </ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>

              <!-- Add to Favorites -->
              <ElButton
                size="small"
                :icon="Star"
                @click="handleAddToFavorites(fund)"
              >
                自选
              </ElButton>

              <!-- Remove -->
              <ElButton
                size="small"
                type="danger"
                :icon="Delete"
                plain
                @click="handleRemove(fund)"
              >
                移除
              </ElButton>
            </div>
          </div>

          <!-- Empty State -->
          <div v-if="currentPoolFunds.length === 0" class="empty-state">
            <div class="empty-icon">📭</div>
            <p class="empty-text">暂无基金</p>
            <ElButton type="primary" :icon="Plus" @click="openAddDialog">
              添加第一只基金
            </ElButton>
          </div>
        </div>
      </ElTabPane>
    </ElTabs>

    <!-- Add Fund Dialog -->
    <ElDialog
      v-model="addDialogVisible"
      title="添加基金到池"
      width="480px"
      :close-on-click-modal="false"
    >
      <ElForm :model="addForm" label-width="80px">
        <ElFormItem label="目标池">
          <ElSelect v-model="addForm.pool_type" style="width: 100%">
            <ElOption
              v-for="pt in poolTypes"
              :key="pt.key"
              :label="`${pt.icon} ${pt.label} (${pt.subLabel})`"
              :value="pt.key"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="基金代码" required>
          <ElInput v-model="addForm.fund_code" placeholder="如: 000001" />
        </ElFormItem>
        <ElFormItem label="基金名称" required>
          <ElInput v-model="addForm.fund_name" placeholder="如: 华夏成长混合" />
        </ElFormItem>
        <ElFormItem label="备注">
          <ElInput
            v-model="addForm.notes"
            type="textarea"
            :rows="2"
            placeholder="可选备注信息"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="addDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="addFormLoading" @click="handleAddFund">
          确定添加
        </ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.fund-pool-management {
  height: calc(100vh - 100px); /* Fallback for older browsers */
  height: calc(100dvh - 100px);
  display: flex;
  flex-direction: column;
  padding: var(--spacing-md);
  background: var(--bg-system);
}

/* Header */
.pool-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  background: var(--bg-card);
  border-radius: 4px;
  margin-bottom: var(--spacing-md);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: var(--spacing-md);
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: 0.5px;
}

.pool-subtitle {
  font-size: 13px;
  color: var(--text-muted);
}

.header-actions {
  display: flex;
  gap: var(--spacing-sm);
}

/* Tabs */
.pool-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border-radius: 4px;
  padding: var(--spacing-sm);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.pool-tabs :deep(.el-tabs__header) {
  margin: 0 0 var(--spacing-md) 0;
  background: var(--bg-system);
  border-radius: 4px;
  padding: var(--spacing-xs);
}

.pool-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.pool-tabs :deep(.el-tabs__item) {
  padding: 0;
  font-weight: 500;
  transition: all 0.2s;
  height: 48px;
  line-height: 48px;
}

.pool-tabs :deep(.el-tabs__item.is-active) {
  background: var(--bg-card);
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.pool-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow: hidden;
}

.pool-tabs :deep(.el-tab-pane) {
  height: 100%;
}

.tab-label-wrapper {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: 0 var(--spacing-md);
  height: 100%;
}

.tab-icon {
  font-size: 16px;
}

.tab-text {
  font-size: 14px;
  font-weight: 600;
}

.tab-sub {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 400;
}

.tab-badge {
  margin-left: var(--spacing-xs);
}

.tab-badge :deep(.el-badge__content) {
  font-size: 11px;
  height: 18px;
  line-height: 18px;
  padding: 0 6px;
}

/* Cards Grid */
.pool-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--spacing-md);
  padding: var(--spacing-xs);
  overflow-y: auto;
  max-height: calc(100vh - 260px); /* Fallback for older browsers */
  max-height: calc(100dvh - 260px);
}

.pool-cards-grid.is-dragging {
  background: rgba(11, 60, 195, 0.02);
}

/* Fund Card */
.fund-card {
  background: var(--bg-card);
  border: 1px solid var(--border-line);
  border-radius: 8px;
  padding: var(--spacing-md);
  transition: all 0.2s ease;
  cursor: grab;
}

.fund-card:hover {
  border-color: var(--brand-navy-active);
  box-shadow: 0 4px 12px rgba(11, 60, 195, 0.12);
  transform: translateY(-2px);
}

.fund-card:active {
  cursor: grabbing;
}

.fund-card.is-removed {
  opacity: 0.6;
  background: var(--bg-system);
}

.fund-card.is-removed:hover {
  opacity: 0.8;
}

/* Card Header */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-sm);
  border-bottom: 1px solid var(--border-line);
}

.fund-identity {
  flex: 1;
  min-width: 0;
}

.fund-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-xs) 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fund-code {
  font-size: 12px;
  color: var(--text-muted);
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
}

/* Card Metrics */
.card-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-label {
  font-size: 11px;
  color: var(--text-muted);
}

.metric-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

/* Card Info */
.card-info {
  margin-bottom: var(--spacing-md);
  padding: var(--spacing-sm);
  background: var(--bg-system);
  border-radius: 4px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  padding: 2px 0;
}

.info-row.notes {
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}

.info-label {
  color: var(--text-muted);
}

.info-value {
  color: var(--text-regular);
  font-weight: 500;
}

/* Card Actions */
.card-actions {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
}

.card-actions .el-button {
  flex: 1;
  min-width: 60px;
}

/* Empty State */
.empty-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl) var(--spacing-md);
  color: var(--text-muted);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: var(--spacing-md);
  opacity: 0.5;
}

.empty-text {
  font-size: 15px;
  margin-bottom: var(--spacing-md);
}

/* Drag indicator */
.pool-tabs :deep(.el-tabs__item) {
  transition: background 0.2s;
}

.pool-cards-grid.is-dragging ~ .pool-tabs :deep(.el-tabs__item:hover) {
  background: rgba(11, 60, 195, 0.05);
}

/* Responsive */
@media (max-width: 768px) {
  .pool-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-sm);
  }
  
  .header-actions {
    width: 100%;
  }
  
  .header-actions .el-button {
    flex: 1;
  }
  
  .pool-cards-grid {
    grid-template-columns: 1fr;
  }
  
  .tab-sub {
    display: none;
  }
  
  .tab-label-wrapper {
    padding: 0 var(--spacing-sm);
  }
  
  .card-actions {
    flex-direction: column;
  }
  
  .card-actions .el-button {
    width: 100%;
  }
}

@media (max-width: 480px) {
  .fund-pool-management {
    padding: var(--spacing-sm);
  }
  
  .page-title {
    font-size: 18px;
  }
  
  .pool-subtitle {
    display: none;
  }
  
  .card-metrics {
    grid-template-columns: 1fr;
    gap: var(--spacing-xs);
  }
}
</style>
