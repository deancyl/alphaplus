<script setup lang="ts">
import { computed } from 'vue'
import { ElCard, ElTag } from 'element-plus'
import { Clock } from '@element-plus/icons-vue'

interface Props {
  title: string
  description: string
  expectedRelease: string
}

const props = defineProps<Props>()

const badgeText = computed(() => `即将上线 - ${props.expectedRelease}`)
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center p-6">
    <ElCard class="max-w-lg w-full text-center shadow-lg">
      <div class="py-8 px-4">
        <!-- Icon -->
        <div class="mb-6">
          <ElIcon :size="64" class="text-amber-500">
            <Clock />
          </ElIcon>
        </div>

        <!-- Title -->
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white mb-4">
          {{ title }}
        </h1>

        <!-- Description -->
        <p class="text-gray-500 dark:text-gray-400 mb-6 leading-relaxed">
          {{ description }}
        </p>

        <!-- Badge -->
        <ElTag type="warning" size="large" effect="plain" class="text-base px-4 py-2">
          {{ badgeText }}
        </ElTag>
      </div>
    </ElCard>
  </div>
</template>

<style scoped>
/* Additional styling if needed */
</style>
