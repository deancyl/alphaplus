<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getFundDetail,
  getFundHoldings,
  getFundIndustry,
  type FundItem,
  type HoldingItem,
  type IndustryItem,
  type ReportDate,
} from '@/api/fund'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import { useBreakpoint } from '@/composables/useBreakpoint'
import type { EChartsOption } from 'echarts'

// ==================== Composables & State ====================

const route = useRoute()
const { isMobile } = useBreakpoint()

// Fund basic info
const fundInfo = ref<FundItem | null>(null)
const fundLoading = ref(false)

// Report dates
const availableDates = ref<ReportDate[]>([])
const selectedDate = ref<string>('')

// Holdings data
const holdings = ref<HoldingItem[]>([])
const holdingsLoading = ref(false)

// Industry data
const industries = ref<IndustryItem[]>([])
const industryLoading = ref(false)

// Get fund code from route
const fundCode = computed(() => route.params.fundCode as string || route.query.code as string)

// ==================== Computed Properties ====================

/**
 * ECharts pie chart option for industry allocation
 */
const industryChartOption = computed<EChartsOption>(() => {
  if (!industries.value.length) {
    return {}
  }

  // Color palette - sophisticated financial colors
  const colorPalette = [
    '#003399', // Brand navy
    '#0B3CC3', // Brand navy active
    '#4A90D9', // Light blue
    '#2E7D32', // Green
    '#689F38', // Light green
    '#E63935', // Red
    '#FF7043', // Orange
    '#FFB300', // Amber
    '#7B1FA2', // Purple
    '#00838F', // Cyan
  ]

  const data = industries.value.map((item, index) => ({
    name: item.industry_name,
    value: item.weight,
    itemStyle: {
      color: colorPalette[index % colorPalette.length]
    }
  }))

  return {
    tooltip: {
      trigger: 'item' as const,
      formatter: (params: any) => {
        return `${params.name}<br/>${params.value.toFixed(2)}%`
      },
      confine: true,
    },
    legend: {
      type: 'scroll' as const,
      orient: isMobile.value ? 'horizontal' : 'vertical' as const,
      right: isMobile.value ? 'center' : '5%' as const,
      top: isMobile.value ? 'bottom' : 'middle' as const,
      itemWidth: 12,
      itemHeight: 12,
      itemGap: 8,
      textStyle: {
        fontSize: 12,
        color: 'var(--text-regular)',
      },
      formatter: (name: string) => {
        const item = industries.value.find(i => i.industry_name === name)
        if (item) {
          return `${name}  ${item.weight.toFixed(2)}%`
        }
        return name
      }
    },
    series: [{
      type: 'pie' as const,
      radius: isMobile.value ? ['35%', '55%'] : ['40%', '65%'],
      center: isMobile.value ? ['50%', '45%'] : ['35%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 4,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: {
        show: false
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 14,
          fontWeight: 'bold' as const,
          formatter: '{b}\n{d}%'
        },
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.3)'
        }
      },
      data
    }]
  }
})

/**
 * Get change direction display text and class
 */
const getChangeDirectionInfo = (direction: HoldingItem['change_direction']) => {
  const map = {
    new: { text: '新进', class: 'direction-new' },
    increase: { text: '增持', class: 'direction-increase' },
    decrease: { text: '减持', class: 'direction-decrease' },
    unchanged: { text: '不变', class: 'direction-unchanged' }
  }
  return map[direction] || map.unchanged
}

// ==================== API Methods ====================

/**
 * Fetch fund basic info
 */
const fetchFundInfo = async () => {
  if (!fundCode.value) return
  
  fundLoading.value = true
  try {
    const data = await getFundDetail(fundCode.value)
    if (data) fundInfo.value = data
  } catch {
    // API interceptor already handled notification
  } finally {
    fundLoading.value = false
  }
}

const fetchHoldings = async () => {
  if (!fundCode.value) return
  
  holdingsLoading.value = true
  try {
    const response = await getFundHoldings(fundCode.value, selectedDate.value || undefined)
    if (response && response.report_dates) {
      availableDates.value = response.report_dates
      if (!selectedDate.value && response.report_dates.length > 0) {
        selectedDate.value = response.report_dates[0].report_date
      }
      holdings.value = response.holdings
    }
  } catch {
    // API interceptor already handled notification
  } finally {
    holdingsLoading.value = false
  }
}

