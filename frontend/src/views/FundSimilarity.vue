<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import type { EChartsOption } from 'echarts'
import api from '@/api/index'

// Types
interface SimilarFund {
  fund_code: string
  fund_name: string
  similarity_score: number
  fund_type: string
  company_name: string
}

interface FundSearchResult {
  fund_code: string
  fund_name: string
  fund_type: string
  company_name: string
}

// State
const sourceFundCode = ref<string>('')
const sourceFundName = ref<string>('')
const searchQuery = ref<string>('')
const searchResults = ref<FundSearchResult[]>([])
const searchLoading = ref(false)
const showSearchDropdown = ref(false)

const algorithmType = ref<string>('holdings')
const minSimilarity = ref<number>(50)
const topN = ref<number>(10)

const similarFunds = ref<SimilarFund[]>([])
const loading = ref(false)
const hasSearched = ref(false)

// Algorithm options
const algorithmOptions = [
  { value: 'holdings', label: '持仓相似度' },
  { value: 'style', label: '风格相似度' },
  { value: 'performance', label: '收益相似度' },
]

// Search funds
const handleSearch = async () => {
  if (!searchQuery.value || searchQuery.value.length < 2) {
    searchResults.value = []
    return
  }

  searchLoading.value = true
  try {
    const response = await api.get('/fund/search', {
      params: { keyword: searchQuery.value, limit: 20 }
    }) as unknown as FundSearchResult[]
    searchResults.value = response || []
    showSearchDropdown.value = searchResults.value.length > 0
  } catch (error) {
    console.error('Search failed:', error)
    searchResults.value = []
  } finally {
    searchLoading.value = false
  }
}

// Select fund
const selectFund = (fund: FundSearchResult) => {
  sourceFundCode.value = fund.fund_code
  sourceFundName.value = fund.fund_name
  searchQuery.value = fund.fund_name
  showSearchDropdown.value = false
  searchResults.value = []
}

// Clear selection
const clearSelection = () => {
  sourceFundCode.value = ''
  sourceFundName.value = ''
  searchQuery.value = ''
  similarFunds.value = []
  hasSearched.value = false
}

// Calculate similarity
const calculateSimilarity = async () => {
  if (!sourceFundCode.value) {
    ElMessage.warning('请先选择一只基金')
    return
  }

  loading.value = true
  hasSearched.value = true
  try {
    const response = await api.post('/fund/similarity', {
      source_fund_code: sourceFundCode.value,
      algorithm: algorithmType.value,
      min_similarity: minSimilarity.value / 100,
      top_n: topN.value,
    }) as unknown as { similar_funds: SimilarFund[] }
    similarFunds.value = response.similar_funds || []
    
    if (similarFunds.value.length === 0) {
      ElMessage.info('未找到符合条件的相似基金')
    }
  } catch (error) {
    ElMessage.error('相似度计算失败，请重试')
    console.error(error)
    similarFunds.value = []
  } finally {
    loading.value = false
  }
}

// Format similarity score
const formatScore = (score: number): string => {
  return `${(score * 100).toFixed(1)}%`
}

// Get score color based on value
const getScoreColor = (score: number): string => {
  const pct = score * 100
  if (pct >= 80) return '#E63935'
  if (pct >= 60) return '#003399'
  if (pct >= 40) return '#FFB347'
  return '#999999'
}

// ECharts gauge option for similarity visualization
const gaugeOption = computed<EChartsOption>(() => {
  const data = similarFunds.value.slice(0, 5).map((fund) => ({
    value: Math.round(fund.similarity_score * 100),
    name: fund.fund_name.length > 8 
      ? fund.fund_name.substring(0, 8) + '...' 
      : fund.fund_name,
    itemStyle: { color: getScoreColor(fund.similarity_score) },
  }))

  return {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}%',
    },
    series: [{
      type: 'gauge',
      startAngle: 180,
      endAngle: 0,
      min: 0,
      max: 100,
      splitNumber: 5,
      radius: '100%',
      center: ['50%', '70%'],
      itemStyle: {
        color: '#003399',
      },
      progress: {
        show: true,
        width: 12,
      },
      axisLine: {
        lineStyle: {
          width: 12,
          color: [[1, '#E5E8ED']],
        },
      },
      axisTick: { show: false },
      splitLine: {
        length: 10,
        lineStyle: { width: 2, color: '#999' },
      },
      axisLabel: {
        distance: 15,
        fontSize: 11,
        color: '#4A4A4A',
      },
      pointer: {
        length: '60%',
        width: 5,
      },
      detail: {
        valueAnimation: true,
        fontSize: 18,
        offsetCenter: [0, '40%'],
        formatter: '{value}%',
        color: '#1A1A1A',
      },
      data: data.length > 0 ? [data[0]] : [{ value: 0, name: '相似度' }],
    }],
  }
})

