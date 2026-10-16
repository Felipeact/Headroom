import { expect, test, vi } from 'vitest'
import messages from '@/messages/en.json'

// Outside a React Server Component, next-intl/server's getRequestConfig is a stub that throws.
// The server build's version returns its callback unchanged, so the mock does the same.
vi.mock('next-intl/server', () => ({
  getRequestConfig: <T>(createRequestConfig: T) => createRequestConfig,
}))

test('C19 request config is English with messages/en.json', async () => {
  const { default: requestConfig } = await import('@/i18n/request')
  const config = await requestConfig({ requestLocale: Promise.resolve(undefined) })
  expect(config.locale).toBe('en')
  expect(config.messages).toEqual(messages)
})
