<script setup lang="ts">
/**
 * 404 页面 —— 沿用 research-terminal 的错误态三段式：
 *   标题（说明发生了什么）→ 细节（真实原因）→ 动作（如何离开）。
 * 不用插画、不编造原因：路径就是真实原因。
 */
import { useRoute, useRouter } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()
const router = useRouter()

const missedPath = computed(() => {
  const p = route.params.pathMatch
  return Array.isArray(p) ? '/' + p.join('/') : String(p || '')
})

const goHome = () => router.push('/')
const goBack = () => router.back()
</script>

<template>
  <div class="not-found">
    <div class="state-card" role="alert">
      <p class="state-title">页面不存在</p>
      <p class="state-detail">未找到 <code>{{ missedPath }}</code> 对应的页面，可能链接已失效或路径拼写有误。</p>
      <div class="state-actions">
        <button class="btn btn-primary" type="button" @click="goHome">返回首页</button>
        <button class="btn btn-ghost" type="button" @click="goBack">返回上一页</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 50vh;
  padding: var(--spacing-lg);
}

.state-card {
  max-width: 560px;
  width: 100%;
  background: var(--bg-card);
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  padding: var(--spacing-xl);
  text-align: center;
}

.state-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-sm);
}

.state-detail {
  font-size: 13px;
  color: var(--text-regular);
  line-height: 1.6;
  margin-bottom: var(--spacing-lg);
  word-break: break-all;
}

.state-detail code {
  font-family: var(--font-mono, 'SF Mono', 'Courier New', monospace);
  background: var(--bg-system);
  padding: 1px 6px;
  border-radius: 3px;
  color: var(--brand-navy-active);
}

.state-actions {
  display: flex;
  gap: var(--spacing-sm);
  justify-content: center;
}

.state-actions .btn {
  min-height: var(--touch-target-min);
  padding: 0 20px;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
}

.btn-primary {
  background: var(--brand-navy-dark);
  border: 1px solid var(--brand-navy-dark);
  color: #fff;
}

.btn-primary:hover {
  background: var(--brand-navy-active);
}

.btn-ghost {
  background: transparent;
  border: 1px solid var(--border-line);
  color: var(--text-regular);
}

.btn-ghost:hover {
  border-color: var(--brand-navy-active);
  color: var(--brand-navy-active);
}
</style>
