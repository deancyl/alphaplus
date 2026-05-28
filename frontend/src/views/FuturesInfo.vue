<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getFuturesQuotes } from '@/api/market'

// 期货合约类型定义
interface FuturesContract {
  code: string
  name: string
  exchange: string
  category: string
  price: number
  change: number
  change_pct: number
  volume: number
  open_interest: number
  spot_price: number
  basis: number
  basis_pct: number
}

// 期货分类配置
const futuresCategories = [
  { label: '商品期货', value: 'commodity' },
  { label: '金融期货', value: 'financial' },
  { label: '能源期货', value: 'energy' },
]

// 合约月份选项
const contractMonths = [
  { label: '当月', value: 0 },
  { label: '下月', value: 1 },
  { label: '季月', value: 3 },
  { label: '次季月', value: 6 },
]

// 各分类下的合约代码
const categoryContracts: Record<string, string[]> = {
  commodity: ['CU', 'AL', 'ZN', 'NI', 'SN', 'PB', 'AU', 'AG', 'C', 'S', 'M', 'Y', 'P', 'SR', 'CF', 'TA', 'MA', 'FG'],
  financial: ['IF', 'IC', 'IM', 'IH', 'T', 'TF', 'TS', 'TL'],
  energy: ['SC', 'FU', 'PG', 'EB', 'PP', 'L', 'V', 'RU', 'NR'],
}

// 状态
const activeCategory = ref('commodity')
const selectedMonth = ref(0)
const contracts = ref<FuturesContract[]>([])
const selectedContract = ref<FuturesContract | null>(null)
const loading = ref(false)
const chartInstance = ref<echarts.ECharts | null>(null)

// 计算基差
const calculateBasis = (spotPrice: number, futuresPrice: number): { basis: number; basis_pct: number } => {
  const basis = spotPrice - futuresPrice
  const basis_pct = futuresPrice !== 0 ? (basis / futuresPrice) * 100 : 0
  return { basis, basis_pct }
}

// 获取合约名称
const getContractName = (code: string): string => {
  const nameMap: Record<string, string> = {
    // 有色金属
    CU: '沪铜', AL: '沪铝', ZN: '沪锌', NI: '沪镍', SN: '沪锡', PB: '沪铅',
    // 贵金属
    AU: '沪金', AG: '沪银',
    // 农产品
    C: '玉米', S: '豆一', M: '豆粕', Y: '豆油', P: '棕榈油', SR: '白糖', CF: '棉花',
    // 化工
    TA: 'PTA', MA: '甲醇', FG: '玻璃',
    // 金融期货
    IF: '沪深300', IC: '中证500', IM: '中证1000', IH: '上证50',
    T: '十年国债', TF: '五年国债', TS: '两年国债', TL: '三十年国债',
    // 能源
    SC: '原油', FU: '燃油', PG: 'LPG', EB: '苯乙烯', PP: 'PP', L: 'LLDPE', V: 'PVC', RU: '橡胶', NR: '20号胶',
  }
  return nameMap[code] || code
}

// 获取交易所
const getExchange = (code: string): string => {
  if (['IF', 'IC', 'IM', 'IH', 'T', 'TF', 'TS', 'TL'].includes(code)) return '中金所'
  if (['SC', 'NR'].includes(code)) return '能源中心'
  if (['CU', 'AL', 'ZN', 'NI', 'SN', 'PB', 'AU', 'AG', 'RB', 'HC', 'SS'].includes(code)) return '上期所'
  if (['C', 'S', 'M', 'Y', 'P', 'SR', 'CF', 'JD', 'LH'].includes(code)) return '大商所'
  if (['TA', 'MA', 'FG', 'RM', 'OI', 'ZC', 'SF', 'SM', 'AP', 'CJ'].includes(code)) return '郑商所'
  return '广期所'
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const data = await getFuturesQuotes(activeCategory.value)
    contracts.value = data
    if (contracts.value.length > 0 && !selectedContract.value) {
      selectedContract.value = contracts.value[0]
      await nextTick()
      initChart()
    }
  } catch (error) {
    ElMessage.error('加载期货数据失败')
  } finally {
    loading.value = false
  }
}

// 初始化图表
const initChart = () => {
  const chartDom = document.getElementById('price-chart')
  if (!chartDom) return
  
  if (chartInstance.value) {
    chartInstance.value.dispose()
  }
  
  chartInstance.value = echarts.init(chartDom)
  updateChart()
}

