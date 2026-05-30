<script setup lang="ts">
/**
 * OmniSearch Component
 * 
 * Global command panel with Ctrl+K hotkey for fund search.
 * Features:
 * - 250ms debounce on search input
 * - LRU cache for 20 recent searches (localStorage)
 * - Keyboard navigation (ArrowUp/Down, Enter, Esc)
 * - Fund search using existing /fund/filter API
 * - Result limit: 15 items for 10ms response time
 * 
 * Design System Compliance:
 * - Uses CSS variables for all colors/spacing
 * - WCAG 44px touch target for result items
 * - Backdrop blur for modern visual aesthetic
 * 
 * @example
 * <OmniSearch />
 */

import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { filterFunds, type FundItem } from '@/api/fund'
import { useDebounce } from '@/composables/useDebounce'

// ==================== Types ====================

interface RecentSearch {
  fundCode: string
  fundName: string
  fundType: string
  timestamp: number
}

// ==================== Constants ====================

const LRU_MAX_SIZE = 20
const SEARCH_RESULT_LIMIT = 15
const STORAGE_KEY = 'omnisearch-history'

// ==================== State ====================

const isVisible = ref(false)
const searchQuery = ref('')
const searchResults = ref<FundItem[]>([])
const recentSearches = ref<RecentSearch[]>([])
const selectedIndex = ref(0)
const isLoading = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

const router = useRouter()

// ==================== Computed ====================

const hasResults = computed(() => searchResults.value.length > 0)
const hasRecentSearches = computed(() => recentSearches.value.length > 0)
const showRecentSearches = computed(() => !searchQuery.value && hasRecentSearches.value)

// ==================== LRU Cache Implementation ====================

const loadRecentSearches = (): void => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      recentSearches.value = JSON.parse(stored)
    }
  } catch {
    recentSearches.value = []
  }
}

const saveRecentSearches = (): void => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(recentSearches.value))
  } catch {
    // Storage quota exceeded or unavailable
  }
}

const addToRecentSearches = (fund: FundItem): void => {
  // Remove if already exists
  const existingIndex = recentSearches.value.findIndex(r => r.fundCode === fund.fund_code)
  if (existingIndex !== -1) {
    recentSearches.value.splice(existingIndex, 1)
  }
  
  // Add to front
  recentSearches.value.unshift({
    fundCode: fund.fund_code,
    fundName: fund.fund_name,
    fundType: fund.fund_type,
    timestamp: Date.now()
  })
  
  // Enforce LRU max size
  if (recentSearches.value.length > LRU_MAX_SIZE) {
    recentSearches.value = recentSearches.value.slice(0, LRU_MAX_SIZE)
  }
  
  saveRecentSearches()
}

const clearRecentSearches = (): void => {
  recentSearches.value = []
  saveRecentSearches()
}

// ==================== Search Logic ====================

const performSearch = async (query: string): Promise<void> => {
  if (!query.trim()) {
    searchResults.value = []
    return
  }
  
  isLoading.value = true
  
  try {
    // Use existing filter API - no search parameter available
    // Fetch first page and filter results client-side for MVP
    const response = await filterFunds({
      page: 1,
      page_size: 200
    })
    
    if (response && response.funds) {
      // Client-side search on fund code and name
      const searchTerm = query.toLowerCase()
      const filtered = response.funds.filter(fund => 
        fund.fund_code.toLowerCase().includes(searchTerm) ||
        fund.fund_name.toLowerCase().includes(searchTerm)
      )
      
      // Limit to 15 results for 10ms response time
      searchResults.value = filtered.slice(0, SEARCH_RESULT_LIMIT)
      selectedIndex.value = 0
    }
  } catch {
    searchResults.value = []
  } finally {
    isLoading.value = false
  }
}

// Debounced search (250ms)
const debouncedSearch = useDebounce(performSearch, 250)

// ==================== Event Handlers ====================

const openModal = (): void => {
  isVisible.value = true
  selectedIndex.value = 0
  nextTick(() => {
    inputRef.value?.focus()
  })
}

const closeModal = (): void => {
  isVisible.value = false
  searchQuery.value = ''
  searchResults.value = []
  selectedIndex.value = 0
}

const handleInput = (): void => {
  if (searchQuery.value.trim()) {
    debouncedSearch(searchQuery.value)
  } else {
    debouncedSearch.cancel()
    searchResults.value = []
  }
}

