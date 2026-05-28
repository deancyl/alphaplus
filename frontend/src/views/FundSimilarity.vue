<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import StyleBox from '@/components/StyleBox.vue'
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

interface FactorExposure {
  fund_code: string
  fund_name: string
  large_cap_growth: number
  large_cap_value: number
  large_cap_blend: number
  mid_cap_growth: number
  mid_cap_value: number
  mid_cap_blend: number
  small_cap_growth: number
  small_cap_value: number
  small_cap_blend: number
  financial_sector: number
  technology_sector: number
  healthcare_sector: number
  consumer_sector: number
  industrial_sector: number
  energy_sector: number
  materials_sector: number
  utilities_sector: number
  calculation_time_ms?: number
}

interface StyleBoxData {
  large_cap_value: number
  large_cap_blend: number
  large_cap_growth: number
  mid_cap_value: number
  mid_cap_blend: number
  mid_cap_growth: number
  small_cap_value: number
  small_cap_blend: number
  small_cap_growth: number
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

// Factor exposure state
const factorExposures = ref<FactorExposure[]>([])
const factorLoading = ref(false)
const factorCalculationTime = ref<number>(0)
const showFactorTable = ref(false)

// Style box state
interface StyleBoxData {
  large_cap_value: number
  large_cap_blend: number
  large_cap_growth: number
  mid_cap_value: number
  mid_cap_blend: number
  mid_cap_growth: number
  small_cap_value: number
  small_cap_blend: number
  small_cap_growth: number
}

const styleBoxData = ref<StyleBoxData | null>(null)
const styleBoxLoading = ref(false)

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
  factorExposures.value = []
  showFactorTable.value = false
  styleBoxData.value = null
}

// Factor column definitions
const factorColumns = [
  { key: 'large_cap_growth', label: '大盘成长' },
  { key: 'large_cap_value', label: '大盘价值' },
  { key: 'mid_cap_growth', label: '中盘成长' },
  { key: 'mid_cap_value', label: '中盘价值' },
  { key: 'small_cap_growth', label: '小盘成长' },
  { key: 'small_cap_value', label: '小盘价值' },
  { key: 'financial_sector', label: '金融' },
  { key: 'technology_sector', label: '科技' },
  { key: 'healthcare_sector', label: '医药' },
  { key: 'consumer_sector', label: '消费' },
  { key: 'industrial_sector', label: '工业' },
  { key: 'energy_sector', label: '能源' },
  { key: 'materials_sector', label: '材料' },
  { key: 'utilities_sector', label: '公用事业' },
]

// Get color for factor weight (green=high, red=low)
const getFactorColor = (weight: number): string => {
  if (weight >= 0.15) return '#22c55e' // Green - high exposure
  if (weight >= 0.10) return '#86efac' // Light green
  if (weight >= 0.05) return '#fef08a' // Yellow
  if (weight >= 0.02) return '#fdba74' // Orange
  return '#f87171' // Red - low exposure
}

// Get background color class for cell
const getFactorBgStyle = (weight: number): string => {
  const alpha = Math.min(weight * 3, 0.4) // Max 40% opacity
  const color = getFactorColor(weight)
  return `background-color: ${color}${Math.round(alpha * 255).toString(16).padStart(2, '0')}`
}

// Fetch factor exposure for a fund
const fetchFactorExposure = async (fundCode: string, fundName: string): Promise<FactorExposure | null> => {
  try {
    const today = new Date()
    const endDate = today.toISOString().split('T')[0]
    const startDate = new Date(today.setFullYear(today.getFullYear() - 1)).toISOString().split('T')[0]
    
    const response = await api.post('/analytics/factor-exposure', null, {
      params: {
        fund_code: fundCode,
        start_date: startDate,
        end_date: endDate,
      }
    }) as unknown as { fund_code: string; exposure: number[] }
    
    const exposure = response.exposure || []
    
    return {
      fund_code: fundCode,
      fund_name: fundName,
      large_cap_growth: exposure[0] || 0,
      large_cap_value: exposure[1] || 0,
      large_cap_blend: exposure[2] || 0,
      mid_cap_growth: exposure[3] || 0,
      mid_cap_value: exposure[4] || 0,
      mid_cap_blend: exposure[5] || 0,
      small_cap_growth: exposure[6] || 0,
      small_cap_value: exposure[7] || 0,
      small_cap_blend: exposure[8] || 0,
      financial_sector: exposure[9] || 0,
      technology_sector: exposure[10] || 0,
      healthcare_sector: exposure[11] || 0,
      consumer_sector: exposure[12] || 0,
      industrial_sector: exposure[13] || 0,
      energy_sector: exposure[14] || 0,
      materials_sector: exposure[15] || 0,
      utilities_sector: exposure[16] || 0,
    }
  } catch (error) {
    console.error(`Failed to fetch factor exposure for ${fundCode}:`, error)
    return null
  }
}

