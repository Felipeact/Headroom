import { expect, test } from '@playwright/test'
import { SIGNED_OUT } from './test-user'

test.use({ storageState: SIGNED_OUT })

test('healthz is public', async ({ request }) => {
  const response = await request.get('/healthz', { maxRedirects: 0 })

  expect(response.status()).toBe(200)
  expect(await response.json()).toEqual({ status: 'ok' })
})