// Bar chart option for all similar funds
const barOption = computed<EChartsOption>(() => {
  const funds = similarFunds.value.slice(0, 10)
  
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: unknown) => {
        const data = params as Array<{ name: string; value: number; color: string }>
        if (!data || data.length === 0) return ''
        const item = data[0]
        return `${item.name}<br/>相似度: <strong style="color:${item.color}">${item.value}%</strong>`
      },
    },
    grid: {
      top: 20,
      left: 120,
      right: 30,
      bottom: 20,
    },
    xAxis: {
      type: 'value',
      max: 100,
      axisLabel: { formatter: '{value}%', color: '#4A4A4A' },
      splitLine: { lineStyle: { color: '#E5E8ED' } },
    },
    yAxis: {
      type: 'category',
      data: funds.map(f => f.fund_name.length > 12 
        ? f.fund_name.substring(0, 12) + '...' 
        : f.fund_name).reverse(),
      axisLabel: { color: '#4A4A4A', fontSize: 12 },
      axisLine: { lineStyle: { color: '#E5E8ED' } },
    },
    series: [{
      type: 'bar',
      data: funds.map(f => ({
        value: Math.round(f.similarity_score * 100),
        itemStyle: {
          color: getScoreColor(f.similarity_score),
          borderRadius: [0, 4, 4, 0],
        },
      })).reverse(),
      barWidth: 16,
      label: {
        show: true,
        position: 'right',
        formatter: '{c}%',
        fontSize: 11,
        color: '#4A4A4A',
      },
    }],
  }
})

// Debounce search
let searchTimeout: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, () => {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    handleSearch()
  }, 300)
})

// Close dropdown on outside click
const handleClickOutside = (event: MouseEvent) => {
  const target = event.target as HTMLElement
  if (!target.closest('.search-container')) {
    showSearchDropdown.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})
</script>

<template>
  <div class="fund-similarity">
    <div class="page-header">
      <h1 class="page-title">相似度计算器</h1>
      <p class="page-desc">基于机器学习回归的配置解构引擎</p>
    </div>

    <div class="main-container">
      <!-- Left Panel: Controls -->
      <div class="control-panel">
        <div class="panel-section">
          <h3 class="section-title">源基金选择</h3>
          
          <div class="search-container">
            <el-input
              v-model="searchQuery"
              placeholder="输入基金代码或名称搜索"
              :prefix-icon="searchLoading ? 'Loading' : 'Search'"
              clearable
              @clear="clearSelection"
              @focus="showSearchDropdown = searchResults.length > 0"
            />
            
            <!-- Search Dropdown -->
            <div v-if="showSearchDropdown && searchResults.length > 0" class="search-dropdown">
              <div
                v-for="fund in searchResults"
                :key="fund.fund_code"
                class="search-item"
                @click="selectFund(fund)"
              >
                <span class="fund-code">{{ fund.fund_code }}</span>
                <span class="fund-name">{{ fund.fund_name }}</span>
                <span class="fund-type">{{ fund.fund_type }}</span>
              </div>
            </div>
          </div>

          <div v-if="sourceFundCode" class="selected-fund">
            <div class="selected-label">已选择:</div>
            <div class="selected-info">
              <span class="code">{{ sourceFundCode }}</span>
              <span class="name">{{ sourceFundName }}</span>
            </div>
          </div>
        </div>

        <div class="panel-section">
          <h3 class="section-title">算法配置</h3>
          
          <div class="form-item">
            <label>相似度算法</label>
            <el-radio-group v-model="algorithmType">
              <el-radio-button
                v-for="opt in algorithmOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </el-radio-button>
            </el-radio-group>
          </div>

          <div class="form-item">
            <label>最低相似度阈值: {{ minSimilarity }}%</label>
            <el-slider
              v-model="minSimilarity"
              :min="0"
              :max="100"
              :step="5"
              show-stops
            />
          </div>

          <div class="form-item">
            <label>返回数量</label>
            <el-input-number
              v-model="topN"
              :min="5"
              :max="20"
              :step="5"
            />
          </div>
        </div>

        <div class="panel-actions">
          <el-button
            type="primary"
            :loading="loading"
            :disabled="!sourceFundCode"
            @click="calculateSimilarity"
          >
            计算相似度
          </el-button>
          <el-button @click="clearSelection">
            清空
          </el-button>
        </div>
      </div>

      <!-- Right Panel: Results -->
      <div class="result-panel">
        <div v-if="!hasSearched" class="empty-state">
          <div class="empty-icon">
            <svg viewBox="0 0 24 24" width="64" height="64" fill="none" stroke="currentColor" stroke-width="1.5">
              <circle cx="11" cy="11" r="8" />
              <path d="M21 21l-4.35-4.35" />
            </svg>
          </div>
          <p>选择一只基金并点击计算，查看相似基金</p>
        </div>

        <template v-else>
          <!-- Visualization Section -->
          <div class="viz-section">
            <div class="viz-card">
              <h4 class="viz-title">Top 1 相似度</h4>
              <EChartsWrapper
                :option="gaugeOption"
                :loading="loading"
                height="280px"
              />
            </div>
            
            <div class="viz-card viz-card-wide">
              <h4 class="viz-title">相似度排名</h4>
              <EChartsWrapper
                :option="barOption"
                :loading="loading"
                height="280px"
              />
            </div>
          </div>

          <!-- Results Table -->
          <div class="table-section">
            <div class="table-header">
              <h4>相似基金列表 ({{ similarFunds.length }} 只)</h4>
            </div>
            
            <el-table
              :data="similarFunds"
              :loading="loading"
              stripe
              max-height="400"
            >
              <el-table-column type="index" label="#" width="50" />
              
              <el-table-column prop="fund_code" label="基金代码" width="100" fixed />
              
              <el-table-column prop="fund_name" label="基金名称" min-width="180">
                <template #default="{ row }">
                  <span class="fund-name-cell">{{ row.fund_name }}</span>
                </template>
              </el-table-column>
              
              <el-table-column prop="similarity_score" label="相似度" width="140" sortable>
                <template #default="{ row }">
                  <div class="score-cell">
                    <el-progress
                      :percentage="Math.round(row.similarity_score * 100)"
                      :stroke-width="8"
                      :color="getScoreColor(row.similarity_score)"
                      :show-text="false"
                    />
                    <span class="score-text">{{ formatScore(row.similarity_score) }}</span>
                  </div>
                </template>
              </el-table-column>
              
              <el-table-column prop="fund_type" label="基金类型" width="100" />
              
              <el-table-column prop="company_name" label="基金公司" min-width="140">
                <template #default="{ row }">
                  <span class="company-cell">{{ row.company_name }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fund-similarity {
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.page-desc {
  font-size: 14px;
  color: var(--text-muted);
}

.main-container {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

/* Control Panel */
.control-panel {
  width: 320px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 20px;
  overflow-y: auto;
}

.panel-section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-line);
}

/* Search */
.search-container {
  position: relative;
}

.search-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: var(--bg-card);
  border: 1px solid var(--border-line);
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  max-height: 240px;
  overflow-y: auto;
  z-index: 100;
  margin-top: 4px;
}

