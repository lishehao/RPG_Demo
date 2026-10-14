import {defineConfig} from 'vitest/config'
import react from '@vitejs/plugin-react'

// Local-only dev server. No proxy to any production service is configured.
export default defineConfig({
  plugins: [react()],
  server: {host: '127.0.0.1', port: 5173, strictPort: true},
  preview: {host: '127.0.0.1', port: 4173, strictPort: true},
  build: {target: 'es2022', chunkSizeWarningLimit: 1200, sourcemap: false},
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.ts', 'tests/**/*.test.tsx'],
    setupFiles: ['tests/setup.ts'],
  },
})
