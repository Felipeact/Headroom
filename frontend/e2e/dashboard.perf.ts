import { clerk } from '@clerk/testing/playwright'
import { expect, test } from '@playwright/test'
import { loadSample } from './dashboard-steps'
import { createOnboardingUser, deleteUser, SIGNED_OUT } from './test-user'

// Spec 26 C34 (Done when 2): under 2 seconds on a mid-range phone, as Lighthouse's mobile profile
// stands in for one: 375x812, 4x CPU slowdown, 150 ms round trip, 1.6 Mbps down, 750 kbps up.
const BUDGET_MS = 2000
const LOADS = 3

test.use({ storageState: SIGNED_OUT, viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true })

test('C34 renders the sample dashboard in under 2 seconds', async ({ page }) => {
  test.setTimeout(240_000)
  const user = await createOnboardingUser()
  try {
    loadSample(user.id)
    await page.goto('/sign-in')
    await clerk.signIn({ page, emailAddress: user.email })
    // One untimed visit, so the measured loads find the server warm as a returning owner would.
    await page.goto('/')
    await page.getByTestId('chart-summary').waitFor({ state: 'attached', timeout: 60_000 })

    // When the chart's text summary first appears, in the page's own clock (ms from navigation start).
    await page.addInitScript(() => {
      const seen = () => document.querySelector('[data-testid="chart-summary"]')
      new MutationObserver((_, observer) => {
        if (seen()) {
          ;(window as unknown as { summaryAt: number }).summaryAt = performance.now()
          observer.disconnect()
        }
      }).observe(document, { childList: true, subtree: true })
    })
    const cdp = await page.context().newCDPSession(page)
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 })
    await cdp.send('Network.enable')
    await cdp.send('Network.emulateNetworkConditions', {
      offline: false,
      latency: 150,
      downloadThroughput: (1.6 * 1024 * 1024) / 8,
      uploadThroughput: (750 * 1024) / 8,
    })

    const times: number[] = []
    for (let load = 0; load < LOADS; load++) {
      await page.goto('/', { waitUntil: 'commit' })
      await page.waitForFunction(() => typeof (window as unknown as { summaryAt?: number }).summaryAt === 'number', null, {
        timeout: 30_000,
      })
      times.push(await page.evaluate(() => Math.round((window as unknown as { summaryAt: number }).summaryAt)))
    }
    console.log(`C34 chart summary attached after ${times.join(' ms, ')} ms`)
    for (const ms of times) expect(ms).toBeLessThan(BUDGET_MS)
  } finally {
    await deleteUser(user.id)
  }
})
