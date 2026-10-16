import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { api } from '@/lib/api/client'
import ApiCheckPage from '@/app/dev/api-check/page'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn() } }))
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))

beforeEach(() => {
  vi.stubEnv('NODE_ENV', 'development')
  vi.mocked(api.GET).mockReset()
})

afterEach(() => {
  vi.unstubAllEnvs()
})

test('connection refused shows API unreachable without a status', async () => {
  vi.mocked(api.GET).mockRejectedValue(new TypeError('fetch failed'))

  render(await ApiCheckPage())

  expect(screen.getByText('API unreachable')).toBeDefined()
  expect(screen.queryByText(/\d{3}/)).toBeNull()
})

test('non-2xx shows API unreachable and the HTTP status', async () => {
  vi.mocked(api.GET).mockResolvedValue({
    error: { status: 'unavailable' },
    response: new Response(null, { status: 503 }),
  } as unknown as Awaited<ReturnType<typeof api.GET>>)

  render(await ApiCheckPage())

  expect(screen.getByText('API unreachable')).toBeDefined()
  expect(screen.getByText('HTTP 503')).toBeDefined()
})