.search-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.search-item:hover {
  background: #f5f7fa;
}

.search-item .fund-code {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 13px;
  color: var(--brand-navy-dark);
  min-width: 70px;
}

.search-item .fund-name {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.search-item .fund-type {
  font-size: 12px;
  color: var(--text-muted);
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 3px;
}

/* Selected Fund */
.selected-fund {
  margin-top: 12px;
  padding: 12px;
  background: rgba(0, 51, 153, 0.05);
  border-radius: 4px;
  border-left: 3px solid var(--brand-navy-dark);
}

.selected-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.selected-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.selected-info .code {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 14px;
  font-weight: 600;
  color: var(--brand-navy-dark);
}

.selected-info .name {
  font-size: 13px;
  color: var(--text-primary);
}

/* Form Items */
.form-item {
  margin-bottom: 16px;
}

.form-item label {
  display: block;
  font-size: 13px;
  color: var(--text-regular);
  margin-bottom: 8px;
}

.panel-actions {
  display: flex;
  gap: 8px;
}

/* Result Panel */
.result-panel {
  flex: 1;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Empty State */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
}

.empty-icon {
  opacity: 0.3;
  margin-bottom: 16px;
}

.empty-state p {
  font-size: 14px;
}

/* Visualization */
.viz-section {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}

.viz-card {
  flex: 1;
  background: #fafafa;
  border-radius: 4px;
  padding: 16px;
}

.viz-card-wide {
  flex: 2;
}

.viz-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

/* Table */
.table-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.table-header {
  margin-bottom: 12px;
}

.table-header h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.score-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.score-cell .el-progress {
  flex: 1;
}

.score-text {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 13px;
  font-weight: 600;
  min-width: 50px;
  text-align: right;
}

.fund-name-cell,
.company-cell {
  font-size: 13px;
  color: var(--text-primary);
}

/* Responsive */
@media (max-width: 1024px) {
  .main-container {
    flex-direction: column;
  }
  
  .control-panel {
    width: 100%;
  }
  
  .viz-section {
    flex-direction: column;
  }
  
  .viz-card,
  .viz-card-wide {
    flex: none;
  }
}
</style>
