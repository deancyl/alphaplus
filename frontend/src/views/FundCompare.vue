<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { filterFunds, compareFunds, type FundFilterParams, type FundItem } from '@/api/fund'
import SkeletonLoader from '@/components/SkeletonLoader.vue'

// Types
interface CompareFund extends FundItem {
  selected: boolean
}

interface RadarData {
  name: string
  value: number[]
}

interface CorrelationStats {
  average: number
  highestPair: { i: number; j: number; value: number }
  lowestPair: { i: number; j: number; value: number }
  sampleSize: number
  calculationDate: string
}

// State
const searchQuery = ref('')
const searchResults = ref<CompareFund[]>([])
const selectedFunds = ref<CompareFund[]>([])
const loading = ref(false)
const compareLoading = ref(false)
const correlationMatrix = ref<number[][]>([])
const radarData = ref<RadarData[]>([])
const correlationStats = ref<CorrelationStats | null>(null)

// Drag and drop state
const draggedIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)

// Debounce timer
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

// Chart refs
const correlationChartRef = ref<HTMLElement | null>(null)
const radarChartRef = ref<HTMLElement | null>(null)
let correlationChart: echarts.ECharts | null = null
let radarChart: echarts.ECharts | null = null

// Scroll detection refs
const tableContainer = ref<HTMLElement | null>(null)
const canScrollLeft = ref(false)
const canScrollRight = ref(false)

// Constants
const MAX_COMPARE = 15
const DEBOUNCE_DELAY = 300
const RADAR_INDICATORS = [
  { name: '收益能力', max: 100 },
  { name: '稳定性', max: 100 },
  { name: '抗风险', max: 100 },
  { name: '夏普比率', max: 100 },
  { name: '规模', max: 100 },
  { name: '成立年限', max: 100 },
]

// Computed
const canAddMore = computed(() => selectedFunds.value.length < MAX_COMPARE)
const hasSelection = computed(() => selectedFunds.value.length > 0)
const hasEnoughForCorrelation = computed(() => selectedFunds.value.length >= 2)
const isAtLimit = computed(() => selectedFunds.value.length >= MAX_COMPARE)

// Debounced search funds
const debouncedSearch = () => {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  
  searchDebounceTimer = setTimeout(() => {
    handleSearch()
  }, DEBOUNCE_DELAY)
}

// Search funds
const handleSearch = async () => {
  if (!searchQuery.value.trim()) {
    searchResults.value = []
    return
  }

  loading.value = true
  try {
    const params: FundFilterParams = {
      page: 1,
      page_size: 50,
    }
    
    const response = await filterFunds(params)
    
    // Filter results by search query
    const query = searchQuery.value.trim().toLowerCase()
    searchResults.value = response.funds
      .filter(f => 
        f.fund_code.toLowerCase().includes(query) || 
        f.fund_name.toLowerCase().includes(query)
      )
      .slice(0, 20)
      .map(f => ({
        ...f,
        selected: selectedFunds.value.some(s => s.fund_code === f.fund_code)
      }))
  } catch (error) {
    ElMessage.error('搜索失败，请重试')
  } finally {
    loading.value = false
  }
}

// Add fund to comparison
const addToComparison = (fund: CompareFund) => {
  if (!canAddMore.value) {
    ElMessage.warning(`最多只能对比 ${MAX_COMPARE} 只基金，请先移除部分基金`)
    return
  }
  
  if (selectedFunds.value.some(f => f.fund_code === fund.fund_code)) {
    ElMessage.info('该基金已在对比列表中')
    return
  }
  
  selectedFunds.value.push({ ...fund, selected: true })
  fund.selected = true
  ElMessage.success(`已添加 ${fund.fund_name}`)
}

// Remove fund from comparison
const removeFromComparison = (fundCode: string) => {
  const index = selectedFunds.value.findIndex(f => f.fund_code === fundCode)
  if (index > -1) {
    const fund = selectedFunds.value[index]
    selectedFunds.value.splice(index, 1)
    
    // Update search result
    const searchFund = searchResults.value.find(f => f.fund_code === fundCode)
    if (searchFund) {
      searchFund.selected = false
    }
    
    ElMessage.info(`已移除 ${fund.fund_name}`)
  }
}

