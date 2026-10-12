// Serves the original tracked frontend for screenshot comparison without changing the working tree.
import { createServer } from '../frontend/node_modules/vite/dist/node/index.js'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const root = fileURLToPath(new URL('../', import.meta.url))
const frontend = path.join(root, 'frontend')
const reference = process.argv[2] ?? '92a8495a7761bf3b91aa6839c44fd3e7df5db3b4'
const server = await createServer({
  root: frontend,
  configFile: path.join(frontend, 'vite.config.ts'),
  cacheDir: path.join(frontend, 'node_modules', '.vite-before'),
  server: { host: '127.0.0.1', port: 5174, strictPort: true },
  plugins: [{
    name: 'original-source-for-comparison', enforce: 'pre',
    load(id) {
      const source = id.split('?')[0]
      if (id.includes('?') || !source.startsWith(path.join(frontend, 'src').replaceAll('\\', '/'))) return null
      try {
        return execFileSync('git', ['show', `${reference}:${path.relative(root, source).replaceAll('\\', '/')}`], { cwd: root, encoding: 'utf8', maxBuffer: 1024 * 1024 })
      } catch { return null }
    },
  }],
})
await server.listen()
console.log('Original frontend preview at http://127.0.0.1:5174')
