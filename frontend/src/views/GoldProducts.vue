<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import EChartsWrapper from '@/components/EChartsWrapper.vue'
import { useBreakpoint } from '@/composables/useBreakpoint'
import type { EChartsOption } from 'echarts'

interface GoldSpotData {
  shanghai_gold: {
    price: number
    unit: string
    source: string
  }
  london_gold: {
    price: number
    unit: string
    source: string
  }
  spread: {
    absolute: number
    percentage: number
    note: string
  }
  timestamp: string
  is_simulated: boolean
}

interface GoldHistoryItem {
  date: string
  shanghai_price: number
  london_price: number
  spread_pct: number
}

interface GoldHistoryData {
  history: GoldHistoryItem[]
  total: number
  is_simulated: boolean
}

// Responsive breakpoint
const { isMobile } = useBreakpoint()

// Reactive state
const loading = ref(false)
const goldData = ref<GoldSpotData | null>(null)
const historyData = ref<GoldHistoryItem[]>([])

// Computed chart options - Dual Y-axis configuration
const chartOptions = computed(() => {
  if (historyData.value.length === 0) {
    return {
      title: { text: '黄金价格走势', left: 'center' },
      xAxis: { type: 'category' as const, data: [] },
      yAxis: [
        { type: 'value' as const, name: '上海金 (CNY/g)' },
        { type: 'value' as const, name: '伦敦金 (USD/oz)' }
      ],
      series: []
    }
  }

  const dates = historyData.value.map(h => h.date)
  const shanghaiPrices = historyData.value.map(h => h.shanghai_price)
  const londonPrices = historyData.value.map(h => h.london_price)
  const spreadPcts = historyData.value.map(h => h.spread_pct)

  return {
    title: {
      text: '黄金价格走势',
      left: 'center',
      textStyle: {
        fontSize: isMobile.value ? 14 : 16,
        fontWeight: 600,
        color: '#1A1A1A'
      }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#E5E8ED',
      borderWidth: 1,
      textStyle: { color: '#1A1A1A' },
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        const idx = params[0].dataIndex
        const date = dates[idx]
        const shanghai = shanghaiPrices[idx]
        const london = londonPrices[idx]
        const spread = spreadPcts[idx]
        
        return `
          <div style="font-weight: 600; margin-bottom: 8px;">${date}</div>
          <div style="margin-bottom: 4px;">
            <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#1565C0;margin-right:6px;"></span>
            上海金: <strong>${shanghai.toFixed(2)}</strong> CNY/g
          </div>
          <div style="margin-bottom: 4px;">
            <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#FF9800;margin-right:6px;"></span>
            伦敦金: <strong>${london.toFixed(2)}</strong> USD/oz
          </div>
          <div>
            <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#E63935;margin-right:6px;"></span>
            溢价率: <strong>${spread?.toFixed(2) ?? '0.00'}%</strong>
          </div>
        `
      }
    },
    legend: {
      data: ['上海金', '伦敦金', '溢价率'],
      top: 30,
      textStyle: { fontSize: isMobile.value ? 11 : 12 }
    },
    grid: {
      left: isMobile.value ? '8%' : '3%',
      right: isMobile.value ? '8%' : '4%',
      bottom: isMobile.value ? '18%' : '12%',
      top: '18%',
      containLabel: true
    },
    xAxis: {
      type: 'category' as const,
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#E5E8ED' } },
      axisLabel: { 
        color: '#4A4A4A', 
        fontSize: isMobile.value ? 10 : 11,
        rotate: isMobile.value ? 45 : 0
      }
    },
    yAxis: [
      {
        type: 'value' as const,
        name: isMobile.value ? '' : '上海金 (CNY/g)',
        position: 'left',
        nameTextStyle: { color: '#1565C0', fontSize: 11 },
        splitLine: { lineStyle: { color: '#E5E8ED', type: 'dashed' } },
        axisLine: { show: true, lineStyle: { color: '#1565C0' } },
        axisLabel: { color: '#1565C0', fontSize: isMobile.value ? 10 : 11 }
      },
      {
        type: 'value' as const,
        name: isMobile.value ? '' : '伦敦金 (USD/oz)',
        position: 'right',
        nameTextStyle: { color: '#FF9800', fontSize: 11 },
        splitLine: { show: false },
        axisLine: { show: true, lineStyle: { color: '#FF9800' } },
        axisLabel: { color: '#FF9800', fontSize: isMobile.value ? 10 : 11 }
      }
    ],
    series: [
      {
        name: '上海金',
        type: 'line' as const,
        yAxisIndex: 0,
        data: shanghaiPrices,
        smooth: true,
        symbol: 'circle',
        symbolSize: isMobile.value ? 4 : 6,
        lineStyle: { width: 2.5, color: '#1565C0' },
        itemStyle: { color: '#1565C0' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(21, 101, 192, 0.25)' },
              { offset: 1, color: 'rgba(21, 101, 192, 0.02)' }
            ]
          }
        }
      },
      {
        name: '伦敦金',
        type: 'line' as const,
        yAxisIndex: 1,
        data: londonPrices,
        smooth: true,
        symbol: 'circle',
        symbolSize: isMobile.value ? 4 : 6,
        lineStyle: { width: 2.5, color: '#FF9800' },
        itemStyle: { color: '#FF9800' }
      },
      {
        name: '溢价率',
        type: 'line' as const,
        yAxisIndex: 0,
        data: spreadPcts,
        smooth: true,
        symbol: 'circle',
        symbolSize: isMobile.value ? 3 : 4,
        lineStyle: { width: 1.5, color: '#E63935', type: 'dashed' },
        itemStyle: { color: '#E63935' },
        markLine: {
          silent: true,
          data: [
            { 
              yAxis: 0, 
              label: { 
                formatter: '平价线',
                position: 'insideEndTop',
                fontSize: isMobile.value ? 10 : 11
              },
              lineStyle: { color: '#999', type: 'solid', width: 1 }
            }
          ]
        },
        markArea: {
          silent: true,
          data: [
            [
              { 
                yAxis: 0.5, 
                name: '低溢价区',
                itemStyle: { color: 'rgba(46, 125, 50, 0.15)' }
              },
              { yAxis: 1.0 }
            ],
            [
              { 
                yAxis: 1.5, 
                name: '高溢价区',
                itemStyle: { color: 'rgba(230, 57, 53, 0.15)' }
              },
              { yAxis: 2.0 }
            ]
          ]
        }
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0],
        filterMode: 'none',
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        moveOnMouseWheel: true,
        preventDefaultMouseMove: false
      },
      {
        type: 'slider',
        xAxisIndex: [0],
        show: !isMobile.value,
        bottom: 10,
        height: 20,
        start: 70,
        end: 100,
        borderColor: 'transparent',
        backgroundColor: 'rgba(0, 0, 0, 0.05)',
        fillerColor: 'rgba(0, 0, 0, 0.1)',
        handleStyle: {
          color: '#1565C0',
          borderColor: '#1565C0'
        },
        textStyle: {
          color: '#4A4A4A'
        }
      }
    ]
  } as EChartsOption
})

