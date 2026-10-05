import AxeBuilder from '@axe-core/playwright'
import { clerk } from '@clerk/testing/playwright'
import { expect, test, type Locator, type Page } from '@playwright/test'
import { completeBusinessStep } from './onboarding-steps'
import { createOnboardingUser, deleteUser, SIGNED_OUT } from './test-user'

const STEP = '/onboarding/business'
const QUEBEC_ERROR =
  "Headroom isn't available in Quebec yet. You can't set up a business there for now."

function pathOf(page: Page): string {
  return new URL(page.url()).pathname
}

// Presses Tab until `target` has focus; fails after `limit` presses.
async function tabTo(page: Page, target: Locator, limit = 30) {
  for (let i = 0; i < limit; i++) {
    await page.keyboard.press('Tab')
    if (await target.evaluate((el) => el === document.activeElement)) return
  }
  throw new Error(`Tab never reached ${target}`)
}

const province = (page: Page) => page.getByRole('combobox', { name: 'Province or territory' })
const timeZone = (page: Page) => page.getByRole('combobox', { name: 'Time zone' })
const continueButton = (page: Page) => page.getByRole('button', { name: 'Continue' })

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

  test('C34 new user creates a business', async ({ page }) => {
    const started = Date.now()
    await page.goto('/')
    await expect.poll(() => pathOf(page)).toBe(STEP)

    await completeBusinessStep(page, 'Harbor Street Plumbing')

    // Spec 12 AC 24: step 2 now lands on step 3; the dashboard shows the business from there.
    expect(pathOf(page)).toBe('/onboarding/bank')
    await page.goto('/')
    await expect(page.getByTestId('header-desktop-identity')).toContainText(
      'Harbor Street Plumbing',
    )
    expect(Date.now() - started).toBeLessThan(120_000)
  })

  test('C36 quebec shows not available', async ({ page }) => {
    await page.goto(STEP)
    await page.getByLabel('Business name').fill('Rue Saint-Paul Café')
    await province(page).click()
    await page.getByRole('option', { name: 'Quebec' }).click()

    await expect(page.getByText(QUEBEC_ERROR)).toBeVisible()
    await continueButton(page).click()
    await expect(page.getByText(QUEBEC_ERROR)).toBeVisible()
    expect(pathOf(page)).toBe(STEP)

    // The page sends a user who has a business to "/", so still seeing the form after a
    // reload means GET /v1/businesses returned none.
    await page.reload()
    expect(pathOf(page)).toBe(STEP)
    await expect(page.getByRole('heading', { name: 'Tell us about your business' })).toBeVisible()
  })

  test('C37 layout keyboard and axe', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto(STEP)
    await expect(continueButton(page)).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)

    const axe = await new AxeBuilder({ page }).analyze()
    expect(axe.violations).toEqual([])

    for (const control of [
      page.getByLabel('Business name'),
      province(page),
      timeZone(page),
      continueButton(page),
    ]) {
      const box = await control.boundingBox()
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(44)
    }

    await page.setViewportSize({ width: 1280, height: 900 })
    const column = await page.locator('main').boundingBox()
    expect(column?.width ?? Infinity).toBeLessThanOrEqual(480)
    const left = column?.x ?? 0
    const right = 1280 - left - (column?.width ?? 0)
    expect(Math.abs(left - right)).toBeLessThanOrEqual(1)

    // Keyboard only: the time zone came from the browser (America/Toronto).
    await expect(timeZone(page)).toHaveText('Eastern Time (Toronto)')
    await tabTo(page, page.getByLabel('Business name'))
    await page.keyboard.type('Harbor Street Plumbing')
    await page.keyboard.press('Tab')
    await expect(province(page)).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('listbox')).toBeVisible()
    await page.keyboard.type('Ontario', { delay: 50 })
    await expect(page.getByRole('option', { name: 'Ontario' })).toBeFocused()
    await page.keyboard.press('ArrowDown')
    await expect(page.getByRole('option', { name: 'Prince Edward Island' })).toBeFocused()
    await page.keyboard.press('ArrowUp')
    await expect(page.getByRole('option', { name: 'Ontario' })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(province(page)).toHaveText('Ontario')
    await tabTo(page, continueButton(page))
    await page.keyboard.press('Enter')

    // Spec 12 AC 24: Continue lands on step 3.
    await expect(page.getByRole('heading', { name: 'Connect your bank' })).toBeVisible()
    expect(pathOf(page)).toBe('/onboarding/bank')
  })
})

test('C35 user with a business skips onboarding', async ({ page }) => {
  await page.goto(STEP)

  await expect.poll(() => pathOf(page)).toBe('/')
  await expect(page.getByTestId('shell')).toBeVisible()
})