// Fetch style box data for selected fund
const fetchStyleBoxData = async (fundCode: string): Promise<StyleBoxData | null> => {
  try {
    styleBoxLoading.value = true
    const today = new Date()
    const endDate = today.toISOString().split('T')[0]
    const startDate = new Date(today.setFullYear(today.getFullYear() - 1)).toISOString().split('T')[0]
    
    const response = await api.post('/analytics/factor-exposure', null, {
      params: {
        fund_code: fundCode,
        start_date: startDate,
        end_date: endDate,
      }
    }) as unknown as {
      fund_code: string
      style_factors: Array<{ name: string; weight: number }>
      sector_factors: Array<{ name: string; weight: number }>
    }
    
    // Extract style factors from response
    const styleFactors = response.style_factors || []
    const getWeight = (name: string): number => {
      const factor = styleFactors.find(f => f.name === name)
      return factor ? factor.weight * 100 : 0
    }
    
    // Map SIZE factor to market cap buckets (Large/Mid/Small)
    // Map VALUE/GROWTH factors to style (Value/Blend/Growth)
    const sizeWeight = getWeight('SIZE')
    const valueWeight = getWeight('VALUE')
    const growthWeight = getWeight('GROWTH')
    
    // Create synthetic Morningstar-style 9-box grid
    // This is a heuristic mapping from 6 factors to 9 boxes
    // SIZE determines market cap distribution
    // VALUE vs GROWTH determines style distribution
    
    // High SIZE = Large Cap, Medium SIZE = Mid Cap, Low SIZE = Small Cap
    const largeCapPct = sizeWeight > 50 ? 70 : sizeWeight > 30 ? 50 : 20
    const midCapPct = sizeWeight > 30 && sizeWeight <= 50 ? 50 : 30
    const smallCapPct = sizeWeight < 30 ? 70 : sizeWeight <= 50 ? 30 : 10
    
    // Value/Blend/Growth distribution
    const valuePct = valueWeight > 50 ? 60 : valueWeight > 30 ? 40 : 20
    const growthPct = growthWeight > 50 ? 60 : growthWeight > 30 ? 40 : 20
    const blendPct = 100 - valuePct - growthPct
    
    // Normalize to ensure sum = 100 for each row
    const normalizeRow = (val: number, blend: number, growth: number) => {
      const total = val + blend + growth
      return {
        value: (val / total) * 100,
        blend: (blend / total) * 100,
        growth: (growth / total) * 100
      }
    }
    
    const largeRow = normalizeRow(largeCapPct * valuePct / 100, largeCapPct * blendPct / 100, largeCapPct * growthPct / 100)
    const midRow = normalizeRow(midCapPct * valuePct / 100, midCapPct * blendPct / 100, midCapPct * growthPct / 100)
    const smallRow = normalizeRow(smallCapPct * valuePct / 100, smallCapPct * blendPct / 100, smallCapPct * growthPct / 100)
    
    return {
      large_cap_value: largeRow.value,
      large_cap_blend: largeRow.blend,
      large_cap_growth: largeRow.growth,
      mid_cap_value: midRow.value,
      mid_cap_blend: midRow.blend,
      mid_cap_growth: midRow.growth,
      small_cap_value: smallRow.value,
      small_cap_blend: smallRow.blend,
      small_cap_growth: smallRow.growth,
    }
  } catch (error) {
    console.error(`Failed to fetch style box data for ${fundCode}:`, error)
    // Return a balanced default distribution
    return {
      large_cap_value: 15,
      large_cap_blend: 25,
      large_cap_growth: 15,
      mid_cap_value: 10,
      mid_cap_blend: 15,
      mid_cap_growth: 10,
      small_cap_value: 5,
      small_cap_blend: 5,
      small_cap_growth: 5,
    }
  } finally {
    styleBoxLoading.value = false
  }
}