// Fetch gold spot price
const fetchGoldData = async () => {
  loading.value = true
  try {
    const response = await axios.get<GoldSpotData>('/api/v1/gold/spot-price')
    goldData.value = response.data
    
    if (response.data.is_simulated) {
      ElMessage.warning('黄金数据暂时不可用，显示模拟数据')
    }
  } catch (error) {
    ElMessage.error('获取黄金价格失败')
  } finally {
    loading.value = false
  }
}

// Fetch gold price history
const fetchHistoryData = async () => {
  try {
    const response = await axios.get<GoldHistoryData>('/api/v1/gold/history?days=30')
    historyData.value = response.data.history
  } catch (error) {
  }
}

// Format timestamp
const formatTime = (timestamp: string): string => {
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// Refresh all data
const refreshData = async () => {
  await Promise.all([fetchGoldData(), fetchHistoryData()])
}

onMounted(() => {
  refreshData()
})
</script>

<template>
  <div class="gold-products" v-loading="loading">
    <!-- Header -->
    <div class="page-header">
      <h2>黄金产品跟踪</h2>
      <div class="header-actions">
        <el-button type="primary" size="small" @click="refreshData" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <span class="update-time" v-if="goldData">
          更新时间: {{ formatTime(goldData.timestamp) }}
        </span>
      </div>
    </div>

    <!-- Current Prices -->
    <div class="price-cards" v-if="goldData">
      <div class="price-card shanghai">
        <div class="card-header">
          <h3>上海金 (Au99.99)</h3>
          <el-tag size="small" type="info">{{ goldData.shanghai_gold.source }}</el-tag>
        </div>
        <div class="card-price">
          <span class="price-value">{{ goldData.shanghai_gold.price.toFixed(2) }}</span>
          <span class="price-unit">{{ goldData.shanghai_gold.unit }}</span>
        </div>
        <div class="card-note">
          上海黄金交易所现货价格
        </div>
      </div>

      <div class="price-card london">
        <div class="card-header">
          <h3>伦敦金 (LBMA)</h3>
          <el-tag size="small" type="warning">{{ goldData.london_gold.source }}</el-tag>
        </div>
        <div class="card-price">
          <span class="price-value">{{ goldData.london_gold.price.toFixed(2) }}</span>
          <span class="price-unit">{{ goldData.london_gold.unit }}</span>
        </div>
        <div class="card-note">
          已按汇率折算为人民币
        </div>
      </div>

      <div class="price-card spread">
        <div class="card-header">
          <h3>价差分析</h3>
          <el-tag size="small" :type="goldData.spread.absolute > 0 ? 'success' : 'danger'">
            {{ goldData.spread.absolute > 0 ? '溢价' : '折价' }}
          </el-tag>
        </div>
        <div class="card-price">
          <span class="price-value" :class="{ positive: goldData.spread.absolute > 0, negative: goldData.spread.absolute < 0 }">
            {{ goldData.spread.absolute > 0 ? '+' : '' }}{{ goldData.spread.absolute.toFixed(2) }}
          </span>
          <span class="price-unit">元/克</span>
        </div>
        <div class="card-note">
          溢价率: {{ goldData.spread.percentage.toFixed(2) }}%
        </div>
      </div>
    </div>

    <!-- Data Quality Notice -->
    <div class="data-notice" v-if="goldData?.is_simulated">
      <el-alert
        title="模拟数据"
        type="warning"
        description="当前显示模拟数据，AkShare 数据源暂时不可用。实际价格请参考官方渠道。"
        show-icon
        :closable="false"
      />
    </div>

    <!-- Price History Chart -->
    <div class="chart-section card">
      <div class="card-title">价格走势 (近30天)</div>
      <EChartsWrapper 
        :option="chartOptions" 
        height="400px"
      />
    </div>

    <!-- Product Information -->
    <div class="info-section">
      <div class="info-card card">
        <div class="card-title">产品说明</div>
        <div class="info-content">
          <div class="info-item">
            <span class="info-label">上海金:</span>
            <span class="info-value">上海黄金交易所 Au99.99 现货黄金，纯度 99.99%</span>
          </div>
          <div class="info-item">
            <span class="info-label">伦敦金:</span>
            <span class="info-value">伦敦金银市场协会 (LBMA) 现货黄金，已按实时汇率折算</span>
          </div>
          <div class="info-item">
            <span class="info-label">价差:</span>
            <span class="info-value">上海金与伦敦金的价差，反映国内黄金市场溢价情况</span>
          </div>
        </div>
      </div>

      <div class="info-card card">
        <div class="card-title">投资提示</div>
        <div class="info-content">
          <ul class="tips-list">
            <li>黄金具有避险属性，适合资产配置中的防御性资产</li>
            <li>价差受汇率、关税、供需关系等因素影响</li>
            <li>投资有风险，决策需谨慎</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.gold-products {
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

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.update-time {
  font-size: 13px;
  color: var(--text-muted);
}

/* Price Cards */
.price-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.price-card {
  background: var(--bg-card);
  border-radius: 8px;
  padding: var(--spacing-lg);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
}

.price-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.price-card.shanghai {
  border-left: 4px solid #1565C0;
}

.price-card.london {
  border-left: 4px solid #FF9800;
}

.price-card.spread {
  border-left: 4px solid #2E7D32;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
}

.card-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.card-price {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: var(--spacing-sm);
}

.price-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  font-family: 'DIN Alternate', -apple-system, sans-serif;
}

.price-value.positive {
  color: #2E7D32;
}

.price-value.negative {
  color: #E63935;
}

.price-unit {
  font-size: 13px;
  color: var(--text-muted);
}

.card-note {
  font-size: 12px;
  color: var(--text-muted);
}

/* Data Notice */
.data-notice {
  margin-bottom: var(--spacing-lg);
}

/* Chart Section */
.chart-section {
  background: var(--bg-card);
  border-radius: 8px;
  padding: var(--spacing-md);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  margin-bottom: var(--spacing-lg);
  touch-action: pan-y pinch-zoom;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-sm);
  border-bottom: 1px solid var(--border-line);
}

/* Info Section */
.info-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
}

.info-card {
  background: var(--bg-card);
  border-radius: 8px;
  padding: var(--spacing-md);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.info-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.info-item {
  display: flex;
  gap: var(--spacing-sm);
  font-size: 13px;
  line-height: 1.6;
}

.info-label {
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

.info-value {
  color: var(--text-secondary);
}

.tips-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--text-secondary);
}

.tips-list li {
  margin-bottom: 4px;
}

/* Responsive */
@media (max-width: 1200px) {
  .price-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .header-actions {
    width: 100%;
    justify-content: space-between;
  }
  
  .price-cards {
    grid-template-columns: 1fr;
  }
  
  .info-section {
    grid-template-columns: 1fr;
  }
  
  .price-value {
    font-size: 28px;
  }
}
</style>
