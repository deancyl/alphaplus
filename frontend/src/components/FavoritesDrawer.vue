<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElDrawer, ElTabs, ElTabPane, ElTable, ElButton, ElIcon, ElMessageBox, ElMessage, ElBadge } from 'element-plus'
import { Delete, Top, ArrowUp, ArrowDown, Refresh, DeleteFilled } from '@element-plus/icons-vue'
import type { Favorite } from '@/api/favorites'
import { favoritesApi } from '@/api/favorites'

// Props
interface Props {
  visible: boolean
}

const props = defineProps<Props>()

// Emits
const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

// LocalStorage key
const STORAGE_KEY = 'alphaplus_favorites'

// Product type tabs
const productTypes = [
  { key: 'funds', label: '基金', icon: '📈' },
  { key: 'stocks', label: '股票', icon: '📊' },
  { key: 'wmps', label: '理财', icon: '💰' },
  { key: 'insurance', label: '保险', icon: '🛡️' },
]

// State
const activeTab = ref('funds')
const favorites = ref<Record<string, Favorite[]>>({
  funds: [],
  stocks: [],
  wmps: [],
  insurance: [],
})
const syncing = ref(false)

// Computed
const currentFavorites = computed(() => favorites.value[activeTab.value] || [])
const totalCount = computed(() => {
  return Object.values(favorites.value).reduce((sum, arr) => sum + arr.length, 0)
})

// Expose for potential future use
defineExpose({
  currentFavorites,
  totalCount,
  favorites,
})

// Load from localStorage
const loadFromStorage = () => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      favorites.value = {
        funds: parsed.funds || [],
        stocks: parsed.stocks || [],
        wmps: parsed.wmps || [],
        insurance: parsed.insurance || [],
      }
    }
  } catch (error) {
    console.error('Failed to load favorites from localStorage:', error)
  }
}

// Save to localStorage
const saveToStorage = () => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites.value))
  } catch (error) {
    console.error('Failed to save favorites to localStorage:', error)
    ElMessage.error('保存失败，请检查浏览器存储空间')
  }
}

// Reassign sort_order
const reassignSortOrder = (items: Favorite[]) => {
  items.forEach((item, index) => {
    item.sort_order = index + 1
  })
}

// Pin to top
const handlePin = (index: number) => {
  const items = favorites.value[activeTab.value]
  const [item] = items.splice(index, 1)
  items.unshift(item)
  reassignSortOrder(items)
  saveToStorage()
  ElMessage.success('已置顶')
}

// Move up
const handleMoveUp = (index: number) => {
  if (index === 0) return
  const items = favorites.value[activeTab.value]
  ;[items[index - 1], items[index]] = [items[index], items[index - 1]]
  reassignSortOrder(items)
  saveToStorage()
}

// Move down
const handleMoveDown = (index: number) => {
  const items = favorites.value[activeTab.value]
  if (index === items.length - 1) return
  ;[items[index], items[index + 1]] = [items[index + 1], items[index]]
  reassignSortOrder(items)
  saveToStorage()
}

// Delete with confirmation
const handleDelete = async (index: number, row: Favorite) => {
  try {
    await ElMessageBox.confirm(
      `确定要移除「${row.product_name}」吗？`,
      '确认移除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    favorites.value[activeTab.value].splice(index, 1)
    reassignSortOrder(favorites.value[activeTab.value])
    saveToStorage()
    ElMessage.success('已移除')
  } catch {
    // User cancelled
  }
}

// Clear all with confirmation
const handleClearAll = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有自选产品吗？此操作不可恢复。',
      '确认清空',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    favorites.value = {
      funds: [],
      stocks: [],
      wmps: [],
      insurance: [],
    }
    saveToStorage()
    ElMessage.success('已清空')
  } catch {
    // User cancelled
  }
}

// Sync to cloud
const handleSyncToCloud = async () => {
  syncing.value = true
  try {
    const allFavorites = Object.values(favorites.value).flat()
    await favoritesApi.sync(allFavorites)
    ElMessage.success('同步成功')
  } catch (error) {
    console.error('Sync failed:', error)
    ElMessage.error('同步失败，请稍后重试')
  } finally {
    syncing.value = false
  }
}

// Close drawer
const handleClose = () => {
  emit('update:visible', false)
}

// Watch for visibility changes
watch(() => props.visible, (newVal) => {
  if (newVal) {
    loadFromStorage()
  }
})

// Load on mount
onMounted(() => {
  loadFromStorage()
})
</script>

