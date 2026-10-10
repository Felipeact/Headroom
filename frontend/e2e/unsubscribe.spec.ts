import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { emailState } from './email-steps'
import { tabTo } from './onboarding-steps'
import { createOnboardingUser, deleteUser, SIGNED_OUT } from './test-user'

function pathOf(page: Page): string {
  return new URL(page.url()).pathname
}

test.describe('unsubscribe (spec 28 C47)', () => {
  test.use({ storageState: SIGNED_OUT })
  let user: { id: string; email: string }
  let token: string

  test.beforeEach(async () => {
    user = await createOnboardingUser()
    token = emailState(user.id).token
  })

  test.afterEach(async () => {
    await deleteUser(user.id)
  })

  test('unsubscribe: signed out, one press turns every email off', async ({ page }) => {
    await page.goto(`/unsubscribe/${token}`)

    expect(pathOf(page)).toBe(`/unsubscribe/${token}`)
    await expect(page.getByRole('heading', { level: 1, name: 'Unsubscribe from Headroom emails?' })).toBeVisible()
    expect(emailState(user.id)).toMatchObject({ alerts: true, weekly_digest: true })

    await page.getByRole('button', { name: 'Unsubscribe' }).click()

    await expect(page.getByRole('heading', { level: 1, name: "You're unsubscribed" })).toBeVisible()
    expect(emailState(user.id)).toMatchObject({ alerts: false, weekly_digest: false })
  })

  test('unsubscribe: phone width, desktop column, keyboard and axe', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto(`/unsubscribe/${token}`)
    const button = page.getByRole('button', { name: 'Unsubscribe' })
    await expect(button).toBeVisible()

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(overflow).toBeLessThanOrEqual(0)
    expect((await button.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44)
    const phoneAxe = await new AxeBuilder({ page }).analyze()
    expect(phoneAxe.violations).toEqual([])

    await page.setViewportSize({ width: 1280, height: 800 })
    const column = await page.locator('main').boundingBox()
    expect(column?.width ?? 0).toBeLessThanOrEqual(480)
    const left = column?.x ?? 0
    const right = 1280 - left - (column?.width ?? 0)
    expect(Math.abs(left - right)).toBeLessThanOrEqual(2)

    await tabTo(page, button)
    await page.keyboard.press('Enter')
    await expect(page.getByRole('heading', { level: 1, name: "You're unsubscribed" })).toBeVisible()
    const doneAxe = await new AxeBuilder({ page }).analyze()
    expect(doneAxe.violations).toEqual([])
  })
})
