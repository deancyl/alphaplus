<script setup lang="ts">
import { ref, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'

const router = useRouter()
const route = useRoute()

const menuItems = [
  {
    label: '首页',
    children: [
      { label: '宏观复盘看板', path: '/' },
    ],
  },
  {
    label: '公募基金',
    children: [
      { label: '基金筛选', path: '/fof/fundFilter' },
      { label: '基金对比', path: '/fof/fundCompare' },
      { label: '相似度计算', path: '/fof/fundSimilarity' },
      { label: '基金发行', path: '/fof/fundIssue' },
      { label: '基金公司', path: '/fof/fundCompany' },
    ],
  },
  {
    label: '行情资讯',
    children: [
      { label: '股票行情', path: '/info/stock' },
      { label: '债券行情', path: '/info/bond' },
      { label: '期货行情', path: '/info/futures' },
    ],
  },
  {
    label: '市场总览',
    children: [
      { label: '全球市场', path: '/market/globalMarket' },
      { label: 'A股市场', path: '/market/domesticStockMarket' },
      { label: '债券市场', path: '/market/domesticBondMarket' },
    ],
  },
  {
    label: '宏观研判',
    children: [
      { label: '恐慌贪婪指数', path: '/market/fearGreed' },
      { label: '风格强度', path: '/market/styleStrength' },
      { label: '股债ERP', path: '/market/erpSpread' },
      { label: '拥挤度分析', path: '/market/marketCrowding', isNew: true },
    ],
  },
]

const activeMenu = ref<string | null>(null)
const mobileMenuOpen = ref(false)
const expandedMobileMenu = ref<string | null>(null)
const hoverTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const leaveTimer = ref<ReturnType<typeof setTimeout> | null>(null)

// Detect touch device - skip debounce on touch devices
const isTouchDevice = ref(false)

// Check for touch capability on mount
if (typeof window !== 'undefined') {
  isTouchDevice.value = 'ontouchstart' in window || navigator.maxTouchPoints > 0
}

const handleMouseEnter = (menu: string) => {
  // Skip debounce on touch devices for immediate response
  if (isTouchDevice.value) {
    activeMenu.value = menu
    return
  }
  
  if (leaveTimer.value) {
    clearTimeout(leaveTimer.value)
    leaveTimer.value = null
  }
  hoverTimer.value = setTimeout(() => {
    activeMenu.value = menu
  }, 150)
}

const handleMouseLeave = () => {
  // Skip debounce on touch devices
  if (isTouchDevice.value) {
    activeMenu.value = null
    return
  }
  
  if (hoverTimer.value) {
    clearTimeout(hoverTimer.value)
    hoverTimer.value = null
  }
  leaveTimer.value = setTimeout(() => {
    activeMenu.value = null
  }, 200)
}

const toggleMobileMenu = () => {
  mobileMenuOpen.value = !mobileMenuOpen.value
  if (!mobileMenuOpen.value) {
    expandedMobileMenu.value = null
  }
}

const toggleMobileSubmenu = (label: string) => {
  expandedMobileMenu.value = expandedMobileMenu.value === label ? null : label
}

const navigateTo = (path: RouteLocationRaw) => {
  router.push(path)
  activeMenu.value = null
  mobileMenuOpen.value = false
  expandedMobileMenu.value = null
}

watch(() => route.path, () => {
  mobileMenuOpen.value = false
  expandedMobileMenu.value = null
})

onUnmounted(() => {
  if (hoverTimer.value) clearTimeout(hoverTimer.value)
  if (leaveTimer.value) clearTimeout(leaveTimer.value)
})
</script>

<template>
  <nav class="mega-menu">
    <div class="menu-brand">
      <span class="brand-text">财富 Alpha+</span>
    </div>
    
    <!-- Desktop Menu -->
    <div class="menu-items hide-mobile">
      <div
        v-for="item in menuItems"
        :key="item.label"
        class="menu-item"
        @mouseenter="handleMouseEnter(item.label)"
        @mouseleave="handleMouseLeave"
      >
        <span class="menu-label">{{ item.label }}</span>
        
        <Transition name="dropdown">
          <div
            v-if="activeMenu === item.label"
            class="dropdown-panel"
          >
            <div
              v-for="child in item.children"
              :key="child.path"
              class="dropdown-item"
              @click="navigateTo(child.path)"
            >
              <span>{{ child.label }}</span>
              <span v-if="child.isNew" class="new-badge">新</span>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Mobile Hamburger Button -->
    <button 
      class="hamburger-btn hide-tablet hide-desktop" 
      @click="toggleMobileMenu"
      :aria-expanded="mobileMenuOpen"
      aria-label="Toggle navigation menu"
    >
      <span class="hamburger-line" :class="{ 'active': mobileMenuOpen }"></span>
      <span class="hamburger-line" :class="{ 'active': mobileMenuOpen }"></span>
      <span class="hamburger-line" :class="{ 'active': mobileMenuOpen }"></span>
    </button>

    <!-- Mobile Menu Overlay -->
    <Transition name="fade">
      <div 
        v-if="mobileMenuOpen" 
        class="mobile-overlay" 
        @click="toggleMobileMenu"
      ></div>
    </Transition>

    <!-- Mobile Menu Drawer -->
    <Transition name="slide">
      <div v-if="mobileMenuOpen" class="mobile-drawer">
        <div class="mobile-drawer-header">
          <span class="brand-text">财富 Alpha+</span>
          <button class="close-btn" @click="toggleMobileMenu" aria-label="Close menu">
            <span>&times;</span>
          </button>
        </div>
        
        <div class="mobile-drawer-content">
          <div 
            v-for="item in menuItems" 
            :key="item.label" 
            class="mobile-menu-section"
          >
            <div 
              class="mobile-menu-title" 
              @click="toggleMobileSubmenu(item.label)"
            >
              <span>{{ item.label }}</span>
              <span class="expand-icon" :class="{ 'expanded': expandedMobileMenu === item.label }">
                ▼
              </span>
            </div>
            
            <Transition name="expand">
              <div v-if="expandedMobileMenu === item.label" class="mobile-submenu">
                <div
                  v-for="child in item.children"
                  :key="child.path"
                  class="mobile-menu-item"
                  @click="navigateTo(child.path)"
                >
                  <span>{{ child.label }}</span>
                  <span v-if="child.isNew" class="new-badge">新</span>
                </div>
              </div>
            </Transition>
          </div>
        </div>
      </div>
    </Transition>
  </nav>
</template>

<style scoped>
.mega-menu {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 var(--spacing-md);
  background-color: var(--brand-navy-dark);
  color: white;
}

.menu-brand {
  flex-shrink: 0;
}

.brand-text {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 1px;
}

.menu-items {
  display: flex;
  gap: 4px;
}

.menu-item {
  position: relative;
  padding: 0 12px;
  height: 48px;
  display: flex;
  align-items: center;
  cursor: pointer;
  transition: background-color 0.2s;
}

.menu-item:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.menu-label {
  font-size: 14px;
  font-weight: 500;
}

.dropdown-panel {
  position: absolute;
  top: 100%;
  left: 0;
  min-width: 160px;
  background-color: white;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 8px 0;
  z-index: 1000;
}

.dropdown-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  color: var(--text-regular);
  font-size: 13px;
  cursor: pointer;
  transition: background-color 0.15s;
}

