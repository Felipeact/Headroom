import { expect, test } from '@playwright/test'

// Driven by .specs/features/07-web-app-shell/proofs.sh (C37, C38), which sets SENTRY_CHECK_RUN
// and then looks the two messages up in Sentry. On its own it only proves the buttons throw.
const RUN = process.env.SENTRY_CHECK_RUN ?? 'local'

test('sentry check buttons throw (C37, C38)', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto(`/dev/sentry-check?run=${RUN}`)
  await page.getByRole('button', { name: 'Throw a client error' }).click()
  await page.getByRole('button', { name: 'Throw a server error' }).click()
  await expect.poll(() => errors.length).toBeGreaterThanOrEqual(2)
  expect(errors).toContain(`Headroom web Sentry check (client) ${RUN}`)
  // Give the browser SDK time to send its envelopes before the page closes.
  await page.waitForTimeout(3000)
})
