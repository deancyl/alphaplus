<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterView } from 'vue-router'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import MegaMenu from '@/components/MegaMenu.vue'
import IndexBar from '@/components/IndexBar.vue'
import FavoritesDrawer from '@/components/FavoritesDrawer.vue'
import OmniSearch from '@/components/OmniSearch.vue'

const favoritesDrawerVisible = ref(false)
const favoritesCount = ref(0)

const STORAGE_KEY = 'alphaplus_favorites'

const loadFavoritesCount = () => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      favoritesCount.value = Object.values(parsed).reduce(
        (sum: number, arr: unknown) => sum + (Array.isArray(arr) ? arr.length : 0),
        0
      )
    }
  } catch {
    // Silently fail - favorites count is not critical
  }
}

const handleOpenFavorites = () => {
  favoritesDrawerVisible.value = true
}

onMounted(() => {
  loadFavoritesCount()
  // Listen for storage changes
  window.addEventListener('storage', loadFavoritesCount)
})
</script>

<template>
  <ErrorBoundary error-message="页面加载失败，请刷新重试">
    <div class="app-container">
      <header class="app-header">
        <MegaMenu @open-favorites="handleOpenFavorites" :favorites-count="favoritesCount" />
        <IndexBar />
      </header>
      
      <main class="app-main">
        <RouterView />
      </main>

      <FavoritesDrawer
        v-model:visible="favoritesDrawerVisible"
        @update:visible="favoritesDrawerVisible = $event"
      />
      
      <!-- Global OmniSearch (Ctrl+K) -->
      <OmniSearch />
      
      <!-- Footer -->
      <footer class="app-footer">
        <p>© 2024 财富 Alpha+ | 投资有风险，决策需谨慎</p>
      </footer>
    </div>
  </ErrorBoundary>
</template>

<style scoped>
.app-container {
  min-height: 100vh; /* Fallback for older browsers */
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-system);
}

.app-header {
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
  background-color: var(--brand-navy-dark);
}

.app-main {
  flex: 1;
  padding: var(--spacing-md);
  max-width: 1920px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

@media (max-width: 768px) {
  .app-main {
    padding: var(--spacing-sm);
  }
}

@media (max-width: 480px) {
  .app-main {
    padding: var(--spacing-xs);
  }
}

@media (min-width: 1400px) {
  .app-main {
    padding: var(--spacing-lg);
  }
}

.app-footer {
  background-color: var(--brand-navy-dark);
  padding: var(--spacing-md);
  text-align: center;
  color: var(--text-muted);
  font-size: var(--text-sm);
  margin-top: auto;
}

.app-footer p {
  margin: 0;
}
</style>
