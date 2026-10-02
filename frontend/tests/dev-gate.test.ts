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