<template>
  <ElDrawer
    :model-value="visible"
    @update:model-value="emit('update:visible', $event)"
    title="自选产品管理"
    direction="rtl"
    :size="560"
    :before-close="handleClose"
    class="favorites-drawer"
  >
    <template #header>
      <div class="drawer-header">
        <h3 class="drawer-title">自选产品管理</h3>
        <div class="drawer-actions">
          <ElButton
            type="primary"
            :icon="Refresh"
            :loading="syncing"
            @click="handleSyncToCloud"
            size="small"
          >
            同步云端
          </ElButton>
          <ElButton
            type="danger"
            :icon="DeleteFilled"
            @click="handleClearAll"
            size="small"
            plain
          >
            清空
          </ElButton>
        </div>
      </div>
    </template>

    <div class="drawer-content">
      <ElTabs v-model="activeTab" class="favorites-tabs">
        <ElTabPane
          v-for="type in productTypes"
          :key="type.key"
          :name="type.key"
          :label="`${type.icon} ${type.label}`"
        >
          <template #label>
            <span class="tab-label">
              <span class="tab-icon">{{ type.icon }}</span>
              <span class="tab-text">{{ type.label }}</span>
              <ElBadge
                v-if="favorites[type.key].length > 0"
                :value="favorites[type.key].length"
                class="tab-badge"
                type="primary"
              />
            </span>
          </template>

          <div class="table-wrapper">
            <ElTable
              :data="favorites[type.key]"
              stripe
              :empty-text="`暂无${type.label}自选`"
              class="favorites-table"
            >
              <ElTable.Column
                prop="sort_order"
                label="序号"
                width="60"
                align="center"
              />
              
              <ElTable.Column
                prop="product_name"
                label="产品名称"
                min-width="140"
                show-overflow-tooltip
              />
              
              <ElTable.Column
                prop="product_code"
                label="代码"
                width="100"
                align="center"
              />
              
              <ElTable.Column
                label="操作"
                width="180"
                align="center"
              >
                <template #default="{ row, $index }">
                  <div class="action-buttons">
                    <ElButton
                      link
                      type="primary"
                      size="small"
                      @click="handlePin($index)"
                      :disabled="$index === 0"
                      title="置顶"
                    >
                      <ElIcon><Top /></ElIcon>
                    </ElButton>
                    <ElButton
                      link
                      type="primary"
                      size="small"
                      @click="handleMoveUp($index)"
                      :disabled="$index === 0"
                      title="上移"
                    >
                      <ElIcon><ArrowUp /></ElIcon>
                    </ElButton>
                    <ElButton
                      link
                      type="primary"
                      size="small"
                      @click="handleMoveDown($index)"
                      :disabled="$index === favorites[type.key].length - 1"
                      title="下移"
                    >
                      <ElIcon><ArrowDown /></ElIcon>
                    </ElButton>
                    <ElButton
                      link
                      type="danger"
                      size="small"
                      @click="handleDelete($index, row)"
                      title="删除"
                    >
                      <ElIcon><Delete /></ElIcon>
                    </ElButton>
                  </div>
                </template>
              </ElTable.Column>
            </ElTable>
          </div>
        </ElTabPane>
      </ElTabs>
    </div>
  </ElDrawer>
</template>

<style scoped>
.favorites-drawer {
  --drawer-padding: 0;
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: var(--spacing-xl);
}

.drawer-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: 0.5px;
}

.drawer-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.drawer-content {
  padding: 0 var(--spacing-md) var(--spacing-md);
}

.favorites-tabs {
  --el-tabs-header-height: 48px;
}

.favorites-tabs :deep(.el-tabs__header) {
  margin: 0 0 var(--spacing-md) 0;
  background: var(--bg-system);
  border-radius: 4px;
  padding: var(--spacing-xs);
}

.favorites-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.favorites-tabs :deep(.el-tabs__item) {
  padding: 0 var(--spacing-md);
  font-weight: 500;
  transition: all 0.2s;
}

.favorites-tabs :deep(.el-tabs__item.is-active) {
  background: var(--bg-card);
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.tab-label {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.tab-icon {
  font-size: 16px;
}

.tab-text {
  font-size: 14px;
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

.table-wrapper {
  background: var(--bg-card);
  border-radius: 4px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.favorites-table {
  width: 100%;
}

.favorites-table :deep(.el-table__header th) {
  background: #fafafa;
  color: var(--text-primary);
  font-weight: 600;
  font-size: 13px;
}

.favorites-table :deep(.el-table__row) {
  transition: background-color 0.15s;
}

.favorites-table :deep(.el-table__row:hover) {
  background: #f5f7fa !important;
}

.favorites-table :deep(.el-table__cell) {
  padding: 10px 0;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 4px;
}

.action-buttons .el-button {
  padding: 4px 8px;
  min-width: 28px;
  touch-action: manipulation;
}

.action-buttons .el-button:disabled {
  opacity: 0.3;
}

/* Empty state */
.favorites-table :deep(.el-table__empty-block) {
  padding: var(--spacing-xl);
}

.favorites-table :deep(.el-table__empty-text) {
  color: var(--text-muted);
  font-size: 14px;
}

/* Responsive */
@media (max-width: 768px) {
  .drawer-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-sm);
  }
  
  .drawer-actions {
    width: 100%;
  }
  
  .drawer-actions .el-button {
    flex: 1;
  }
  
  .favorites-tabs :deep(.el-tabs__item) {
    padding: 0 var(--spacing-sm);
    font-size: 13px;
  }
  
  .tab-icon {
    font-size: 14px;
  }
  
  .tab-text {
    font-size: 12px;
  }
}
</style>