const handleKeydown = (event: KeyboardEvent): void => {
  const totalItems = hasResults.value 
    ? searchResults.value.length 
    : showRecentSearches.value 
      ? recentSearches.value.length 
      : 0
  
  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      if (totalItems > 0) {
        selectedIndex.value = (selectedIndex.value + 1) % totalItems
      }
      break
      
    case 'ArrowUp':
      event.preventDefault()
      if (totalItems > 0) {
        selectedIndex.value = selectedIndex.value === 0 
          ? totalItems - 1 
          : selectedIndex.value - 1
      }
      break
      
    case 'Enter':
      event.preventDefault()
      if (hasResults.value && searchResults.value[selectedIndex.value]) {
        selectFund(searchResults.value[selectedIndex.value])
      } else if (showRecentSearches.value && recentSearches.value[selectedIndex.value]) {
        const recent = recentSearches.value[selectedIndex.value]
        navigateToFund(recent.fundCode, recent.fundName, recent.fundType)
      }
      break
      
    case 'Escape':
      event.preventDefault()
      closeModal()
      break
  }
}

const selectFund = (fund: FundItem): void => {
  addToRecentSearches(fund)
  navigateToFund(fund.fund_code, fund.fund_name, fund.fund_type)
}

const navigateToFund = (fundCode: string, _fundName: string, _fundType: string): void => {
  closeModal()
  router.push({
    name: 'FundDetail',
    params: { fundCode }
  })
}

const handleBackdropClick = (event: MouseEvent): void => {
  if (event.target === event.currentTarget) {
    closeModal()
  }
}

// ==================== Global Hotkey ====================

const handleGlobalKeydown = (event: KeyboardEvent): void => {
  // Ctrl+K or Cmd+K
  if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
    event.preventDefault()
    if (isVisible.value) {
      closeModal()
    } else {
      openModal()
    }
  }
}

// ==================== Lifecycle ====================

onMounted(() => {
  loadRecentSearches()
  document.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleGlobalKeydown)
})
</script>

<template>
  <!-- Modal Overlay with Backdrop Blur -->
  <Transition name="modal-fade">
    <div
      v-if="isVisible"
      class="omnisearch-overlay"
      @click="handleBackdropClick"
    >
      <div class="omnisearch-modal">
        <!-- Search Input -->
        <div class="search-header">
          <div class="search-input-wrapper">
            <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            <input
              ref="inputRef"
              v-model="searchQuery"
              type="text"
              class="search-input"
              placeholder="搜索基金代码或名称..."
              inputmode="search"
              @input="handleInput"
              @keydown="handleKeydown"
            />
            <span class="search-hint">
              <kbd>ESC</kbd> 关闭
            </span>
          </div>
        </div>
        
        <!-- Results Section -->
        <div class="search-content">
          <!-- Loading State -->
          <div v-if="isLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <span>搜索中...</span>
          </div>
          
          <!-- Search Results -->
          <div v-else-if="hasResults" class="results-list">
            <div class="results-header">
              <span>搜索结果</span>
              <span class="results-count">{{ searchResults.length }} 只基金</span>
            </div>
            
            <div
              v-for="(fund, index) in searchResults"
              :key="fund.fund_code"
              class="result-item"
              :class="{ 'selected': index === selectedIndex }"
              @click="selectFund(fund)"
              @mouseenter="selectedIndex = index"
            >
              <div class="result-main">
                <span class="result-code">{{ fund.fund_code }}</span>
                <span class="result-name">{{ fund.fund_name }}</span>
              </div>
              <span class="result-type">{{ fund.fund_type }}</span>
            </div>
          </div>
          
          <!-- Recent Searches -->
          <div v-else-if="showRecentSearches" class="results-list">
            <div class="results-header">
              <span>最近搜索</span>
              <button class="clear-btn" @click="clearRecentSearches">
                清空
              </button>
            </div>
            
            <div
              v-for="(recent, index) in recentSearches"
              :key="recent.fundCode"
              class="result-item"
              :class="{ 'selected': index === selectedIndex }"
              @click="navigateToFund(recent.fundCode, recent.fundName, recent.fundType)"
              @mouseenter="selectedIndex = index"
            >
              <div class="result-main">
                <span class="result-code">{{ recent.fundCode }}</span>
                <span class="result-name">{{ recent.fundName }}</span>
              </div>
              <span class="result-type">{{ recent.fundType }}</span>
            </div>
          </div>
          
          <!-- Empty State -->
          <div v-else-if="searchQuery && !isLoading && !hasResults" class="empty-state">
            <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
              <path d="M8 8l6 6M14 8l-6 6" />
            </svg>
            <span>未找到相关基金</span>
            <span class="empty-hint">请尝试其他关键词</span>
          </div>
          
          <!-- Initial Empty State -->
          <div v-else-if="!searchQuery && !hasRecentSearches" class="empty-state initial">
            <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            <span>输入基金代码或名称开始搜索</span>
            <span class="empty-hint">按 <kbd>Ctrl</kbd>+<kbd>K</kbd> 快速打开</span>
          </div>
        </div>
        
        <!-- Footer with Keyboard Hints -->
        <div class="search-footer">
          <div class="hint-group">
            <span class="hint">
              <kbd>↑</kbd><kbd>↓</kbd> 导航
            </span>
            <span class="hint">
              <kbd>Enter</kbd> 选择
            </span>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* ==================== Overlay & Modal ==================== */

