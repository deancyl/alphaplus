import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './assets/styles/main.css'

const app = createApp(App)

// Register all Element Plus icons globally
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// Global error handler
app.config.errorHandler = (err, instance, info) => {
  // Log error for debugging
  if (import.meta.env.DEV) {
    console.error('[Global Error]', err)
    console.error('[Error Info]', info)
    console.error('[Component]', instance?.$options?.name || 'Unknown')
  }
  
  // In production: could send to error tracking service
  // e.g., Sentry, LogRocket, etc.
  // if (import.meta.env.PROD) {
  //   Sentry.captureException(err)
  // }
  
  // Prevent app crash - error is handled
  // ErrorBoundary will catch and display fallback UI
}

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
  if (import.meta.env.DEV) {
    console.error('[Unhandled Promise Rejection]', event.reason)
  }
  // Prevent default behavior (logging to console)
  event.preventDefault()
})

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

app.mount('#app')
