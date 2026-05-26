<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { filterFunds, compareFunds, type FundFilterParams, type FundItem } from '@/api/fund'

// Types
interface CompareFund extends FundItem {
  selected: boolean
}

interface RadarData {
  name: string
  value: number[]
}

// State
const searchQuery = ref('')
const searchResults = ref<CompareFund[]>([])
const selectedFunds = ref<CompareFund[]>([])
const loading = ref(false)
const compareLoading = ref(false)
const correlationMatrix = ref<number[][]>([])
const radarData = ref<RadarData[]>([])

// Chart refs
const correlationChartRef = ref<HTMLElement | null>(null)
const radarChartRef = ref<HTMLElement | null>(null)
let correlationChart: echarts.ECharts | null = null
let radarChart: echarts.ECharts | null = null

// Constants
const MAX_COMPARE = 15
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
    console.error(error)
  } finally {
    loading.value = false
  }
}

// Add fund to comparison
const addToComparison = (fund: CompareFund) => {
  if (!canAddMore.value) {
    ElMessage.warning(`最多只能对比 ${MAX_COMPARE} 只基金`)
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
  ElMessage.info('已清空对比列表')
}

// Fetch comparison data
const fetchComparisonData = async () => {
  if (!hasEnoughForCorrelation.value) {
    correlationMatrix.value = []
    radarData.value = []
    return
  }
  
  compareLoading.value = true
  try {
    const fundCodes = selectedFunds.value.map(f => f.fund_code)
    const response = await compareFunds(fundCodes)
    correlationMatrix.value = response.correlation_matrix
    
    // Generate radar data
    radarData.value = selectedFunds.value.map(fund => ({
      name: fund.fund_name.length > 8 ? fund.fund_name.slice(0, 8) + '...' : fund.fund_name,
      value: normalizeRadarValues(fund)
    }))
    
    await nextTick()
    renderCharts()
  } catch (error) {
    ElMessage.error('获取对比数据失败')
    console.error(error)
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

// Render correlation heatmap
const renderCorrelationChart = () => {
  if (!correlationChartRef.value || !hasEnoughForCorrelation.value) return
  
  if (!correlationChart) {
    correlationChart = echarts.init(correlationChartRef.value)
  }
  
  const fundNames = selectedFunds.value.map(f => 
    f.fund_name.length > 6 ? f.fund_name.slice(0, 6) + '...' : f.fund_name
  )
  
  const option: echarts.EChartsOption = {
    tooltip: {
      position: 'top',
      formatter: (params: unknown) => {
        const p = params as { data: number[] }
        const [i, j, value] = p.data
        return `${fundNames[i]} vs ${fundNames[j]}<br/>相关系数: ${value.toFixed(2)}`
      }
    },
    grid: {
      top: 40,
      left: 80,
      right: 20,
      bottom: 60
    },
    xAxis: {
      type: 'category',
      data: fundNames,
      axisLabel: {
        rotate: 45,
        fontSize: 11,
        color: '#4A4A4A'
      },
      splitArea: { show: true }
    },
    yAxis: {
      type: 'category',
      data: fundNames,
      axisLabel: {
        fontSize: 11,
        color: '#4A4A4A'
      },
      splitArea: { show: true }
    },
    visualMap: {
      min: 0,
      max: 1,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: {
        color: ['#E6F7FF', '#1890FF', '#0050B3']
      }
    },
    series: [{
      name: '相关系数',
      type: 'heatmap',
      data: correlationMatrix.value.flatMap((row, i) => 
        row.map((value, j) => [i, j, value])
      ),
      label: {
        show: true,
        fontSize: 10,
        formatter: (params: unknown) => {
          const p = params as { data: number[] }
          return p.data[2].toFixed(2)
        }
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
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
        color: '#4A4A4A'
      }
    },
    radar: {
      indicator: RADAR_INDICATORS,
      center: ['50%', '45%'],
      radius: '60%',
      axisName: {
        color: '#1A1A1A',
        fontSize: 12
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(0, 102, 204, 0.02)', 'rgba(0, 102, 204, 0.05)']
        }
      },
      axisLine: {
        lineStyle: {
          color: '#E5E8ED'
        }
      },
      splitLine: {
        lineStyle: {
          color: '#E5E8ED'
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

// Watch for selection changes
watch(selectedFunds, () => {
  fetchComparisonData()
}, { deep: true })

// Handle window resize
const handleResize = () => {
  correlationChart?.resize()
  radarChart?.resize()
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  correlationChart?.dispose()
  radarChart?.dispose()
})
</script>

<template>
  <div class="fund-compare">
    <div class="compare-container">
      <!-- 左侧搜索面板 -->
      <div class="search-panel">
        <div class="panel-header">
          <h3>基金搜索</h3>
          <span class="hint">已选 {{ selectedFunds.length }}/{{ MAX_COMPARE }} 只</span>
        </div>
        
        <div class="search-box">
          <el-input
            v-model="searchQuery"
            placeholder="输入基金代码或名称搜索"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #append>
              <el-button @click="handleSearch" :loading="loading">
                搜索
              </el-button>
            </template>
          </el-input>
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
            <h3>对比列表</h3>
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
          
          <div v-else class="selected-tags">
            <el-tag
              v-for="fund in selectedFunds"
              :key="fund.fund_code"
              closable
              type="primary"
              @close="removeFromComparison(fund.fund_code)"
            >
              {{ fund.fund_code }} {{ fund.fund_name.slice(0, 6) }}
            </el-tag>
          </div>
        </div>
        
        <!-- 对比表格 -->
        <div class="compare-table-panel" v-if="hasSelection">
          <div class="panel-header">
            <h3>指标对比</h3>
          </div>
          
          <el-table
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
              show-overflow-tooltip
            />
            <el-table-column
              prop="fund_type"
              label="类型"
              width="90"
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
            <el-table-column
              prop="volatility_1y"
              label="波动率%"
              width="100"
              sortable
            >
              <template #default="{ row }">
                {{ formatNumber(row.volatility_1y) }}
              </template>
            </el-table-column>
          </el-table>
        </div>
        
        <!-- 图表区域 -->
        <div class="charts-area" v-if="hasSelection">
          <!-- 相关性矩阵 -->
          <div class="chart-panel" v-if="hasEnoughForCorrelation">
            <div class="panel-header">
              <h3>相关性矩阵</h3>
            </div>
            <div
              ref="correlationChartRef"
              class="chart-container"
              v-loading="compareLoading"
            />
          </div>
          
          <!-- 雷达图 -->
          <div class="chart-panel">
            <div class="panel-header">
              <h3>多因子雷达图</h3>
            </div>
            <div
              ref="radarChartRef"
              class="chart-container"
              v-loading="compareLoading"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fund-compare {
  height: calc(100vh - 100px);
}

.compare-container {
  display: flex;
  gap: 16px;
  height: 100%;
}

/* 左侧搜索面板 */
.search-panel {
  width: 360px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.search-box {
  margin-bottom: 16px;
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
  gap: 16px;
  overflow-y: auto;
}

.selected-panel {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 60px;
  color: var(--text-muted);
  font-size: 13px;
}

.selected-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.compare-table-panel {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
}

.charts-area {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.chart-panel {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  min-height: 350px;
}

.chart-container {
  width: 100%;
  height: 280px;
}

/* 通用面板头部 */
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

.hint {
  font-size: 12px;
  color: var(--text-muted);
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
}
</style>