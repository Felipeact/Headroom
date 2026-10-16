import { configDefaults, defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    // Playwright owns e2e/; its *.spec.ts files would otherwise match Vitest's default pattern.
    exclude: [...configDefaults.exclude, 'e2e/**'],
  },
})
