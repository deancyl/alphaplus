<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { filterFunds, type FundFilterParams, type FundItem } from '@/api/fund'

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
const leftPanelCollapsed = ref(false)

// 计算分页
const totalPages = computed(() => Math.ceil(total.value / filterParams.value.page_size!))

// 执行筛选
const handleFilter = async () => {
  loading.value = true
  try {
    const response = await filterFunds(filterParams.value)
    tableData.value = response.funds
    total.value = response.total
  } catch (error) {
    ElMessage.error('筛选失败，请重试')
    console.error(error)
  } finally {
    loading.value = false
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

// 保存筛选配置到localStorage
const saveFilterConfig = () => {
  localStorage.setItem('fundFilterConfig', JSON.stringify(filterParams.value))
  ElMessage.success('筛选配置已保存')
}

// 加载筛选配置
const loadFilterConfig = () => {
  const saved = localStorage.getItem('fundFilterConfig')
  if (saved) {
    filterParams.value = JSON.parse(saved)
    handleFilter()
    ElMessage.success('筛选配置已加载')
  }
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

onMounted(() => {
  handleFilter()
})
</script>

<template>
  <div class="fund-filter">
    <div class="filter-container" :class="{ collapsed: leftPanelCollapsed }">
      <!-- 左侧筛选面板 -->
      <div class="filter-panel">
        <div class="panel-header">
          <h3>筛选条件</h3>
          <button class="collapse-btn" @click="leftPanelCollapsed = !leftPanelCollapsed">
            {{ leftPanelCollapsed ? '展开' : '收起' }}
          </button>
        </div>
        
        <div v-if="!leftPanelCollapsed" class="filter-form">
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
                />
                <span>-</span>
                <el-input-number
                  v-model="filterParams.setup_year_max"
                  :min="0"
                  :max="20"
                  placeholder="最大"
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
                />
                <span>-</span>
                <el-input-number
                  v-model="filterParams.scale_max"
                  :min="0"
                  placeholder="最大"
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
                />
                <span>-</span>
                <el-input-number
                  v-model="filterParams.return_1y_max"
                  placeholder="最大"
                />
              </div>
            </div>
            
            <div class="form-item">
              <label>最大回撤 ≤ (%)</label>
              <el-input-number
                v-model="filterParams.max_drawdown_1y_max"
                :min="0"
                :max="100"
              />
            </div>
            
            <div class="form-item">
              <label>夏普比率 ≥</label>
              <el-input-number
                v-model="filterParams.sharpe_1y_min"
                :step="0.1"
              />
            </div>
          </div>
          
          <!-- 操作按钮 -->
          <div class="filter-actions">
            <el-button type="primary" @click="handleFilter">
              筛选
            </el-button>
            <el-button @click="handleReset">
              重置
            </el-button>
            <el-button @click="saveFilterConfig">
              保存配置
            </el-button>
            <el-button @click="loadFilterConfig">
              加载配置
            </el-button>
          </div>
        </div>
      </div>
      
      <!-- 右侧结果表格 -->
      <div class="result-panel">
        <div class="panel-header">
          <h3>筛选结果 ({{ total }} 只)</h3>
        </div>
        
        <el-table
          :data="tableData"
          :loading="loading"
          stripe
          height="calc(100vh - 200px)"
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
            min-width="180"
            fixed
          />
          <el-table-column
            prop="fund_type"
            label="类型"
            width="100"
          />
          <el-table-column
            prop="manager"
            label="经理"
            width="100"
          />
          <el-table-column
            prop="scale"
            label="规模(亿)"
            width="100"
          >
            <template #default="{ row }">
              {{ formatNumber(row.scale) }}
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
            label="最大回撤%"
            width="110"
            sortable
          >
            <template #default="{ row }">
              <span :class="getValueClass(-row.max_drawdown_1y)">
                {{ formatNumber(row.max_drawdown_1y) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column
            prop="sharpe_1y"
            label="夏普"
            width="80"
            sortable
          >
            <template #default="{ row }">
              {{ formatNumber(row.sharpe_1y) }}
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
    </div>
  </div>
</template>

<style scoped>
.fund-filter {
  height: calc(100vh - 100px);
}

.filter-container {
  display: flex;
  gap: 16px;
  height: 100%;
}

.filter-container.collapsed .filter-panel {
  width: 60px;
}

.filter-panel {
  width: 320px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  overflow-y: auto;
  transition: width 0.3s;
}

.result-panel {
  flex: 1;
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
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-line);
}

.panel-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.collapse-btn {
  padding: 4px 12px;
  font-size: 12px;
  background: #f0f0f0;
  border: none;
  border-radius: 4px;
  cursor: pointer;
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

.filter-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}
</style>
