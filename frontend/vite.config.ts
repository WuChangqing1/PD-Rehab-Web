import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      // Keeps the browser on one origin during development, so the dev server
      // stays a Secure Context (localhost) and camera APIs remain available.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        // Function form: object form is not part of the current Rollup types.
        manualChunks(id: string) {
          if (id.includes('node_modules')) {
            if (id.includes('echarts') || id.includes('zrender')) return 'charts'
            if (id.includes('element-plus') || id.includes('@element-plus')) return 'element'
            if (
              id.includes('/vue/') ||
              id.includes('vue-router') ||
              id.includes('pinia') ||
              id.includes('@vue/')
            ) {
              return 'vue'
            }
          }
          return undefined
        },
      },
    },
  },
})