const fetchIndustry = async () => {
  if (!fundCode.value) return
  
  industryLoading.value = true
  try {
    const response = await getFundIndustry(fundCode.value, selectedDate.value || undefined)
    if (response && response.industries) {
      industries.value = response.industries
    }
  } catch {
    // API interceptor already handled notification
  } finally {
    industryLoading.value = false
  }
}

const handleDateChange = () => {
  fetchHoldings()
  fetchIndustry()
}

// ==================== Lifecycle ====================

watch(fundCode, () => {
  if (fundCode.value) {
    fetchFundInfo()
    fetchHoldings()
    fetchIndustry()
  }
}, { immediate: true })

onMounted(() => {
  if (fundCode.value) {
    fetchFundInfo()
  }
})
</script>

<template>
  <div class="fund-detail">
    <!-- Header Section -->
    <div class="detail-header">
      <div class="header-content">
        <div v-if="fundLoading" class="loading-skeleton header-skeleton"></div>
        <template v-else-if="fundInfo">
          <div class="fund-title">
            <h1>{{ fundInfo.fund_name }}</h1>
            <span class="fund-code">{{ fundInfo.fund_code }}</span>
          </div>
          <div class="fund-meta">
            <span class="meta-item">
              <label>基金类型</label>
              <span>{{ fundInfo.fund_type }}</span>
            </span>
            <span class="meta-item">
              <label>基金经理</label>
              <span>{{ fundInfo.manager || '-' }}</span>
            </span>
            <span class="meta-item">
              <label>基金规模</label>
              <span>{{ fundInfo.scale ? `${fundInfo.scale.toFixed(2)}亿` : '-' }}</span>
            </span>
            <span class="meta-item">
              <label>成立日期</label>
              <span>{{ fundInfo.setup_date || '-' }}</span>
            </span>
          </div>
          <div v-if="fundInfo.manager_honors" class="manager-honors">
            <span class="honors-label">经理荣誉:</span>
            <span class="honors-value">{{ fundInfo.manager_honors }}</span>
          </div>
        </template>
      </div>
    </div>

    <!-- Report Date Selector -->
    <div class="date-selector-bar">
      <span class="selector-label">报告期:</span>
      <el-select
        v-model="selectedDate"
        placeholder="选择报告期"
        size="default"
        @change="handleDateChange"
      >
        <el-option
          v-for="date in availableDates"
          :key="date.report_date"
          :label="date.label"
          :value="date.report_date"
        />
      </el-select>
    </div>

    <!-- Main Content Grid -->
    <div class="content-grid">
      <!-- Top Holdings Section -->
      <section class="holdings-section card">
        <div class="section-header">
          <h2>前十大重仓股</h2>
          <span v-if="selectedDate" class="report-date-tag">{{ selectedDate }}</span>
        </div>
        
        <div v-loading="holdingsLoading" class="holdings-content">
          <el-table
            :data="holdings"
            :stripe="true"
            :size="isMobile ? 'small' : 'default'"
            class="holdings-table"
          >
            <el-table-column
              prop="stock_code"
              label="股票代码"
              width="100"
              fixed
            />
            <el-table-column
              prop="stock_name"
              label="股票名称"
              min-width="100"
            />
            <el-table-column
              prop="holding_ratio"
              label="持仓比例"
              width="100"
              sortable
            >
              <template #default="{ row }">
                <span class="ratio-value">{{ row.holding_ratio.toFixed(2) }}%</span>
              </template>
            </el-table-column>
            <el-table-column
              prop="holding_value"
              label="持仓市值(万)"
              width="120"
              sortable
            >
              <template #default="{ row }">
                {{ row.holding_value.toLocaleString() }}
              </template>
            </el-table-column>
            <el-table-column
              prop="change_direction"
              label="变动方向"
              width="90"
            >
              <template #default="{ row }">
                <span :class="['direction-tag', getChangeDirectionInfo(row.change_direction).class]">
                  {{ getChangeDirectionInfo(row.change_direction).text }}
                </span>
              </template>
            </el-table-column>
          </el-table>
          
          <div v-if="!holdingsLoading && holdings.length === 0" class="empty-state">
            暂无持仓数据
          </div>
        </div>
      </section>

      <!-- Industry Allocation Section -->
      <section class="industry-section card">
        <div class="section-header">
          <h2>行业配置</h2>
          <span v-if="selectedDate" class="report-date-tag">{{ selectedDate }}</span>
        </div>
        
        <div v-loading="industryLoading" class="industry-content">
          <EChartsWrapper
            v-if="industries.length > 0"
            :option="industryChartOption"
            :height="isMobile ? '300px' : '400px'"
          />
          
          <div v-if="!industryLoading && industries.length === 0" class="empty-state">
            暂无行业数据
          </div>
        </div>
      </section>
    </div>

    <!-- Empty State -->
    <div v-if="!fundCode" class="no-fund-selected">
      <p>请选择一只基金查看详情</p>
    </div>
  </div>