// Clear all selected funds
const clearSelection = () => {
  selectedFunds.value = []
  searchResults.value.forEach(f => f.selected = false)
  correlationMatrix.value = []
  radarData.value = []
  correlationStats.value = null
  ElMessage.info('已清空对比列表')
}

// Calculate correlation statistics
const calculateCorrelationStats = (): CorrelationStats | null => {
  if (!correlationMatrix.value.length || correlationMatrix.value.length < 2) {
    return null
  }
  
  const n = correlationMatrix.value.length
  let sum = 0
  let count = 0
  let highest = { i: 0, j: 1, value: -Infinity }
  let lowest = { i: 0, j: 1, value: Infinity }
  
  // Only consider upper triangle (excluding diagonal)
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const value = correlationMatrix.value[i][j]
      sum += value
      count++
      
      if (value > highest.value) {
        highest = { i, j, value }
      }
      if (value < lowest.value) {
        lowest = { i, j, value }
      }
    }
  }
  
  return {
    average: count > 0 ? sum / count : 0,
    highestPair: highest,
    lowestPair: lowest,
    sampleSize: count,
    calculationDate: new Date().toLocaleDateString('zh-CN')
  }
}

// Fetch comparison data
const fetchComparisonData = async () => {
  if (!hasEnoughForCorrelation.value) {
    correlationMatrix.value = []
    radarData.value = []
    correlationStats.value = null
    return
  }
  
  compareLoading.value = true
  try {
    const fundCodes = selectedFunds.value.map(f => f.fund_code)
    const response = await compareFunds(fundCodes)
    correlationMatrix.value = response.correlation_matrix
    
    // Calculate statistics
    correlationStats.value = calculateCorrelationStats()
    
    // Generate radar data
    radarData.value = selectedFunds.value.map(fund => ({
      name: fund.fund_name.length > 8 ? fund.fund_name.slice(0, 8) + '...' : fund.fund_name,
      value: normalizeRadarValues(fund)
    }))
    
    await nextTick()
    renderCharts()
  } catch (error) {
    ElMessage.error('获取对比数据失败')
  } finally {
    compareLoading.value = false
  }
}

// Normalize fund values for radar chart (0-100 scale)
const normalizeRadarValues = (fund: FundItem): number[] => {
  const maxReturn = 100
  const maxVolatility = 50
  const maxDrawdown = 50
  const maxSharpe = 5
  const maxScale = 500
  const maxYear = 20

  return [
    // 收益能力 (higher is better)
    Math.min(100, Math.max(0, ((fund.return_1y || 0) / maxReturn) * 100 + 50)),
    // 稳定性 (lower volatility is better, so invert)
    Math.min(100, Math.max(0, 100 - ((fund.volatility_1y || 25) / maxVolatility) * 100)),
    // 抗风险 (lower drawdown is better, so invert)
    Math.min(100, Math.max(0, 100 - ((fund.max_drawdown_1y || 25) / maxDrawdown) * 100)),
    // 夏普比率
    Math.min(100, Math.max(0, ((fund.sharpe_1y || 0) / maxSharpe) * 100)),
    // 规模
    Math.min(100, Math.max(0, ((fund.scale || 0) / maxScale) * 100)),
    // 成立年限
    Math.min(100, Math.max(0, ((fund.setup_year || 0) / maxYear) * 100)),
  ]
}

