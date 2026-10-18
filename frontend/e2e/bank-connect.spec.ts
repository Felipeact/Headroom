import AxeBuilder from '@axe-core/playwright'
import { clerk } from '@clerk/testing/playwright'
import { expect, test, type Page } from '@playwright/test'
import { completeBusinessStep, connectSandboxBank, plaidLink, tabTo } from './onboarding-steps'
import { createOnboardingUser, deleteUser, SIGNED_OUT } from './test-user'

const STEP = '/onboarding/bank'

function pathOf(page: Page): string {
  return new URL(page.url()).pathname
}

const connectButton = (page: Page) => page.getByRole('button', { name: 'Connect your bank' })
test.describe('a user without a business', () => {
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

  test('C41 new user connects a sandbox bank', async ({ page }) => {
    test.setTimeout(180_000)
    const started = Date.now()
    await page.goto('/')
    await expect.poll(() => pathOf(page)).toBe('/onboarding/business')

    await completeBusinessStep(page, 'Harbor Street Plumbing')
    expect(pathOf(page)).toBe(STEP)

    await connectButton(page).click()
    await connectSandboxBank(page)

    // Spec 13: a connected bank lands on choosing cash accounts; spec 23: Continue goes on to step 4.
    await expect.poll(() => pathOf(page), { timeout: 60_000 }).toBe('/onboarding/accounts')
    await page.getByRole('button', { name: 'Continue' }).click()
    await expect.poll(() => pathOf(page), { timeout: 30_000 }).toBe('/onboarding/minimum-balance')
    await expect(page.getByRole('heading', { name: 'Set your minimum balance' })).toBeVisible()
    expect(Date.now() - started).toBeLessThan(120_000)
  })

  test('C42 no business goes to step 2', async ({ page }) => {
    await page.goto(STEP)

    await expect.poll(() => pathOf(page)).toBe('/onboarding/business')
  })
})

// The existing test user has a business (global setup) and no bank yet, and the page does not
// require one, so it can show step 3 any number of times.
test('C43 layout keyboard and axe', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto(STEP)
  await expect(connectButton(page)).toBeEnabled()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
  const box = await connectButton(page).boundingBox()
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(44)

  const axe = await new AxeBuilder({ page }).analyze()
  expect(axe.violations).toEqual([])

  await page.setViewportSize({ width: 1280, height: 900 })
  const column = await page.locator('main').boundingBox()
  expect(column?.width ?? Infinity).toBeLessThanOrEqual(480)
  const left = column?.x ?? 0
  const right = 1280 - left - (column?.width ?? 0)
  expect(Math.abs(left - right)).toBeLessThanOrEqual(1)

  await tabTo(page, connectButton(page))
  await page.keyboard.press('Enter')
  await expect(
    plaidLink(page).getByRole('button', { name: 'Continue without phone number' }),
  ).toBeVisible({ timeout: 30_000 })
})