// Calculate factor exposures for all similar funds
const calculateFactorExposures = async () => {
  if (similarFunds.value.length === 0) {
    ElMessage.warning('请先计算相似基金')
    return
  }
  
  factorLoading.value = true
  showFactorTable.value = true
  const startTime = performance.now()
  
  try {
    const promises = similarFunds.value.slice(0, 10).map(fund => 
      fetchFactorExposure(fund.fund_code, fund.fund_name)
    )
    
    const results = await Promise.all(promises)
    factorExposures.value = results.filter((r): r is FactorExposure => r !== null)
    
    if (factorExposures.value.length === 0) {
      ElMessage.warning('无法获取因子暴露数据')
    }
  } catch (error) {
    ElMessage.error('因子暴露计算失败')
    console.error(error)
  } finally {
    factorCalculationTime.value = Math.round(performance.now() - startTime)
    factorLoading.value = false
  }
}

// Export factor exposure to CSV
const exportFactorExposure = () => {
  if (factorExposures.value.length === 0) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  
  const headers = ['基金代码', '基金名称', ...factorColumns.map(c => c.label)]
  const rows = factorExposures.value.map(exp => [
    exp.fund_code,
    exp.fund_name,
    ...factorColumns.map(c => (exp[c.key as keyof FactorExposure] as number).toFixed(4)),
  ])
  
  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `factor_exposure_${sourceFundCode.value}_${new Date().toISOString().split('T')[0]}.csv`
  link.click()
  URL.revokeObjectURL(url)
  
  ElMessage.success('导出成功')
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
    
    // Fetch style box data for selected fund
    await fetchStyleBoxData(sourceFundCode.value)
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

// Fetch style box data when source fund is selected
watch(sourceFundCode, async (newCode) => {
  if (newCode) {
    styleBoxData.value = await fetchStyleBoxData(newCode)
  } else {
    styleBoxData.value = null
  }
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

          <!-- Style Box Visualization -->
          <div v-if="sourceFundCode" class="style-box-section">
            <StyleBox
              v-if="styleBoxData && !styleBoxLoading"
              :data="styleBoxData"
              title="风格定位"
            />
            <div v-else-if="styleBoxLoading" class="style-box-loading">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>加载风格数据...</span>
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
          <!-- Style Box Section -->
          <div v-if="styleBoxData" class="style-box-section">
            <StyleBox 
              :data="styleBoxData" 
              title="源基金投资风格"
            />
          </div>

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

          <!-- Factor Exposure Section -->
          <div v-if="similarFunds.length > 0" class="factor-section">
            <div class="factor-header">
              <h4>因子暴露分析</h4>
              <div class="factor-actions">
                <el-button
                  type="primary"
                  size="small"
                  :loading="factorLoading"
                  @click="calculateFactorExposures"
                >
                  计算因子暴露
                </el-button>
                <el-button
                  v-if="factorExposures.length > 0"
                  size="small"
                  @click="exportFactorExposure"
                >
                  导出 CSV
                </el-button>
              </div>
            </div>

            <!-- Loading Progress -->
            <div v-if="factorLoading" class="factor-loading">
              <el-progress
                :percentage="100"
                :stroke-width="10"
                status="success"
                :indeterminate="true"
              />
              <p class="loading-text">正在计算 SLSQP 约束优化...</p>
            </div>

            <!-- Factor Exposure Table -->
            <div v-if="showFactorTable && factorExposures.length > 0 && !factorLoading" class="factor-table-wrapper">
              <div class="factor-meta">
                <span class="calc-time">计算耗时: {{ factorCalculationTime }}ms</span>
                <span class="fund-count">共 {{ factorExposures.length }} 只基金</span>
              </div>
              
              <el-table
                :data="factorExposures"
                stripe
                border
                max-height="400"
                size="small"
              >
                <el-table-column prop="fund_code" label="基金代码" width="90" fixed />
                
                <el-table-column prop="fund_name" label="基金名称" min-width="140" fixed>
                  <template #default="{ row }">
                    <span class="factor-fund-name">{{ row.fund_name }}</span>
                  </template>
                </el-table-column>

                <!-- Style Factors -->
                <el-table-column label="风格因子">
                  <el-table-column
                    v-for="col in factorColumns.slice(0, 6)"
                    :key="col.key"
                    :prop="col.key"
                    :label="col.label"
                    width="85"
                  >
                    <template #default="{ row }">
                      <div
                        class="factor-cell"
                        :style="getFactorBgStyle(row[col.key])"
                      >
                        {{ (row[col.key] as number).toFixed(3) }}
                      </div>
                    </template>
                  </el-table-column>
                </el-table-column>

                <!-- Sector Factors -->
                <el-table-column label="板块因子">
                  <el-table-column
                    v-for="col in factorColumns.slice(6)"
                    :key="col.key"
                    :prop="col.key"
                    :label="col.label"
                    width="85"
                  >
                    <template #default="{ row }">
                      <div
                        class="factor-cell"
                        :style="getFactorBgStyle(row[col.key])"
                      >
                        {{ (row[col.key] as number).toFixed(3) }}
                      </div>
                    </template>
                  </el-table-column>
                </el-table-column>
              </el-table>

              <!-- Factor Legend -->
              <div class="factor-legend">
                <span class="legend-title">颜色说明:</span>
                <span class="legend-item high">≥15% 高暴露</span>
                <span class="legend-item medium">≥10% 中等</span>
                <span class="legend-item low">≥5% 较低</span>
                <span class="legend-item minimal">&lt;5% 极低</span>
              </div>
            </div>

            <!-- Empty Factor State -->
            <div v-if="showFactorTable && factorExposures.length === 0 && !factorLoading" class="factor-empty">
              <p>暂无因子暴露数据，请点击计算按钮</p>
            </div>
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
  z-index: var(--z-dropdown);
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

/* Style Box Section */
.style-box-section {
  margin-top: 16px;
}

.style-box-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  background: rgba(0, 51, 153, 0.05);
  border-radius: 8px;
  color: var(--text-muted);
  font-size: 13px;
}

.style-box-loading .el-icon {
  font-size: 16px;
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

/* Style Box Section */
.style-box-section {
  margin-bottom: 20px;
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

/* Factor Exposure Section */
.factor-section {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--border-line);
}

.factor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.factor-header h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.factor-actions {
  display: flex;
  gap: 8px;
}

.factor-loading {
  padding: 24px;
  background: #fafafa;
  border-radius: 4px;
  text-align: center;
}

.loading-text {
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-muted);
}

.factor-table-wrapper {
  overflow-x: auto;
}

.factor-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--text-muted);
}

.calc-time {
  font-family: 'SF Mono', Monaco, monospace;
}

.fund-count {
  color: var(--text-regular);
}

.factor-cell {
  padding: 4px 8px;
  border-radius: 3px;
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
  text-align: center;
  font-weight: 500;
}

.factor-fund-name {
  font-size: 12px;
  color: var(--text-primary);
}

.factor-legend {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  font-size: 12px;
}

.legend-title {
  color: var(--text-muted);
  font-weight: 500;
}

.legend-item {
  padding: 2px 8px;
  border-radius: 3px;
}

.legend-item.high {
  background: rgba(34, 197, 94, 0.2);
  color: #166534;
}

.legend-item.medium {
  background: rgba(134, 239, 172, 0.3);
  color: #15803d;
}

.legend-item.low {
  background: rgba(254, 240, 138, 0.4);
  color: #854d0e;
}

.legend-item.minimal {
  background: rgba(248, 113, 113, 0.2);
  color: #991b1b;
}

.factor-empty {
  padding: 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  background: #fafafa;
  border-radius: 4px;
}
</style>