.dropdown-item:hover {
  background-color: #f5f7fa;
  color: var(--brand-navy-active);
}

.dropdown-item:active {
  background-color: #e8eaef;
}

.new-badge {
  padding: 1px 6px;
  background-color: #F5222D;
  color: white;
  font-size: 11px;
  border-radius: 2px;
  margin-left: 4px;
}

/* Hamburger Button */
.hamburger-btn {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  width: 44px;
  height: 44px;
  padding: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  gap: 5px;
}

.hamburger-line {
  display: block;
  width: 22px;
  height: 2px;
  background: white;
  border-radius: 1px;
  transition: transform 0.3s, opacity 0.3s;
}

.hamburger-line.active:nth-child(1) {
  transform: translateY(7px) rotate(45deg);
}

.hamburger-line.active:nth-child(2) {
  opacity: 0;
}

.hamburger-line.active:nth-child(3) {
  transform: translateY(-7px) rotate(-45deg);
}

/* Mobile Overlay */
.mobile-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 998;
}

/* Mobile Drawer */
.mobile-drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: 280px;
  max-width: 85vw;
  height: 100vh;
  background: white;
  z-index: 999;
  overflow-y: auto;
  box-shadow: -4px 0 12px rgba(0, 0, 0, 0.15);
}

.mobile-drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  background: var(--brand-navy-dark);
  color: white;
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  color: white;
  font-size: 28px;
  cursor: pointer;
}

.mobile-drawer-content {
  padding: var(--spacing-sm) 0;
}

.mobile-menu-section {
  border-bottom: 1px solid var(--border-line);
}

.mobile-menu-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  font-weight: 600;
  color: var(--text-primary);
  cursor: pointer;
  min-height: 48px;
}

.mobile-menu-title:active {
  background-color: var(--bg-system);
}

.expand-icon {
  font-size: 10px;
  color: var(--text-muted);
  transition: transform 0.2s;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.mobile-submenu {
  background: var(--bg-system);
}

.mobile-menu-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  padding-left: calc(var(--spacing-md) + var(--spacing-md));
  color: var(--text-regular);
  font-size: 14px;
  cursor: pointer;
  min-height: 44px;
}

.mobile-menu-item:active {
  background-color: #e8eaef;
}

/* Dropdown transition */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* Fade transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Slide transition */
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}

/* Expand transition */
.expand-enter-active,
.expand-leave-active {
  transition: max-height 0.3s ease;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  max-height: 0;
}

.expand-enter-to,
.expand-leave-from {
  max-height: 300px;
}

/* Responsive */
@media (max-width: 768px) {
  .mega-menu {
    padding: 0 var(--spacing-sm);
  }
  
  .brand-text {
    font-size: 16px;
  }
}
</style>