// Render correlation heatmap (triangular)
const renderCorrelationChart = () => {
  if (!correlationChartRef.value || !hasEnoughForCorrelation.value) return
  
  if (!correlationChart) {
    correlationChart = echarts.init(correlationChartRef.value)
  }
  
  const fundNames = selectedFunds.value.map(f => 
    f.fund_name.length > 6 ? f.fund_name.slice(0, 6) + '...' : f.fund_name
  )
  
  // Build triangular data (upper triangle including diagonal)
  const heatmapData: number[][] = []
  for (let i = 0; i < correlationMatrix.value.length; i++) {
    for (let j = i; j < correlationMatrix.value[i].length; j++) {
      heatmapData.push([j, i, correlationMatrix.value[i][j]])
    }
  }
  
  const option: echarts.EChartsOption = {
    tooltip: {
      position: 'top',
      formatter: (params: unknown) => {
        const p = params as { data: number[] }
        const [j, i, value] = p.data
        return `${fundNames[i]} vs ${fundNames[j]}<br/>相关系数: ${value.toFixed(3)}`
      }
    },
    grid: {
      top: 40,
      left: 100,
      right: 40,
      bottom: 60
    },
    xAxis: {
      type: 'category',
      data: fundNames,
      axisLabel: {
        rotate: 45,
        fontSize: 11,
        color: 'var(--text-regular)'
      },
      splitArea: { 
        show: true,
        areaStyle: {
          color: ['rgba(0,0,0,0.02)', 'rgba(0,0,0,0.04)']
        }
      },
      axisLine: {
        lineStyle: { color: 'var(--border-line)' }
      }
    },
    yAxis: {
      type: 'category',
      data: fundNames,
      axisLabel: {
        fontSize: 11,
        color: 'var(--text-regular)'
      },
      splitArea: { 
        show: true,
        areaStyle: {
          color: ['rgba(0,0,0,0.02)', 'rgba(0,0,0,0.04)']
        }
      },
      axisLine: {
        lineStyle: { color: 'var(--border-line)' }
      }
    },
    visualMap: {
      min: -1,
      max: 1,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      text: ['高相关', '低相关'],
      textStyle: {
        color: 'var(--text-muted)',
        fontSize: 11
      },
      inRange: {
        color: ['#E63935', '#FFB74D', '#FFE082', '#C5E1A5', '#2E7D32']
      }
    },
    series: [{
      name: '相关系数',
      type: 'heatmap',
      data: heatmapData,
      label: {
        show: true,
        fontSize: 10,
        color: 'var(--text-primary)',
        formatter: (params: unknown) => {
          const p = params as { data: number[] }
          return p.data[2].toFixed(2)
        }
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.3)',
          borderColor: '#333',
          borderWidth: 1
        }
      },
      itemStyle: {
        borderColor: 'var(--border-line)',
        borderWidth: 1
      }
    }]
  }
  
  correlationChart.setOption(option)
}

// Render radar chart
const renderRadarChart = () => {
  if (!radarChartRef.value || !hasSelection.value) return
  
  if (!radarChart) {
    radarChart = echarts.init(radarChartRef.value)
  }
  
  const colors = [
    '#0066cc', '#cc0000', '#00cc00', '#ff9900', '#9933ff',
    '#00cccc', '#cc6600', '#66cc00', '#cc0099', '#006699',
    '#cc3300', '#33cc00', '#9900cc', '#00cc99', '#cc9900'
  ]
  
  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item'
    },
    legend: {
      bottom: 0,
      textStyle: {
        fontSize: 11,
        color: 'var(--text-regular)'
      }
    },
    radar: {
      indicator: RADAR_INDICATORS,
      center: ['50%', '45%'],
      radius: '60%',
      axisName: {
        color: 'var(--text-primary)',
        fontSize: 12
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(0, 102, 204, 0.02)', 'rgba(0, 102, 204, 0.05)']
        }
      },
      axisLine: {
        lineStyle: {
          color: 'var(--border-line)'
        }
      },
      splitLine: {
        lineStyle: {
          color: 'var(--border-line)'
        }
      }
    },
    series: [{
      type: 'radar',
      data: radarData.value.map((item, index) => ({
        value: item.value,
        name: item.name,
        lineStyle: {
          width: 2,
          color: colors[index % colors.length]
        },
        areaStyle: {
          opacity: 0.1,
          color: colors[index % colors.length]
        },
        itemStyle: {
          color: colors[index % colors.length]
        }
      }))
    }]
  }
  
  radarChart.setOption(option)
}

// Render all charts
const renderCharts = () => {
  renderCorrelationChart()
  renderRadarChart()
}

// Format number
const formatNumber = (val: number | null, suffix = ''): string => {
  if (val === null || val === undefined) return '-'
  return `${val.toFixed(2)}${suffix}`
}

