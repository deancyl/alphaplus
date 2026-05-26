import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '首页宏观复盘' },
  },
  {
    path: '/fof/fundFilter',
    name: 'FundFilter',
    component: () => import('@/views/FundFilter.vue'),
    meta: { title: '基金筛选' },
  },
  {
    path: '/fof/fundCompare',
    name: 'FundCompare',
    component: () => import('@/views/FundCompare.vue'),
    meta: { title: '基金对比' },
  },
  {
    path: '/fof/fundSimilarity',
    name: 'FundSimilarity',
    component: () => import('@/views/FundSimilarity.vue'),
    meta: { title: '相似度计算' },
  },
  {
    path: '/fof/fundIssue',
    name: 'FundIssue',
    component: () => import('@/views/FundIssue.vue'),
    meta: { title: '基金发行' },
  },
  {
    path: '/fof/fundCompany',
    name: 'FundCompany',
    component: () => import('@/views/FundCompany.vue'),
    meta: { title: '基金公司' },
  },
  {
    path: '/info/stock',
    name: 'StockInfo',
    component: () => import('@/views/StockInfo.vue'),
    meta: { title: '股票行情' },
  },
  {
    path: '/info/bond',
    name: 'BondInfo',
    component: () => import('@/views/BondInfo.vue'),
    meta: { title: '债券行情' },
  },
  {
    path: '/info/futures',
    name: 'FuturesInfo',
    component: () => import('@/views/FuturesInfo.vue'),
    meta: { title: '期货行情' },
  },
  {
    path: '/market/globalMarket',
    name: 'GlobalMarket',
    component: () => import('@/views/GlobalMarket.vue'),
    meta: { title: '全球市场' },
  },
  {
    path: '/market/domesticStockMarket',
    name: 'DomesticStockMarket',
    component: () => import('@/views/DomesticStockMarket.vue'),
    meta: { title: 'A股市场' },
  },
  {
    path: '/market/domesticBondMarket',
    name: 'DomesticBondMarket',
    component: () => import('@/views/DomesticBondMarket.vue'),
    meta: { title: '债券市场' },
  },
  {
    path: '/market/fearGreed',
    name: 'FearGreed',
    component: () => import('@/views/FearGreed.vue'),
    meta: { title: '恐慌贪婪' },
  },
  {
    path: '/market/styleStrength',
    name: 'StyleStrength',
    component: () => import('@/views/StyleStrength.vue'),
    meta: { title: '风格强度' },
  },
  {
    path: '/market/erpSpread',
    name: 'ERPSpread',
    component: () => import('@/views/ERPSpread.vue'),
    meta: { title: '股债ERP' },
  },
  {
    path: '/market/marketCrowding',
    name: 'MarketCrowding',
    component: () => import('@/views/MarketCrowding.vue'),
    meta: { title: '拥挤度分析' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || 'Alpha+'} - 财富 Alpha+`
  next()
})

export default router
