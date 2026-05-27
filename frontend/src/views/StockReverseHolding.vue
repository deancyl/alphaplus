<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getStockReverseHolding, type StockReverseHoldingResponse } from '@/api/fund'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import { useBreakpoint } from '@/composables/useBreakpoint'
import type { EChartsOption } from 'echarts'

const { isMobile } = useBreakpoint()
const searchCode = ref('')
const loading = ref(false)
const result = ref<StockReverseHoldingResponse | null>(null)

const handleSearch = async () => {
  if (!searchCode.value.trim()) {
    ElMessage.warning('请输入股票代码')
    return
  }
  
  loading.value = true
  try {
    result.value = await getStockReverseHolding(searchCode.value.trim())
  } catch (error) {
    console.error('Failed to fetch stock reverse holding:', error)
    ElMessage.error('查询失败，请检查股票代码')
  } finally {
    loading.value = false
  }
}

const pieChartOption = computed<EChartsOption>(() => {
  if (!result.value || result.value.funds.length === 0) {
    return {}
  }

  const top10 = result.value.funds.slice(0, 10)

  const colorPalette = [
    '#003399',
    '#0B3CC3',
    '#4A90D9',
    '#2E7D32',
    '#689F38',
    '#E63935',
    '#FF7043',
    '#FFB300',
    '#7B1FA2',
    '#00838F',
  ]

  const data = top10.map((item, index) => ({
    name: item.fund_name,
    value: item.holding_ratio * 100,
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
        const item = top10.find(f => f.fund_name === name)
        if (item) {
          return `${name}  ${(item.holding_ratio * 100).toFixed(1)}%`
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

const formatHoldingRatio = (ratio: number): string => {
  return `${(ratio * 100).toFixed(2)}%`
}

const formatHoldingValue = (value?: number): string => {
  if (value === undefined || value === null) return '-'
  return value.toLocaleString()
}
</script>

<template>
  <div class="stock-reverse-view">
    <div class="search-section card">
      <div class="search-header">
        <h2>机构抱团分析</h2>
        <span class="search-subtitle">查找持有特定股票的基金</span>
      </div>
      
      <div class="search-form">
        <el-input
          v-model="searchCode"
          placeholder="输入股票代码，如 600519"
          clearable
          size="large"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <span class="search-icon">🔍</span>
          </template>
        </el-input>
        
        <el-button
          type="primary"
          size="large"
          :loading="loading"
          @click="handleSearch"
        >
          查询
        </el-button>
      </div>
      
      <div class="search-hints">
        <span class="hint-item">热门: 600519 贵州茅台</span>
        <span class="hint-item">000858 五粮液</span>
        <span class="hint-item">000001 平安银行</span>
      </div>
    </div>

    <div v-if="result" class="results-section">
      <div class="summary-grid">
        <div class="summary-card card">
          <div class="summary-label">股票名称</div>
          <div class="summary-value">{{ result.stock_name }}</div>
          <div class="summary-code">{{ result.stock_code }}</div>
        </div>
        
        <div class="summary-card card">
          <div class="summary-label">持有基金数</div>
          <div class="summary-value summary-value--highlight">{{ result.total_funds }}</div>
          <div class="summary-unit">只基金</div>
        </div>
        
        <div class="summary-card card">
          <div class="summary-label">加总暴露</div>
          <div class="summary-value summary-value--exposure">
            {{ result.aggregate_exposure.toFixed(2) }}%
          </div>
          <div class="summary-note">合计持仓占净值</div>
        </div>
      </div>

      <div class="chart-section card">
        <div class="section-header">
          <h3>Top 10 持仓基金分布</h3>
          <span class="section-tag">占比可视化</span>
        </div>
        
        <EChartsWrapper
          :option="pieChartOption"
          :height="isMobile ? '300px' : '400px'"
        />
      </div>

      <div class="table-section card">
        <div class="section-header">
          <h3>持仓基金明细</h3>
          <span class="section-count">共 {{ result.funds.length }} 只</span>
        </div>
        
        <el-table
          :data="result.funds"
          :stripe="true"
          :size="isMobile ? 'small' : 'default'"
          :loading="loading"
        >
          <el-table-column
            prop="fund_code"
            label="基金代码"
            width="100"
            fixed
          />
          <el-table-column
            prop="fund_name"
            label="基金名称"
            min-width="140"
          />
          <el-table-column
            prop="holding_ratio"
            label="占净值比"
            width="100"
            sortable
          >
            <template #default="{ row }">
              <span class="ratio-cell">{{ formatHoldingRatio(row.holding_ratio) }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="holding_value"
            label="持股市值(万)"
            width="120"
            sortable
          >
            <template #default="{ row }">
              {{ formatHoldingValue(row.holding_value) }}
            </template>
          </el-table-column>
          <el-table-column
            prop="report_date"
            label="报告期"
            width="110"
          />
        </el-table>
        
        <div v-if="result.funds.length === 0" class="empty-table">
          暂无持仓基金数据
        </div>
      </div>
    </div>

    <div v-else class="empty-initial-state card">
      <div class="empty-icon">📊</div>
      <p class="empty-title">查询机构抱团情况</p>
      <p class="empty-desc">输入股票代码，查看哪些基金持有该股票</p>
    </div>
  </div>
</template>

<style scoped>
.stock-reverse-view {
  min-height: calc(100vh - 100px);
  padding: var(--spacing-md);
}

.search-section {
  margin-bottom: var(--spacing-md);
}

.search-header {
  margin-bottom: var(--spacing-md);
}

.search-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.search-subtitle {
  display: block;
  font-size: 14px;
  color: var(--text-muted);
  margin-top: var(--spacing-xs);
}

.search-form {
  display: flex;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.search-form .el-input {
  flex: 1;
  max-width: 400px;
}

.search-icon {
  font-size: 16px;
}

.search-hints {
  display: flex;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.hint-item {
  font-size: 13px;
  color: var(--text-muted);
  cursor: pointer;
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-system);
  border-radius: 4px;
  transition: all 0.2s;
}

.hint-item:hover {
  color: var(--brand-navy-active);
  background: var(--mark-area-normal);
}

.results-section {
  display: grid;
  gap: var(--spacing-md);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-md);
}

.summary-card {
  text-align: center;
  padding: var(--spacing-lg);
}

.summary-label {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: var(--spacing-sm);
}

.summary-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-xs);
}

.summary-value--highlight {
  color: var(--brand-navy-dark);
}

.summary-value--exposure {
  color: var(--market-down);
}

.summary-code {
  font-size: 14px;
  font-family: 'SF Mono', Monaco, 'Courier New', monospace;
  color: var(--text-regular);
}

.summary-unit {
  font-size: 13px;
  color: var(--text-muted);
}

.summary-note {
  font-size: 12px;
  color: var(--text-muted);
}

.chart-section,
.table-section {
  padding: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-line);
}

.section-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.section-tag {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-system);
  padding: 2px 8px;
  border-radius: 4px;
}

.section-count {
  font-size: 13px;
  color: var(--text-regular);
}

.ratio-cell {
  font-weight: 500;
  color: var(--brand-navy-dark);
}

.empty-table {
  padding: var(--spacing-lg);
  text-align: center;
  color: var(--text-muted);
}

.empty-initial-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  opacity: 0.5;
  margin-bottom: var(--spacing-md);
}

.empty-title {
  font-size: 18px;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-sm);
}

.empty-desc {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0;
}

@media (max-width: 768px) {
  .stock-reverse-view {
    padding: var(--spacing-sm);
  }

  .search-header h2 {
    font-size: 18px;
  }

  .search-form {
    flex-direction: column;
  }

  .search-form .el-input {
    max-width: none;
  }

  .search-hints {
    gap: var(--spacing-sm);
  }

  .hint-item {
    font-size: 12px;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .summary-card {
    padding: var(--spacing-md);
  }

  .summary-value {
    font-size: 20px;
  }

  .section-header {
    padding: var(--spacing-sm);
  }

  .section-header h3 {
    font-size: 14px;
  }
}

@media (max-width: 480px) {
  .summary-value {
    font-size: 18px;
  }
}
</style>