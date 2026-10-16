import { existsSync } from 'node:fs'
import { defineConfig, devices } from '@playwright/test'

// Clerk keys and the test user (spec 10) live in .env.local, which CI does not have.
if (existsSync('.env.local')) process.loadEnvFile('.env.local')

// Spec 26 C34: the dashboard's render time, measured on the production build (`npm run start`),
// because the dev server compiles each route on its first request. Run with
// `npx playwright test -c playwright.perf.config.ts`.
export default defineConfig({
  testDir: './e2e',
  testMatch: /global\.setup\.ts|dashboard\.perf\.ts/,
  workers: 1,
  reporter: 'list',
  use: { baseURL: 'http://localhost:3100' },
  projects: [
    { name: 'setup', testMatch: /global\.setup\.ts/ },
    {
      name: 'perf',
      testMatch: /dashboard\.perf\.ts/,
      use: { ...devices['Desktop Chrome'] },
      dependencies: ['setup'],
    },
  ],
  webServer: [
    {
      command: 'npm run build && npm run start -- --port 3100',
      url: 'http://localhost:3100',
      // Never a dev server left on the port: the measurement is of the production build.
      reuseExistingServer: false,
      timeout: 300_000,
      env: { API_URL: 'http://localhost:8100' },
    },
    {
      command: 'uv run fastapi dev app/main.py --port 8100',
      cwd: '../services/core',
      url: 'http://localhost:8100/healthz/live',
      reuseExistingServer: false,
      // Session tokens from the production build carry azp http://localhost:3100; this local test
      // API accepts that origin beside the dev server's (process env beats .env.local).
      env: { CLERK_AUTHORIZED_PARTIES: 'http://localhost:3000,http://localhost:3100' },
    },
  ],
})
