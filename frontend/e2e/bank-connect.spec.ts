import AxeBuilder from '@axe-core/playwright'
import { clerk } from '@clerk/testing/playwright'
import { expect, test, type Locator, type Page } from '@playwright/test'
import { completeBusinessStep } from './onboarding-steps'
import { createOnboardingUser, deleteUser, SIGNED_OUT } from './test-user'

const STEP = '/onboarding/bank'

function pathOf(page: Page): string {
  return new URL(page.url()).pathname
}

const connectButton = (page: Page) => page.getByRole('button', { name: 'Connect your bank' })
const plaidLink = (page: Page) => page.frameLocator('iframe[id^="plaid-link-iframe"]')

// Presses Tab until `target` has focus; fails after `limit` presses.
async function tabTo(page: Page, target: Locator, limit = 30) {
  for (let i = 0; i < limit; i++) {
    await page.keyboard.press('Tab')
    if (await target.evaluate((el) => el === document.activeElement)) return
  }
  throw new Error(`Tab never reached ${target}`)
}

/** Goes through the Plaid Link sandbox for TD Canada Trust with Plaid's test credentials. */
async function connectSandboxBank(page: Page) {
  const link = plaidLink(page)
  await link.getByRole('button', { name: 'Continue without phone number' }).click()
  await link.locator('input').first().fill('TD Canada Trust')
  await link.getByText('TD Canada Trust', { exact: true }).first().click()
  await link.getByRole('button', { name: 'TD Canada Trust', exact: true }).click()
  await link.locator('input[type="text"]').fill('user_good')
  await link.locator('input[type="password"]').fill('pass_good')
  await link.getByRole('button', { name: 'Submit' }).click()
  await link.getByRole('button', { name: 'Continue', exact: true }).click()
  await link.getByRole('button', { name: 'Finish without saving' }).click()
}

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

    await expect.poll(() => pathOf(page), { timeout: 60_000 }).toBe('/')
    await expect(page.getByTestId('shell')).toBeVisible()
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
