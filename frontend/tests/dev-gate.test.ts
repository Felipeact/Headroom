import { afterEach, expect, test, vi } from 'vitest'
import Page from '@/app/dev/components/page'
import { api } from '@/lib/api/client'

vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn() } }))
// Dev pages also require a signed-in user (spec 10); the gate under test runs before that.
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))

afterEach(() => {
  vi.unstubAllEnvs()
})

test('C33 production calls notFound', async () => {
  vi.stubEnv('NODE_ENV', 'production')
  const thrown = await Page().catch((error: unknown) => error)
  expect((thrown as { digest?: string } | undefined)?.digest).toBe(
    'NEXT_HTTP_ERROR_FALLBACK;404',
  )
})

test('C33 development renders the page', async () => {
  vi.stubEnv('NODE_ENV', 'development')
  await expect(Page()).resolves.toBeDefined()
})

test('C39 sentry check: production calls notFound', async () => {
  vi.stubEnv('NODE_ENV', 'production')
  const { default: SentryCheckPage } = await import('@/app/dev/sentry-check/page')
  const thrown = await SentryCheckPage({ searchParams: Promise.resolve({}), params: Promise.resolve({}) }).catch(
    (error: unknown) => error,
  )
  expect((thrown as { digest?: string } | undefined)?.digest).toBe('NEXT_HTTP_ERROR_FALLBACK;404')
})

test('C39 sentry check: development renders the page', async () => {
  vi.stubEnv('NODE_ENV', 'development')
  const { default: SentryCheckPage } = await import('@/app/dev/sentry-check/page')
  await expect(
    SentryCheckPage({ searchParams: Promise.resolve({ run: 'abc' }), params: Promise.resolve({}) }),
  ).resolves.toBeDefined()
})

test('C14 api check: production calls notFound and makes no request', async () => {
  vi.stubEnv('NODE_ENV', 'production')
  const { default: ApiCheckPage } = await import('@/app/dev/api-check/page')
  const thrown = await ApiCheckPage().catch((error: unknown) => error)
  expect((thrown as { digest?: string } | undefined)?.digest).toBe('NEXT_HTTP_ERROR_FALLBACK;404')
  expect(api.GET).toHaveBeenCalledTimes(0)
})
