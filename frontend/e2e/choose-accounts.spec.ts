import AxeBuilder from '@axe-core/playwright'
import { clerk } from '@clerk/testing/playwright'
import { expect, test, type Page } from '@playwright/test'
import { completeBusinessStep, connectSandboxBank, tabTo } from './onboarding-steps'
import { createOnboardingUser, deleteUser, SIGNED_OUT } from './test-user'

const STEP = '/onboarding/accounts'

function pathOf(page: Page): string {
  return new URL(page.url()).pathname
}

const primaryRadios = (page: Page) => page.getByRole('radio', { name: 'Primary account' })

/** A fresh user through steps 2 and 3, with TD Canada Trust connected; ends on choose accounts. */
async function onboardWithBank(page: Page) {
  await page.goto('/')
  await expect.poll(() => pathOf(page)).toBe('/onboarding/business')
  await completeBusinessStep(page, 'Harbor Street Plumbing')
  await page.getByRole('button', { name: 'Connect your bank' }).click()
  await connectSandboxBank(page, 'TD Canada Trust')
  await expect.poll(() => pathOf(page), { timeout: 60_000 }).toBe(STEP)
  await expect(page.getByRole('heading', { name: 'Which accounts count as cash?' })).toBeVisible()
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

  test('C49 owner chooses cash accounts across two banks', async ({ page }) => {
    test.setTimeout(240_000)
    await onboardWithBank(page)
    await expect(page.getByText('TD Canada Trust is connected.', { exact: false })).toBeVisible()
    const checked = primaryRadios(page).and(page.locator('[aria-checked="true"]'))
    await expect(checked).toHaveCount(1)

    await page.getByRole('button', { name: 'Connect another bank' }).click()
    await connectSandboxBank(page, 'RBC Royal Bank')
    await expect(page.getByRole('heading', { level: 2, name: 'TD Canada Trust' })).toBeVisible({
      timeout: 60_000,
    })
    await expect(page.getByRole('heading', { level: 2, name: 'RBC Royal Bank' })).toBeVisible()
    expect(pathOf(page)).toBe(STEP)

    // The first savings account: count it, then make it primary.
    const savingsGroup = page.getByRole('radiogroup', { name: /^Count .* as cash$/ }).first()
    const savingsCard = page.getByRole('listitem').filter({ has: savingsGroup }).first()
    await savingsCard.getByRole('radio', { name: 'Yes, count it' }).click()
    await expect(savingsCard.getByRole('radio', { name: 'Yes, count it' })).toHaveAttribute(
      'aria-checked',
      'true',
    )
    await savingsCard.getByRole('radio', { name: 'Primary account' }).click()
    await expect(savingsCard.getByRole('radio', { name: 'Primary account' })).toHaveAttribute(
      'aria-checked',
      'true',
    )

    await page.reload()
    const reloadedGroup = page.getByRole('radiogroup', { name: /^Count .* as cash$/ }).first()
    const reloaded = page.getByRole('listitem').filter({ has: reloadedGroup }).first()
    await expect(reloaded.getByRole('radio', { name: 'Yes, count it' })).toHaveAttribute('aria-checked', 'true')
    await expect(reloaded.getByRole('radio', { name: 'Primary account' })).toHaveAttribute('aria-checked', 'true')
    await expect(checked).toHaveCount(1)

    await page.getByRole('button', { name: 'Continue' }).click()
    await expect.poll(() => pathOf(page), { timeout: 30_000 }).toBe('/onboarding/minimum-balance')
  })

  test('C50 layout keyboard and axe', async ({ page }, testInfo) => {
    test.setTimeout(180_000)
    await page.setViewportSize({ width: 375, height: 812 })
    await onboardWithBank(page)

    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
    const heading = await page.getByRole('heading', { level: 1 }).boundingBox()
    const firstCard = await page.getByRole('listitem').first().boundingBox()
    const lastCard = await page.getByRole('listitem').last().boundingBox()
    const note = await page.getByText('Expected payments you add go to your primary account').boundingBox()
    const connect = await page.getByRole('button', { name: 'Connect another bank' }).boundingBox()
    const next = await page.getByRole('button', { name: 'Continue' }).boundingBox()
    const ys = [heading, firstCard, lastCard, note, connect, next].map((box) => box?.y ?? -1)
    expect(ys).toEqual([...ys].sort((a, b) => a - b))
    for (const button of [connect, next]) {
      expect(Math.abs((button?.width ?? 0) - (heading?.width ?? 0))).toBeLessThanOrEqual(1)
    }

    const controls = [
      page.getByRole('switch'),
      page.getByRole('radiogroup', { name: /^Count .* as cash$/ }).getByRole('radio'),
      page.locator('label').filter({ hasText: 'Primary account' }),
      page.getByRole('button', { name: /^(Connect another bank|Continue)$/ }),
    ]
    for (const control of controls) {
      for (const box of await Promise.all((await control.all()).map((c) => c.boundingBox()))) {
        expect(box?.height ?? 0).toBeGreaterThanOrEqual(44)
      }
    }
    await testInfo.attach('choose-accounts-375', {
      body: await page.screenshot({ fullPage: true }),
      contentType: 'image/png',
    })

    const axe = await new AxeBuilder({ page }).analyze()
    expect(axe.violations).toEqual([])

    // The checking account is primary and cannot be excluded, so move the primary to savings
    // with the mouse first; then the keyboard flips the checking switch.
    const savingsGroup = page.getByRole('radiogroup', { name: /^Count .* as cash$/ }).first()
    const savingsCard = page.getByRole('listitem').filter({ has: savingsGroup }).first()
    await savingsCard.getByRole('radio', { name: 'Yes, count it' }).click()
    await savingsCard.getByRole('radio', { name: 'Primary account' }).click()
    await expect(savingsCard.getByRole('radio', { name: 'Primary account' })).toHaveAttribute(
      'aria-checked',
      'true',
    )
    const firstSwitch = page.getByRole('switch').first()
    const before = await firstSwitch.getAttribute('aria-checked')
    await page.locator('body').focus()
    await tabTo(page, firstSwitch)
    await page.keyboard.press('Space')
    await expect(page.getByRole('switch').first()).not.toHaveAttribute('aria-checked', before ?? '', {
      timeout: 15_000,
    })
    await tabTo(page, page.getByRole('button', { name: 'Continue' }))

    await page.setViewportSize({ width: 1280, height: 900 })
    const column = await page.locator('main').boundingBox()
    expect(column?.width ?? Infinity).toBeLessThanOrEqual(480)
    const left = column?.x ?? 0
    const right = 1280 - left - (column?.width ?? 0)
    expect(Math.abs(left - right)).toBeLessThanOrEqual(1)
  })
})
