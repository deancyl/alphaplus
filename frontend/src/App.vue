<script setup lang="ts">
import { RouterView } from 'vue-router'
import MegaMenu from '@/components/MegaMenu.vue'
import IndexBar from '@/components/IndexBar.vue'
</script>

<template>
  <div class="app-container">
    <header class="app-header">
      <MegaMenu />
      <IndexBar />
    </header>
    
    <main class="app-main">
      <RouterView />
    </main>
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
  z-index: 100;
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