// Get value class
const getValueClass = (val: number | null): string => {
  if (val === null) return ''
  return val >= 0 ? 'text-up' : 'text-down'
}

// Drag and drop handlers
const handleDragStart = (index: number) => {
  draggedIndex.value = index
}

const handleDragOver = (e: DragEvent, index: number) => {
  e.preventDefault()
  dragOverIndex.value = index
}

const handleDragEnd = () => {
  if (draggedIndex.value !== null && dragOverIndex.value !== null && draggedIndex.value !== dragOverIndex.value) {
    const items = [...selectedFunds.value]
    const draggedItem = items[draggedIndex.value]
    items.splice(draggedIndex.value, 1)
    items.splice(dragOverIndex.value, 0, draggedItem)
    selectedFunds.value = items
  }
  draggedIndex.value = null
  dragOverIndex.value = null
}

// Watch for selection changes
watch(selectedFunds, () => {
  fetchComparisonData()
}, { deep: true })

// Watch for search query changes
watch(searchQuery, () => {
  debouncedSearch()
})

// Scroll detection logic
const updateScrollIndicators = () => {
  if (!tableContainer.value) return
  const { scrollLeft, scrollWidth, clientWidth } = tableContainer.value
  canScrollLeft.value = scrollLeft > 0
  canScrollRight.value = scrollLeft < scrollWidth - clientWidth - 1
}

// Handle window resize
const handleResize = () => {
  correlationChart?.resize()
  radarChart?.resize()
  updateScrollIndicators()
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  tableContainer.value?.addEventListener('scroll', updateScrollIndicators)
  // Initial check
  nextTick(() => updateScrollIndicators())
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  tableContainer.value?.removeEventListener('scroll', updateScrollIndicators)
  correlationChart?.dispose()
  radarChart?.dispose()
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
})
</script>

