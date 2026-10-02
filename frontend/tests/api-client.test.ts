// @vitest-environment node
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

// `server-only` throws outside a React Server Components build, which Vitest is not.
vi.mock('server-only', () => ({}))

beforeEach(() => {
  vi.resetModules()
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

test('sends to API_URL', async () => {
  vi.stubEnv('API_URL', 'http://api.test:9999')
  const fakeFetch = vi.fn(
    async () =>
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
  )
  vi.stubGlobal('fetch', fakeFetch)
  const { api } = await import('@/lib/api/client')

  const { data } = await api.GET('/healthz/live')

  expect(fakeFetch).toHaveBeenCalledTimes(1)
  const request = (fakeFetch.mock.calls[0] as unknown[])[0] as Request
  expect(request.url).toBe('http://api.test:9999/healthz/live')
  expect(request.method).toBe('GET')
  expect(data).toEqual({ status: 'ok' })
})

test('API_URL unset: import works, the call rejects without fetching', async () => {
  vi.stubEnv('API_URL', undefined)
  const fakeFetch = vi.fn()
  vi.stubGlobal('fetch', fakeFetch)

  const { api } = await import('@/lib/api/client')

  await expect(api.GET('/healthz/live')).rejects.toThrow(new Error('API_URL is not set'))
  expect(fakeFetch).not.toHaveBeenCalled()
})