</template>

<style scoped>
.fund-detail {
  min-height: calc(100vh - 100px); /* Fallback for older browsers */
  min-height: calc(100dvh - 100px);
  padding: var(--spacing-md);
}

/* Header Section */
.detail-header {
  background: var(--bg-card);
  border-radius: 4px;
  padding: var(--spacing-lg);
  margin-bottom: var(--spacing-md);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.header-content {
  max-width: 1200px;
}

.fund-title {
  display: flex;
  align-items: baseline;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.fund-title h1 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.fund-code {
  font-size: 14px;
  color: var(--text-muted);
  font-family: 'SF Mono', Monaco, 'Courier New', monospace;
}

.fund-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-sm);
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.meta-item label {
  font-size: 12px;
  color: var(--text-muted);
}

.meta-item span {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.manager-honors {
  margin-top: var(--spacing-sm);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--border-line);
  font-size: 13px;
}

.honors-label {
  color: var(--text-muted);
  margin-right: var(--spacing-sm);
}

.honors-value {
  color: var(--brand-navy-dark);
}

/* Date Selector Bar */
.date-selector-bar {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-card);
  border-radius: 4px;
}

.selector-label {
  font-size: 14px;
  color: var(--text-regular);
  font-weight: 500;
}

/* Content Grid */
.content-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--spacing-md);
}

@media (min-width: 1024px) {
  .content-grid {
    grid-template-columns: 1.2fr 1fr;
  }
}

/* Section Styles */
.card {
  background: var(--bg-card);
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-line);
}

.section-header h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.report-date-tag {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-system);
  padding: 2px 8px;
  border-radius: 4px;
}

/* Holdings Section */
.holdings-content {
  padding: var(--spacing-md);
}

.holdings-table {
  width: 100%;
}

.ratio-value {
  font-weight: 500;
  color: var(--brand-navy-dark);
}

/* Direction Tags */
.direction-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.direction-new,
.direction-increase {
  background: rgba(46, 125, 50, 0.1);
  color: var(--market-down); /* Green in A-share context */
}

.direction-decrease {
  background: rgba(230, 57, 53, 0.1);
  color: var(--market-up); /* Red in A-share context */
}

.direction-unchanged {
  background: rgba(153, 153, 153, 0.1);
  color: var(--market-flat);
}

/* Industry Section */
.industry-content {
  padding: var(--spacing-md);
  min-height: 300px;
}

/* Empty State */
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  color: var(--text-muted);
  font-size: 14px;
}

.no-fund-selected {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  color: var(--text-muted);
}

/* Loading Skeleton */
.loading-skeleton {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 4px;
}

.header-skeleton {
  height: 80px;
  width: 100%;
}

@keyframes skeleton-loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Mobile Responsive */
@media (max-width: 768px) {
  .fund-detail {
    padding: var(--spacing-sm);
  }
  
  .detail-header {
    padding: var(--spacing-md);
  }
  
  .fund-title {
    flex-direction: column;
    gap: var(--spacing-xs);
  }
  
  .fund-title h1 {
    font-size: 18px;
  }
  
  .fund-meta {
    gap: var(--spacing-md);
  }
  
  .date-selector-bar {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-xs);
  }
  
  .holdings-content,
  .industry-content {
    padding: var(--spacing-sm);
  }
  
  .section-header {
    padding: var(--spacing-sm);
  }
  
  .section-header h2 {
    font-size: 14px;
  }
}

/* Tablet Responsive */
@media (max-width: 1024px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
  
  .industry-section {
    order: 2;
  }
}
</style>
