import AxeBuilder from '@axe-core/playwright'
import { clerk } from '@clerk/testing/playwright'
import { expect, test, type Page } from '@playwright/test'
import { completeBusinessStep, connectSandboxBank, tabTo } from './onboarding-steps'
import { createOnboardingUser, deleteUser, SIGNED_OUT } from './test-user'

function pathOf(page: Page): string {
  return new URL(page.url()).pathname
}

/** At 375 px: no horizontal scroll, Continue at least 44 px tall, and no axe violations. */
async function meetsScreenRules(page: Page, name: string) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth), `${name} scroll`).toBeLessThanOrEqual(375)
  const axe = await new AxeBuilder({ page }).analyze()
  expect(axe.violations, `${name} axe`).toEqual([])
}

test.describe('a new owner', () => {
  test.use({ storageState: SIGNED_OUT, timezoneId: 'America/Toronto' })

  let user: { id: string; email: string }

  test.beforeEach(async ({ page }) => {
    user = await createOnboardingUser()
    await page.goto('/sign-in')
    await clerk.signIn({ page, emailAddress: user.email })
  })

  test.afterEach(async () => {
    await deleteUser(user.id)
  })

  test('C34 from sign-up to building the forecast', async ({ page }, testInfo) => {
    test.setTimeout(300_000)
    await page.setViewportSize({ width: 375, height: 812 })

    await page.goto('/')
    await expect.poll(() => pathOf(page)).toBe('/onboarding/business')
    await completeBusinessStep(page, `Harbor ${Date.now()}`)
    await page.getByRole('button', { name: 'Connect your bank' }).click()
    await connectSandboxBank(page, 'TD Canada Trust')
    await expect.poll(() => pathOf(page), { timeout: 60_000 }).toBe('/onboarding/accounts')
    await page.getByRole('button', { name: 'Continue' }).click()

    // Step 4.
    await expect.poll(() => pathOf(page), { timeout: 30_000 }).toBe('/onboarding/minimum-balance')
    await expect(page.getByRole('heading', { level: 1, name: 'Set your minimum balance' })).toBeVisible()
    await expect(page.getByText('Step 4 of 5')).toBeVisible()
    const input = page.getByRole('textbox', { name: 'Minimum balance' })
    await expect(input).toHaveValue(/^(\d{1,3}(,\d{3})*)?$/)
    const next = await page.getByRole('button', { name: 'Continue' }).boundingBox()
    expect(next?.height ?? 0).toBeGreaterThanOrEqual(44)
    await meetsScreenRules(page, 'step 4')
    await testInfo.attach('minimum-balance-375', { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })

    // Keyboard only: Tab to the field, type, Enter.
    await page.locator('body').focus()
    await tabTo(page, input)
    await page.keyboard.press('ControlOrMeta+A')
    await page.keyboard.type('5,000')
    await expect(page.getByText(/If your forecast dips below \$5,000,/)).toBeVisible()
    await page.keyboard.press('Enter')

    // Step 5: shown while the forecast builds, and for 2 s once it is ready (AD-092).
    await expect.poll(() => pathOf(page), { timeout: 30_000 }).toBe('/onboarding/forecast')
    await expect(page.getByRole('heading', { level: 1, name: 'Building your forecast' })).toBeVisible()
    await expect(page.getByText('Step 5 of 5')).toBeVisible()
    await expect(page.getByRole('status')).toContainText('Connected TD Canada Trust')
    await testInfo.attach('building-forecast-375', {
      body: await page.screenshot({ fullPage: true }),
      contentType: 'image/png',
    })
    await meetsScreenRules(page, 'step 5')
    // The checks above ran on step 5, not on the dashboard it moves to.
    expect(pathOf(page)).toBe('/onboarding/forecast')

    // Then the dashboard, once the first forecast reflects the synced bank.
    await expect.poll(() => pathOf(page), { timeout: 120_000 }).toBe('/')
    await expect(page.getByTestId('shell')).toBeVisible()
  })
})
