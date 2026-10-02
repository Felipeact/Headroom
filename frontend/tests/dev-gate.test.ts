import { afterEach, expect, test, vi } from 'vitest'
import Page from '@/app/dev/components/page'

afterEach(() => {
  vi.unstubAllEnvs()
})

test('C33 production calls notFound', () => {
  vi.stubEnv('NODE_ENV', 'production')
  let thrown: unknown
  try {
    Page()
  } catch (error) {
    thrown = error
  }
  expect((thrown as { digest?: string } | undefined)?.digest).toBe(
    'NEXT_HTTP_ERROR_FALLBACK;404',
  )
})

test('C33 development renders the page', () => {
  vi.stubEnv('NODE_ENV', 'development')
  expect(() => Page()).not.toThrow()
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