<template>
  <div class="fund-compare">
    <div class="compare-container">
      <!-- 左侧搜索面板 -->
      <div class="search-panel">
        <div class="panel-header">
          <h3>基金搜索</h3>
          <span class="hint" :class="{ 'limit-warning': isAtLimit }">
            已选 {{ selectedFunds.length }}/{{ MAX_COMPARE }} 只
          </span>
        </div>
        
        <div class="search-box">
          <el-input
            v-model="searchQuery"
            placeholder="输入基金代码或名称搜索（自动搜索）"
            clearable
            @clear="searchResults = []"
          >
            <template #prefix>
              <el-icon><i-ep-search /></el-icon>
            </template>
          </el-input>
        </div>
        
        <!-- Limit warning -->
        <div v-if="isAtLimit" class="limit-warning-box">
          <el-icon><i-ep-warning-filled /></el-icon>
          <span>已达上限 {{ MAX_COMPARE }} 只，请移除后继续添加</span>
        </div>
        
        <!-- 搜索结果 -->
        <div class="search-results" v-loading="loading">
          <div v-if="searchResults.length === 0" class="empty-hint">
            <p>输入关键词搜索基金</p>
          </div>
          
          <div
            v-for="fund in searchResults"
            :key="fund.fund_code"
            class="result-item"
            :class="{ selected: fund.selected }"
          >
            <div class="fund-info">
              <span class="fund-code">{{ fund.fund_code }}</span>
              <span class="fund-name">{{ fund.fund_name }}</span>
              <span class="fund-type">{{ fund.fund_type }}</span>
            </div>
            <el-button
              v-if="!fund.selected"
              type="primary"
              size="small"
              :disabled="!canAddMore"
              @click="addToComparison(fund)"
            >
              添加
            </el-button>
            <el-button
              v-else
              type="info"
              size="small"
              disabled
            >
              已添加
            </el-button>
          </div>
        </div>
      </div>
      
      <!-- 右侧对比区域 -->
      <div class="compare-area">
        <!-- 已选基金列表 -->
        <div class="selected-panel">
          <div class="panel-header">
            <h3>对比列表 <span class="drag-hint" v-if="hasSelection">(拖拽排序)</span></h3>
            <el-button
              v-if="hasSelection"
              type="danger"
              size="small"
              @click="clearSelection"
            >
              清空
            </el-button>
          </div>
          
          <div v-if="!hasSelection" class="empty-state">
            <p>请从左侧搜索并添加基金进行对比</p>
          </div>
          
          <div v-else class="selected-funds-grid">
            <div
              v-for="(fund, index) in selectedFunds"
              :key="fund.fund_code"
              class="selected-fund-card"
              :class="{ 
                'dragging': draggedIndex === index,
                'drag-over': dragOverIndex === index 
              }"
              draggable="true"
              @dragstart="handleDragStart(index)"
              @dragover="handleDragOver($event, index)"
              @dragend="handleDragEnd"
            >
              <div class="card-header">
                <span class="fund-index">{{ index + 1 }}</span>
                <span class="fund-code">{{ fund.fund_code }}</span>
                <el-button
                  type="danger"
                  size="small"
                  circle
                  class="remove-btn"
                  @click="removeFromComparison(fund.fund_code)"
                >
                  <el-icon><i-ep-close /></el-icon>
                </el-button>
              </div>
              <div class="card-body">
                <div class="fund-name">{{ fund.fund_name }}</div>
                <div class="fund-type">{{ fund.fund_type }}</div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 对比表格 -->
        <div class="compare-table-panel" v-if="hasSelection">
          <div class="panel-header">
            <h3>指标对比</h3>
          </div>
          
          <div class="table-container" ref="tableContainer">
            <!-- Left scroll indicator - gradient mask only -->
            <div 
              v-if="canScrollLeft" 
              class="scroll-indicator scroll-indicator-left"
              aria-hidden="true"
            />
            
            <!-- Skeleton table when loading -->
            <SkeletonLoader 
              v-if="compareLoading && hasSelection" 
              variant="table" 
              :rows="selectedFunds.length || 5" 
              :columns="7"
            />
            
            <!-- Actual table when loaded -->
            <el-table
              v-else-if="hasSelection"
              :data="selectedFunds"
              stripe
              border
              size="small"
              max-height="300"
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
                min-width="150"
                fixed="left"
                class-name="sticky-column"
                show-overflow-tooltip
              >
                <template #default="{ row }">
                  <span class="font-medium">{{ row.fund_name }}</span>
                </template>
              </el-table-column>
              <el-table-column
                prop="fund_type"
                label="类型"
                width="90"
                class-name="table-cell"
              />
              <el-table-column
                prop="scale"
                label="规模(亿)"
                width="100"
                class-name="hidden sm:table-cell"
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
                class-name="hidden sm:table-cell md:table-cell"
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
                class-name="hidden md:table-cell lg:table-cell"
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
                class-name="hidden lg:table-cell xl:table-cell"
              >
                <template #default="{ row }">
                  {{ formatNumber(row.sharpe_1y) }}
                </template>
              </el-table-column>
              <el-table-column
                prop="volatility_1y"
                label="波动率%"
                width="100"
                sortable
                class-name="hidden xl:table-cell"
              >
                <template #default="{ row }">
                  {{ formatNumber(row.volatility_1y) }}
                </template>
              </el-table-column>