// 更新图表
const updateChart = () => {
  if (!chartInstance.value) return
  
  const option: echarts.EChartsOption = {
    title: {
      text: selectedContract.value ? `${selectedContract.value.name} 价格走势` : '价格走势',
      left: 'center',
      textStyle: {
        fontSize: 14,
        color: 'var(--text-primary)',
      },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: 'var(--border-line)',
      textStyle: {
        color: 'var(--text-regular)',
      },
    },
    legend: {
      data: ['期货价格', '现货价格'],
      bottom: 10,
      textStyle: {
        color: 'var(--text-regular)',
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '15%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: [],
      boundaryGap: false,
      axisLine: {
        lineStyle: {
          color: 'var(--border-line)',
        },
      },
      axisLabel: {
        color: 'var(--text-muted)',
        fontSize: 11,
      },
    },
    yAxis: {
      type: 'value',
      axisLine: {
        show: false,
      },
      axisLabel: {
        color: 'var(--text-muted)',
        fontSize: 11,
      },
      splitLine: {
        lineStyle: {
          color: 'var(--border-line)',
          type: 'dashed',
        },
      },
    },
    series: [
      {
        name: '期货价格',
        type: 'line',
        data: [],
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 2,
          color: 'var(--brand-navy-dark)',
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 51, 153, 0.3)' },
            { offset: 1, color: 'rgba(0, 51, 153, 0.05)' },
          ]),
        },
      },
      {
        name: '现货价格',
        type: 'line',
        data: [],
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 2,
          color: 'var(--market-up)',
          type: 'dashed',
        },
      },
    ],
  }
  
  chartInstance.value.setOption(option)
}

// 选择合约
const handleSelectContract = (contract: FuturesContract) => {
  selectedContract.value = contract
  updateChart()
}

// 格式化数字
const formatNumber = (val: number | null | undefined, decimals = 2): string => {
  if (val === null || val === undefined) return '-'
  return val.toFixed(decimals)
}

// 获取涨跌样式
const getValueClass = (val: number | null | undefined): string => {
  if (val === null || val === undefined) return ''
  return val >= 0 ? 'text-up' : 'text-down'
}

// 格式化成交量
const formatVolume = (val: number): string => {
  if (val >= 10000) {
    return (val / 10000).toFixed(2) + '万'
  }
  return val.toString()
}

// 监听分类切换
watch(activeCategory, () => {
  selectedContract.value = null
  loadData()
})

// 监听月份切换
watch(selectedMonth, () => {
  loadData()
})

// 窗口大小变化时重绘图表
const handleResize = () => {
  chartInstance.value?.resize()
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})
</script>

