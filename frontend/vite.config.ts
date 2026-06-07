import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

delete process.env.http_proxy
delete process.env.HTTP_PROXY
delete process.env.https_proxy
delete process.env.HTTPS_PROXY

export default defineConfig({
  plugins: [vue()],
  css: {
    postcss: './postcss.config.js',
  },
  base: './',  // Relative path for portable deployment
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 60201,
    host: '0.0.0.0',
    strictPort: true,  // Fail if port occupied
    hmr: {
      overlay: false,  // Prevent error overlay crashes
      timeout: 30000,  // HMR connection timeout
    },
    watch: {
      usePolling: true,  // Better file watching in Docker/VM
      interval: 1000,
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:60200',
        changeOrigin: true,
        timeout: 30000,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    minify: 'terser',
    chunkSizeWarningLimit: 1500,  // Allow larger chunks
    rollupOptions: {
      output: {
        manualChunks: {
          'echarts': ['echarts', 'vue-echarts'],
          'element-plus': ['element-plus'],
          'vendor': ['vue', 'vue-router', 'pinia', 'axios'],
        },
      },
    },
  },
})
