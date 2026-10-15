import AxeBuilder from '@axe-core/playwright'
import { clerk } from '@clerk/testing/playwright'
import { expect, test, type Page } from '@playwright/test'
import { completeBusinessStep, tabTo } from './onboarding-steps'
import { createOnboardingUser, deleteUser, SIGNED_OUT } from './test-user'

const PAGE = '/settings/members'

function pathOf(page: Page): string {
  return new URL(page.url()).pathname
}

// Spec 31 C29: the Members section, as the owner of a business sees it.
test.describe('members and invite: members section', () => {
  test.use({ storageState: SIGNED_OUT, timezoneId: 'America/Toronto' })
  let user: { id: string; email: string }

  test.beforeEach(async ({ page }) => {
    user = await createOnboardingUser()
    await page.goto('/sign-in')
    await clerk.signIn({ page, emailAddress: user.email })
    await page.goto('/')
    await expect.poll(() => pathOf(page)).toBe('/onboarding/business')
    await completeBusinessStep(page, 'Members Co')
  })

  test.afterEach(async () => {
    await deleteUser(user.id)
  })

  test('members and invite: empty state, then an invitation is pending', async ({ page }) => {
    await page.goto(PAGE)
    await expect(page.getByRole('heading', { name: 'Members', level: 2 })).toBeVisible()
    await expect(page.getByTestId('members-empty')).toContainText('No bookkeepers yet')
    await expect(page.getByTestId('member-row')).toHaveCount(1)

    await page.getByLabel("Bookkeeper's email address").fill('pat@example.test')
    await page.getByRole('button', { name: 'Send invitation' }).click()

    await expect(page.getByText('Invitation sent to pat@example.test')).toBeVisible()
    await expect(page.getByTestId('pending-invitation')).toHaveCount(1)
    await expect(page.getByTestId('members-empty')).toHaveCount(0)
  })

  test('members and invite: an invalid address is refused', async ({ page }) => {
    await page.goto(PAGE)
    await page.getByLabel("Bookkeeper's email address").fill('not-an-email')
    await page.getByRole('button', { name: 'Send invitation' }).click()

    await expect(page.getByTestId('shell').getByRole('alert')).toHaveText('Enter a valid email address.')
  })

  test('members and invite: phone width, keyboard and axe', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto(PAGE)
    const input = page.getByLabel("Bookkeeper's email address")
    await expect(input).toBeVisible()

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(overflow).toBeLessThanOrEqual(0)
    const send = page.getByRole('button', { name: 'Send invitation' })
    expect((await send.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44)
    for (const row of await page.getByTestId('member-row').all()) {
      expect((await row.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44)
    }

    await tabTo(page, input)
    await input.fill('pat@example.test')
    await page.keyboard.press('Enter')
    const toast = page.getByText('Invitation sent to pat@example.test')
    await expect(toast).toBeVisible()
    // axe measures colour while the toast is still fading in; scan the settled toast.
    await expect(page.locator('[data-sonner-toast]')).toHaveCSS('opacity', '1')

    const axe = await new AxeBuilder({ page }).analyze()
    expect(axe.violations).toEqual([])
  })
})

test.describe('members and invite: members signed out', () => {
  test.use({ storageState: SIGNED_OUT })

  test('members and invite: signed out goes to sign-in', async ({ page }) => {
    await page.goto(PAGE)

    await expect.poll(() => pathOf(page)).toBe('/sign-in')
  })
})