.omnisearch-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: var(--z-modal);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 15vh;
}

.omnisearch-modal {
  width: 100%;
  max-width: 640px;
  margin: 0 var(--spacing-md);
  background: var(--bg-card);
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 70vh;
}

/* ==================== Search Header ==================== */

.search-header {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-line);
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  background: var(--bg-system);
  border-radius: 8px;
  padding: 0 var(--spacing-md);
}

.search-icon {
  width: 20px;
  height: 20px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 16px;
  color: var(--text-primary);
  padding: var(--spacing-md) 0;
  outline: none;
}

.search-input::placeholder {
  color: var(--text-muted);
}

.search-hint {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.search-hint kbd {
  display: inline-block;
  padding: 2px 6px;
  background: var(--bg-card);
  border: 1px solid var(--border-line);
  border-radius: 4px;
  font-family: inherit;
  font-size: 11px;
  margin-right: 4px;
}

/* ==================== Search Content ==================== */

.search-content {
  flex: 1;
  overflow-y: auto;
  min-height: 200px;
  max-height: 50vh;
}

.results-list {
  padding: var(--spacing-sm) 0;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.results-count {
  font-weight: 400;
}

.clear-btn {
  background: none;
  border: none;
  color: var(--brand-navy-active);
  font-size: 12px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background-color 0.15s;
}

.clear-btn:hover {
  background: var(--bg-system);
}

/* ==================== Result Items ==================== */

.result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  cursor: pointer;
  transition: background-color 0.15s;
  border-left: 3px solid transparent;
  min-height: var(--touch-target-min);
  touch-action: manipulation;
}

.result-item:hover,
.result-item.selected {
  background: var(--bg-system);
}

.result-item.selected {
  border-left-color: var(--brand-navy-active);
}

.result-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}

.result-code {
  font-size: 13px;
  font-weight: 600;
  color: var(--brand-navy-active);
}

.result-name {
  font-size: 14px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-type {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-system);
  padding: 4px 8px;
  border-radius: 4px;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ==================== Loading & Empty States ==================== */

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  color: var(--text-muted);
  gap: var(--spacing-sm);
  min-height: 200px;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-line);
  border-top-color: var(--brand-navy-active);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.empty-icon {
  width: 48px;
  height: 48px;
  color: var(--text-muted);
  opacity: 0.5;
}

.empty-state span {
  font-size: 14px;
}

.empty-hint {
  font-size: 12px !important;
  opacity: 0.7;
}

.empty-hint kbd {
  display: inline-block;
  padding: 2px 6px;
  background: var(--bg-system);
  border: 1px solid var(--border-line);
  border-radius: 4px;
  font-family: inherit;
  font-size: 11px;
}

/* ==================== Footer ==================== */

.search-footer {
  padding: var(--spacing-sm) var(--spacing-md);
  border-top: 1px solid var(--border-line);
  background: var(--bg-system);
}

.hint-group {
  display: flex;
  gap: var(--spacing-lg);
}

.hint {
  font-size: 12px;
  color: var(--text-muted);
}

.hint kbd {
  display: inline-block;
  padding: 2px 6px;
  background: var(--bg-card);
  border: 1px solid var(--border-line);
  border-radius: 4px;
  font-family: inherit;
  font-size: 11px;
  margin-right: 4px;
}

/* ==================== Transitions ==================== */

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-active .omnisearch-modal,
.modal-fade-leave-active .omnisearch-modal {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-from .omnisearch-modal {
  transform: translateY(-20px) scale(0.95);
  opacity: 0;
}

.modal-fade-leave-to .omnisearch-modal {
  transform: translateY(-10px) scale(0.98);
  opacity: 0;
}

/* ==================== Responsive ==================== */

@media (max-width: 768px) {
  .omnisearch-overlay {
    padding-top: 10vh;
    align-items: flex-start;
  }
  
  .omnisearch-modal {
    margin: 0 var(--spacing-sm);
    max-height: 80vh;
    border-radius: 8px;
  }
  
  .search-input {
    font-size: 16px; /* Prevent iOS zoom */
  }
  
  .search-hint {
    display: none;
  }
  
  .result-name {
    font-size: 13px;
  }
  
  .hint-group {
    flex-wrap: wrap;
    gap: var(--spacing-sm);
  }
}

@media (max-width: 480px) {
  .omnisearch-modal {
    margin: 0;
    border-radius: 0;
    max-height: 100dvh;
    width: 100vw;
  }
  
  .omnisearch-overlay {
    padding-top: 0;
  }
  
  .search-content {
    max-height: calc(100dvh - 140px);
  }
}
</style>
