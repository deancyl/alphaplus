<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterView } from 'vue-router'
import MegaMenu from '@/components/MegaMenu.vue'
import IndexBar from '@/components/IndexBar.vue'
import FavoritesDrawer from '@/components/FavoritesDrawer.vue'

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
  } catch (error) {
    console.error('Failed to load favorites count:', error)
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
  </div>
</template>

<style scoped>
.app-container {
  min-height: 100vh;
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
</style>