</el-table>
            
            <!-- Right scroll indicator - gradient mask only -->
            <div 
              v-if="canScrollRight" 
              class="scroll-indicator scroll-indicator-right"
              aria-hidden="true"
            />
          </div>
        </div>
        
        <!-- 图表区域 -->
        <div class="charts-area" v-if="hasSelection">
          <!-- 相关性矩阵 -->
          <div class="chart-panel correlation-panel" v-if="hasEnoughForCorrelation">
            <div class="panel-header">
              <h3>相关性矩阵（Pearson系数）</h3>
            </div>
            
            <!-- Correlation Statistics -->
            <div v-if="correlationStats" class="correlation-stats">
              <div class="stat-item">
                <span class="stat-label">平均相关系数</span>
                <span class="stat-value" :class="correlationStats.average >= 0 ? 'positive' : 'negative'">
                  {{ correlationStats.average.toFixed(3) }}
                </span>
              </div>
              <div class="stat-item">
                <span class="stat-label">最高相关</span>
                <span class="stat-value positive">
                  {{ selectedFunds[correlationStats.highestPair.i]?.fund_name?.slice(0, 4) }} ↔ 
                  {{ selectedFunds[correlationStats.highestPair.j]?.fund_name?.slice(0, 4) }}:
                  {{ correlationStats.highestPair.value.toFixed(3) }}
                </span>
              </div>
              <div class="stat-item">
                <span class="stat-label">最低相关</span>
                <span class="stat-value negative">
                  {{ selectedFunds[correlationStats.lowestPair.i]?.fund_name?.slice(0, 4) }} ↔ 
                  {{ selectedFunds[correlationStats.lowestPair.j]?.fund_name?.slice(0, 4) }}:
                  {{ correlationStats.lowestPair.value.toFixed(3) }}
                </span>
              </div>
              <div class="stat-item">
                <span class="stat-label">样本数</span>
                <span class="stat-value">{{ correlationStats.sampleSize }} 对</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">计算日期</span>
                <span class="stat-value">{{ correlationStats.calculationDate }}</span>
              </div>
            </div>
            
            <!-- Skeleton when loading -->
            <SkeletonLoader 
              v-if="compareLoading" 
              variant="heatmap" 
              height="320px"
            />
            
            <!-- Actual chart when loaded -->
            <div
              v-else
              ref="correlationChartRef"
              class="chart-container correlation-chart"
            />
          </div>
          
          <!-- 雷达图 -->
          <div class="chart-panel">
            <div class="panel-header">
              <h3>多因子雷达图</h3>
            </div>
            <!-- Skeleton when loading -->
            <SkeletonLoader 
              v-if="compareLoading" 
              variant="gauge" 
              height="280px"
            />
            
            <!-- Actual chart when loaded -->
            <div
              v-else
              ref="radarChartRef"
              class="chart-container"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fund-compare {
  height: calc(100vh - 100px); /* Fallback for older browsers */
  height: calc(100dvh - 100px);
}

.compare-container {
  display: flex;
  gap: var(--spacing-md);
  height: 100%;
}

/* 左侧搜索面板 */
.search-panel {
  width: 360px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-radius: 4px;
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
}

.search-box {
  margin-bottom: var(--spacing-md);
}

.limit-warning-box {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-md);
  background: rgba(230, 57, 53, 0.08);
  border-radius: 4px;
  margin-bottom: var(--spacing-md);
  color: var(--market-up);
  font-size: 12px;
}

.search-results {
  flex: 1;
  overflow-y: auto;
}

.empty-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-muted);
  font-size: 13px;
}

.result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-bottom: 1px solid var(--border-line);
  transition: background-color 0.2s;
}

.result-item:hover {
  background-color: #f5f7fa;
}

.result-item.selected {
  background-color: rgba(0, 102, 204, 0.05);
}

.fund-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.fund-code {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.fund-name {
  font-size: 12px;
  color: var(--text-regular);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fund-type {
  font-size: 11px;
  color: var(--text-muted);
}

/* 右侧对比区域 */
.compare-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  overflow-y: auto;
}

.selected-panel {
  background: var(--bg-card);
  border-radius: 4px;
  padding: var(--spacing-md);
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 60px;
  color: var(--text-muted);
  font-size: 13px;
}

.selected-funds-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: var(--spacing-sm);
}

.selected-fund-card {
  background: var(--bg-system);
  border: 1px solid var(--border-line);
  border-radius: 6px;
  padding: var(--spacing-sm);
  cursor: grab;
  transition: all 0.2s ease;
  position: relative;
}

.selected-fund-card:hover {
  border-color: var(--brand-navy-active);
  box-shadow: 0 2px 8px rgba(0, 51, 153, 0.1);
}

.selected-fund-card.dragging {
  opacity: 0.5;
  transform: scale(0.95);
}

.selected-fund-card.drag-over {
  border-color: var(--brand-navy-active);
  border-style: dashed;
  background: rgba(0, 102, 204, 0.05);
}

.card-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-xs);
}

.fund-index {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: var(--brand-navy-dark);
  color: white;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 600;
}

