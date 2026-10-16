import AxeBuilder from '@axe-core/playwright'
import { clerk } from '@clerk/testing/playwright'
import { expect, test, type Page } from '@playwright/test'
import { createInvitation } from './invite-steps'
import { completeBusinessStep, tabTo } from './onboarding-steps'
import { createOnboardingUser, deleteUser, SIGNED_OUT } from './test-user'

function pathOf(page: Page): string {
  return new URL(page.url()).pathname
}

// Spec 31 C29: the invitation link, as the invited bookkeeper opens it.
test.describe('members and invite: invite page', () => {
  test.use({ storageState: SIGNED_OUT, timezoneId: 'America/Toronto' })
  let owner: { id: string; email: string }
  let bookkeeper: { id: string; email: string }

  test.beforeEach(async ({ page }) => {
    owner = await createOnboardingUser()
    bookkeeper = await createOnboardingUser()
    await page.goto('/sign-in')
    await clerk.signIn({ page, emailAddress: owner.email })
    await page.goto('/')
    await expect.poll(() => pathOf(page)).toBe('/onboarding/business')
    await completeBusinessStep(page, 'Invite Co')
    await clerk.signOut({ page })
    await page.goto('/sign-in')
    await clerk.signIn({ page, emailAddress: bookkeeper.email })
  })

  test.afterEach(async () => {
    await deleteUser(owner.id)
    await deleteUser(bookkeeper.id)
  })

  test('members and invite: accepting gives the bookkeeper the business', async ({ page }) => {
    const token = createInvitation(owner.id, bookkeeper.email)
    await page.goto(`/invite/${token}`)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Join Invite Co on Headroom')

    await page.getByRole('button', { name: 'Accept invitation' }).click()
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('You now have access to Invite Co')
    await page.getByRole('link', { name: 'Go to the dashboard' }).click()

    await expect.poll(() => pathOf(page)).toBe('/')
    await page.goto('/settings')
    const nav = page.getByRole('navigation', { name: 'Settings' })
    await expect(nav.getByRole('link', { name: 'Email preferences' })).toBeVisible()
    await expect(nav.getByRole('link', { name: 'Members' })).toHaveCount(0)
  })

  test('members and invite: an invitation for another address is refused', async ({ page }) => {
    const token = createInvitation(owner.id, 'someone-else@example.test')
    await page.goto(`/invite/${token}`)
    await page.getByRole('button', { name: 'Accept invitation' }).click()

    await expect(page.getByRole('heading', { level: 1 })).toHaveText(
      'This invitation is for a different email address',
    )
  })

  test('members and invite: an expired link', async ({ page }) => {
    const token = createInvitation(owner.id, bookkeeper.email, 'expired')
    await page.goto(`/invite/${token}`)

    await expect(page.getByRole('heading', { level: 1 })).toHaveText('This invitation has expired')
    await expect(page.getByRole('button', { name: 'Accept invitation' })).toHaveCount(0)
  })

  test('members and invite: an unknown link', async ({ page }) => {
    await page.goto(`/invite/${'x'.repeat(43)}`)

    await expect(page.getByRole('heading', { level: 1 })).toHaveText("We can't find this invitation")
  })

  test('members and invite: invite phone width, keyboard and axe', async ({ page }) => {
    const token = createInvitation(owner.id, bookkeeper.email)
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto(`/invite/${token}`)
    const accept = page.getByRole('button', { name: 'Accept invitation' })
    await expect(accept).toBeVisible()

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(overflow).toBeLessThanOrEqual(0)
    expect((await accept.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44)
    const axe = await new AxeBuilder({ page }).analyze()
    expect(axe.violations).toEqual([])

    await tabTo(page, accept)
    await page.keyboard.press('Enter')
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('You now have access to Invite Co')
  })
})

test.describe('members and invite: invite signed out', () => {
  test.use({ storageState: SIGNED_OUT })

  test('members and invite: signed out goes to sign-in', async ({ page }) => {
    await page.goto(`/invite/${'x'.repeat(43)}`)

    await expect.poll(() => pathOf(page)).toBe('/sign-in')
  })
})
