<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

interface DepositRate {
  bank: string
  product: string
  rate: number
  rate_display: string
}

interface TreasuryYield {
  tenor: string
  yield: number
  yield_display: string
}

interface Spread {
  bank: string
  product: string
  deposit_rate: number
  treasury_yield: number
  spread: number
  spread_display: string
}

interface DepositData {
  deposit_rates: DepositRate[]
  treasury_yields: TreasuryYield[]
  spreads: Spread[]
  timestamp: string
}

const loading = ref(true)
const depositData = ref<DepositData>({
  deposit_rates: [],
  treasury_yields: [],
  spreads: [],
  timestamp: ''
})
const autoRefresh = ref(false)
let refreshInterval: ReturnType<typeof setInterval> | null = null

const REFRESH_INTERVAL = 30000

const fetchDepositRates = async () => {
  try {
    const response = await axios.get<DepositData>('/api/v1/deposit/rates')
    depositData.value = response.data
  } catch (error) {
    console.error('Failed to load deposit rates:', error)
    ElMessage.error('获取存款利率数据失败')
  } finally {
    loading.value = false
  }
}

const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    refreshInterval = setInterval(fetchDepositRates, REFRESH_INTERVAL)
    ElMessage.success('已开启自动刷新 (30秒)')
  } else {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
    ElMessage.info('已关闭自动刷新')
  }
}

const getSpreadColor = (spread: number): string => {
  if (spread >= 0.5) return 'var(--market-up)'
  if (spread <= 0) return 'var(--market-down)'
  return 'var(--text-primary)'
}

const formatTimestamp = (timestamp: string): string => {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchDepositRates()
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<template>
  <div class="deposit-market" v-loading="loading">
    <div class="page-header">
      <div class="header-left">
        <h2>存款产品利率研究</h2>
        <span class="update-time" v-if="depositData.timestamp">
          更新时间: {{ formatTimestamp(depositData.timestamp) }}
        </span>
      </div>
      <div class="header-actions">
        <el-button size="small" @click="fetchDepositRates" :loading="loading">
          刷新
        </el-button>
        <el-button 
          size="small" 
          :type="autoRefresh ? 'primary' : 'default'"
          @click="toggleAutoRefresh"
        >
          {{ autoRefresh ? '停止刷新' : '自动刷新' }}
        </el-button>
      </div>
    </div>

    <div class="treasury-section card">
      <h3 class="section-title">国债收益率曲线</h3>
      <div class="yield-cards">
        <div 
          v-for="item in depositData.treasury_yields" 
          :key="item.tenor"
          class="yield-card"
        >
          <div class="tenor">{{ item.tenor }}</div>
          <div class="yield-value">{{ item.yield_display }}</div>
        </div>
      </div>
    </div>

    <div class="spread-section card">
      <h3 class="section-title">
        存款利率与国债利差分析
        <el-tooltip content="利差 = 存款利率 - 3年期国债收益率" placement="top">
          <el-icon class="info-icon"><i-ep-info-filled /></el-icon>
        </el-tooltip>
      </h3>
      
      <el-table 
        :data="depositData.spreads" 
        stripe
        style="width: 100%"
      >
        <el-table-column prop="bank" label="银行" width="120" />
        <el-table-column prop="product" label="产品" min-width="200" />
        <el-table-column prop="deposit_rate" label="存款利率 (%)" width="120" align="right">
          <template #default="{ row }">
            <span class="rate-value">{{ row.deposit_rate.toFixed(2) }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="treasury_yield" label="3Y国债 (%)" width="120" align="right">
          <template #default="{ row }">
            <span class="treasury-value">{{ row.treasury_yield.toFixed(2) }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="spread" label="利差 (%)" width="120" align="right">
          <template #default="{ row }">
            <span class="spread-value" :style="{ color: getSpreadColor(row.spread) }">
              {{ row.spread >= 0 ? '+' : '' }}{{ row.spread.toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="deposit-section card">
      <h3 class="section-title">各银行大额存单利率</h3>
      
      <el-table 
        :data="depositData.deposit_rates" 
        stripe
        style="width: 100%"
      >
        <el-table-column prop="bank" label="银行" width="120" />
        <el-table-column prop="product" label="产品" min-width="200" />
        <el-table-column prop="rate" label="利率" width="120" align="right">
          <template #default="{ row }">
            <span class="rate-value">{{ row.rate_display }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="empty-state" v-if="!loading && depositData.deposit_rates.length === 0">
      <p>暂无存款利率数据</p>
    </div>
  </div>
</template>

<style scoped>
.deposit-market {
  min-height: calc(100vh - 100px); /* Fallback for older browsers */
  min-height: calc(100dvh - 100px);
  padding: var(--spacing-md);
  background: var(--bg-system);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--border-line);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.header-left h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.update-time {
  font-size: 13px;
  color: var(--text-muted);
}

.header-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.card {
  background: var(--bg-card);
  border-radius: 8px;
  padding: var(--spacing-md);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  margin-bottom: var(--spacing-md);
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-md) 0;
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.info-icon {
  font-size: 16px;
  color: var(--text-muted);
  cursor: help;
}

.yield-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md);
}

@media (max-width: 768px) {
  .yield-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

.yield-card {
  background: var(--bg-system);
  border-radius: 8px;
  padding: var(--spacing-md);
  text-align: center;
}

.yield-card .tenor {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: var(--spacing-xs);
}

.yield-card .yield-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--brand-navy-dark);
  font-family: 'DIN Alternate', -apple-system, sans-serif;
}

.rate-value {
  font-weight: 600;
  color: var(--text-primary);
  font-family: 'DIN Alternate', -apple-system, sans-serif;
}

.treasury-value {
  font-weight: 600;
  color: var(--text-muted);
  font-family: 'DIN Alternate', -apple-system, sans-serif;
}

.spread-value {
  font-weight: 700;
  font-family: 'DIN Alternate', -apple-system, sans-serif;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
  color: var(--text-muted);
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-md);
  }
  
  .header-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
