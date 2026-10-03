import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// Public base path.
//   '/'          -> served at the site root (e.g. http://host:18085/)
//   '/pd-rehab/' -> served under a sub-path (e.g. https://ccqspace.site/pd-rehab/)
// Set VITE_BASE at build time; the same source produces either layout.
const base = process.env.VITE_BASE || '/'

// Where the dev server forwards API calls.
//
// Port 8000 is a popular default and this machine runs several projects; when
// another one already holds it, the proxy silently answers from the wrong
// application and every page renders empty rather than erroring. Override with
// `VITE_DEV_BACKEND=http://127.0.0.1:8010` when that happens.
const DEV_BACKEND = process.env.VITE_DEV_BACKEND || 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  base,
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
      // Both prefixes are proxied so the sub-path deployment can be tested locally.
      //
      // The backend port is overridable because 8000 is a busy default on a
      // machine running several projects; when something else already holds it,
      // the API quietly answers from the wrong application and the pages render
      // empty instead of failing loudly.
      '/api': {
        target: DEV_BACKEND,
        changeOrigin: true,
      },
      '/pd-rehab/api': {
        target: DEV_BACKEND,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/pd-rehab/, ''),
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