.card-header .fund-code {
  flex: 1;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.remove-btn {
  padding: 10px;
  min-height: 44px;
  min-width: 44px;
  touch-action: manipulation;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.card-body .fund-name {
  font-size: 12px;
  color: var(--text-regular);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-body .fund-type {
  font-size: 11px;
  color: var(--text-muted);
}

.compare-table-panel {
  background: var(--bg-card);
  border-radius: 4px;
  padding: var(--spacing-md);
}

.charts-area {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
}

.chart-panel {
  background: var(--bg-card);
  border-radius: 4px;
  padding: var(--spacing-md);
  min-height: 350px;
}

.correlation-panel {
  min-height: 450px;
}

.correlation-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--bg-system);
  border-radius: 4px;
  margin-bottom: var(--spacing-md);
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-label {
  font-size: 11px;
  color: var(--text-muted);
}

.stat-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-value.positive {
  color: var(--market-up);
}

.stat-value.negative {
  color: var(--market-down);
}

.chart-container {
  width: 100%;
  height: 280px;
}

.correlation-chart {
  height: 320px;
}

/* 通用面板头部 */
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-line);
}

.panel-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.drag-hint {
  font-size: 12px;
  font-weight: normal;
  color: var(--text-muted);
  margin-left: var(--spacing-xs);
}

.hint {
  font-size: 12px;
  color: var(--text-muted);
}

.hint.limit-warning {
  color: var(--market-up);
  font-weight: 600;
}

/* 响应式 */
@media (max-width: 1200px) {
  .charts-area {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .compare-container {
    flex-direction: column;
  }
  
  .search-panel {
    width: 100%;
    max-height: 300px;
  }
  
  .selected-funds-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  }
}

/* Sticky left column for mobile horizontal scroll with progressive shadow */
.el-table .sticky-column {
  position: sticky !important;
  left: 0 !important;
  z-index: var(--z-sticky) !important;
  background: var(--bg-card) !important;
}

/* Progressive shadow + gradient mask on sticky column edge */
.el-table .sticky-column::before {
  content: '';
  position: absolute;
  right: -4px;
  top: 0;
  height: 100%;
  width: 20px;
  background: linear-gradient(to left, transparent 0%, var(--bg-card) 100%);
  pointer-events: none;
  z-index: calc(var(--z-sticky) - 1);
}

/* Shadow effect on sticky column */
.el-table .sticky-column::after {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  height: 100%;
  width: 8px;
  background: transparent;
  box-shadow: 4px 0 12px rgba(0, 0, 0, 0.15);
  pointer-events: none;
}

/* For dark mode */
:root.dark .el-table .sticky-column {
  background: var(--bg-card) !important;
}

:root.dark .el-table .sticky-column::before {
  background: linear-gradient(to left, transparent 0%, var(--bg-card) 100%);
}

:root.dark .el-table .sticky-column::after {
  box-shadow: 4px 0 12px rgba(0, 0, 0, 0.4);
}

/* Second column also sticky if needed */
.el-table .sticky-column-second {
  position: sticky;
  left: 150px;
  z-index: calc(var(--z-sticky) - 1);
  background: var(--bg-card);
  box-shadow: 4px 0 10px rgba(0, 0, 0, 0.08);
}

/* Table container with scroll detection */
.table-container {
  position: relative;
  overflow-x: auto;
  overscroll-behavior-x: contain;
  scroll-snap-type: x proximity;
}

/* Scroll indicators with gradient masks */
.scroll-indicator {
  position: absolute;
  top: 0;
  height: 100%;
  z-index: var(--z-sticky);
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.scroll-indicator-left {
  left: 0;
  width: 48px;
  background: linear-gradient(to right, var(--bg-card) 0%, var(--bg-card) 20%, transparent 100%);
}

.scroll-indicator-right {
  right: 0;
  width: 48px;
  background: linear-gradient(to left, var(--bg-card) 0%, var(--bg-card) 20%, transparent 100%);
}

/* Dark mode scroll indicators */
:root.dark .scroll-indicator-left {
  background: linear-gradient(to right, var(--bg-card) 0%, var(--bg-card) 20%, transparent 100%);
}

:root.dark .scroll-indicator-right {
  background: linear-gradient(to left, var(--bg-card) 0%, var(--bg-card) 20%, transparent 100%);
}
</style>
