import AxeBuilder from '@axe-core/playwright'
import { clerk } from '@clerk/testing/playwright'
import { expect, test, type Page } from '@playwright/test'
import { emailState } from './email-steps'
import { completeBusinessStep, tabTo } from './onboarding-steps'
import { createOnboardingUser, deleteUser, SIGNED_OUT } from './test-user'

const PAGE = '/settings/email'

function pathOf(page: Page): string {
  return new URL(page.url()).pathname
}

test.describe('email preferences (spec 28 C36)', () => {
  test.use({ storageState: SIGNED_OUT, timezoneId: 'America/Toronto' })
  let user: { id: string; email: string }

  test.beforeEach(async ({ page }) => {
    user = await createOnboardingUser()
    await page.goto('/sign-in')
    await clerk.signIn({ page, emailAddress: user.email })
    await page.goto('/')
    await expect.poll(() => pathOf(page)).toBe('/onboarding/business')
    await completeBusinessStep(page, 'Email Prefs Co')
  })

  test.afterEach(async () => {
    await deleteUser(user.id)
  })

  test('email preferences: turn off the weekly digest, and it stays off', async ({ page }) => {
    await page.goto(PAGE)
    const digest = page.getByRole('switch', { name: 'Weekly digest' })
    const alerts = page.getByRole('switch', { name: 'Cash gap alerts' })
    await expect(digest).toHaveAttribute('aria-checked', 'true')
    await expect(alerts).toHaveAttribute('aria-checked', 'true')

    await digest.click()

    await expect(page.getByText('Email preferences saved')).toBeVisible()
    await page.reload()
    await expect(page.getByRole('switch', { name: 'Weekly digest' })).toHaveAttribute('aria-checked', 'false')
    await expect(page.getByRole('switch', { name: 'Cash gap alerts' })).toHaveAttribute('aria-checked', 'true')
    expect(emailState(user.id)).toMatchObject({ alerts: true, weekly_digest: false })
  })

  test('email preferences: phone width, keyboard and axe', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto(PAGE)
    const alerts = page.getByRole('switch', { name: 'Cash gap alerts' })
    const digest = page.getByRole('switch', { name: 'Weekly digest' })
    await expect(alerts).toBeVisible()

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(overflow).toBeLessThanOrEqual(0)
    for (const row of await page.getByTestId('email-preference-row').all()) {
      const box = await row.boundingBox()
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(44)
    }

    await tabTo(page, alerts)
    await page.keyboard.press('Tab')
    await expect(digest).toBeFocused()
    await page.keyboard.press('Space')
    await expect(digest).toHaveAttribute('aria-checked', 'false')
    await expect(page.getByText('Email preferences saved')).toBeVisible()

    const axe = await new AxeBuilder({ page }).analyze()
    expect(axe.violations).toEqual([])
  })
})

test.describe('email preferences signed out (spec 28 C36)', () => {
  test.use({ storageState: SIGNED_OUT })

  test('email preferences: signed out goes to sign-in', async ({ page }) => {
    await page.goto(PAGE)

    await expect.poll(() => pathOf(page)).toBe('/sign-in')
  })
})