<template>
  <div class="futures-info">
    <!-- 顶部控制栏 -->
    <div class="control-bar">
      <div class="tabs-wrapper">
        <el-tabs v-model="activeCategory" class="category-tabs">
          <el-tab-pane
            v-for="cat in futuresCategories"
            :key="cat.value"
            :label="cat.label"
            :name="cat.value"
          />
        </el-tabs>
      </div>
      
      <div class="month-selector">
        <span class="selector-label">合约月份:</span>
        <el-select v-model="selectedMonth" size="small" style="width: 100px;">
          <el-option
            v-for="month in contractMonths"
            :key="month.value"
            :label="month.label"
            :value="month.value"
          />
        </el-select>
      </div>
    </div>
    
    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧行情表格 -->
      <div class="quote-panel">
        <div class="panel-header">
          <h3>期货行情</h3>
          <span class="update-time">更新时间: {{ new Date().toLocaleTimeString() }}</span>
        </div>
        
        <el-table
          :data="contracts"
          :loading="loading"
          stripe
          highlight-current-row
          @current-change="handleSelectContract"
          height="calc(100dvh - 280px)"
        >
          <el-table-column prop="code" label="代码" width="70" fixed />
          <el-table-column prop="name" label="名称" width="90" />
          <el-table-column prop="price" label="最新价" width="100" align="right">
            <template #default="{ row }">
              <span class="price-value">{{ formatNumber(row.price) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="change" label="涨跌" width="80" align="right">
            <template #default="{ row }">
              <span :class="getValueClass(row.change)">
                {{ row.change >= 0 ? '+' : '' }}{{ formatNumber(row.change) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="change_pct" label="涨跌幅%" width="90" align="right">
            <template #default="{ row }">
              <span :class="getValueClass(row.change_pct)">
                {{ row.change_pct >= 0 ? '+' : '' }}{{ formatNumber(row.change_pct) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="volume" label="成交量" width="90" align="right">
            <template #default="{ row }">
              {{ formatVolume(row.volume) }}
            </template>
          </el-table-column>
          <el-table-column prop="open_interest" label="持仓量" width="90" align="right">
            <template #default="{ row }">
              {{ formatVolume(row.open_interest) }}
            </template>
          </el-table-column>
        </el-table>
      </div>
      
      <!-- 右侧图表与基差分析 -->
      <div class="chart-panel">
        <!-- 价格走势图 -->
        <div class="chart-container">
          <div id="price-chart" class="price-chart" />
        </div>
        
        <!-- 基差分析 -->
        <div class="basis-panel">
          <div class="panel-header">
            <h3>基差分析</h3>
            <span v-if="selectedContract" class="contract-info">
              {{ selectedContract.name }} ({{ selectedContract.code }})
            </span>
          </div>
          
          <div v-if="selectedContract" class="basis-content">
            <div class="basis-row">
              <div class="basis-item">
                <span class="basis-label">现货价格</span>
                <span class="basis-value">{{ formatNumber(selectedContract.spot_price) }}</span>
              </div>
              <div class="basis-item">
                <span class="basis-label">期货价格</span>
                <span class="basis-value">{{ formatNumber(selectedContract.price) }}</span>
              </div>
              <div class="basis-item">
                <span class="basis-label">基差</span>
                <span class="basis-value" :class="getValueClass(selectedContract.basis)">
                  {{ selectedContract.basis >= 0 ? '+' : '' }}{{ formatNumber(selectedContract.basis) }}
                </span>
              </div>
              <div class="basis-item">
                <span class="basis-label">基差率</span>
                <span class="basis-value" :class="getValueClass(selectedContract.basis_pct)">
                  {{ selectedContract.basis_pct >= 0 ? '+' : '' }}{{ formatNumber(selectedContract.basis_pct) }}%
                </span>
              </div>
            </div>
            
            <div class="basis-explanation">
              <div v-if="selectedContract.basis > 0" class="explanation-item">
                <span class="status-tag status-premium">升水</span>
                <span class="explanation-text">
                  现货价格高于期货价格，市场处于升水状态，可能反映现货供应紧张或市场对未来价格看跌预期。
                </span>
              </div>
              <div v-else-if="selectedContract.basis < 0" class="explanation-item">
                <span class="status-tag status-discount">贴水</span>
                <span class="explanation-text">
                  现货价格低于期货价格，市场处于贴水状态，可能反映现货供应充足或市场对未来价格看涨预期。
                </span>
              </div>
              <div v-else class="explanation-item">
                <span class="status-tag status-flat">平水</span>
                <span class="explanation-text">
                  现货价格与期货价格基本持平，市场处于均衡状态。
                </span>
              </div>
            </div>
          </div>
          
          <div v-else class="empty-basis">
            <span class="empty-text">请选择合约查看基差分析</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.futures-info {
  height: calc(100vh - 100px); /* Fallback for older browsers */
  height: calc(100dvh - 100px);
  display: flex;
  flex-direction: column;
}

.control-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 0 16px;
  margin-bottom: 16px;
}

.tabs-wrapper {
  flex: 1;
}

.category-tabs {
  --el-tabs-header-height: 44px;
}

.category-tabs :deep(.el-tabs__header) {
  margin: 0;
  border-bottom: none;
}

.category-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.category-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  color: var(--text-regular);
  padding: 0 20px;
}

.category-tabs :deep(.el-tabs__item.is-active) {
  color: var(--brand-navy-dark);
  font-weight: 600;
}

.category-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--brand-navy-dark);
}

.month-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.selector-label {
  font-size: 13px;
  color: var(--text-regular);
}

.main-content {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.quote-panel {
  width: 680px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.chart-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.chart-container {
  flex: 1;
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
  min-height: 300px;
}

.price-chart {
  width: 100%;
  height: 100%;
  min-height: 280px;
}

.basis-panel {
  background: var(--bg-card);
  border-radius: 4px;
  padding: 16px;
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

.update-time {
  font-size: 12px;
  color: var(--text-muted);
}

.contract-info {
  font-size: 13px;
  color: var(--text-regular);
  background: var(--bg-system);
  padding: 4px 12px;
  border-radius: 4px;
}

.basis-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.basis-row {
  display: flex;
  gap: 24px;
}

.basis-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.basis-label {
  font-size: 12px;
  color: var(--text-muted);
}

.basis-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.basis-explanation {
  padding: 12px;
  background: var(--bg-system);
  border-radius: 4px;
}

.explanation-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.status-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.status-premium {
  background: rgba(230, 57, 53, 0.1);
  color: var(--market-up);
}

.status-discount {
  background: rgba(46, 125, 50, 0.1);
  color: var(--market-down);
}

.status-flat {
  background: rgba(153, 153, 153, 0.1);
  color: var(--market-flat);
}

.explanation-text {
  font-size: 13px;
  color: var(--text-regular);
  line-height: 1.6;
}

.empty-basis {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.empty-text {
  font-size: 14px;
  color: var(--text-muted);
}

.price-value {
  font-weight: 600;
  color: var(--text-primary);
}

/* 涨跌颜色 */
.text-up {
  color: var(--market-up);
}

.text-down {
  color: var(--market-down);
}

.text-flat {
  color: var(--market-flat);
}
</style>
