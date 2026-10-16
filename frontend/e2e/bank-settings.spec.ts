import { execFileSync } from 'node:child_process'
import AxeBuilder from '@axe-core/playwright'
import { clerk } from '@clerk/testing/playwright'
import { expect, test, type Page } from '@playwright/test'
import { completeBusinessStep, connectSandboxBank, tabTo } from './onboarding-steps'
import { createOnboardingUser, deleteUser, SIGNED_OUT } from './test-user'

const SETTINGS = '/settings/banks'
const TD = 'TD Canada Trust'
const RBC = 'RBC Royal Bank'

function pathOf(page: Page): string {
  return new URL(page.url()).pathname
}

/** A fresh owner through onboarding with `TD Canada Trust`, then on Settings > Bank connections. */
async function ownerWithBank(page: Page, business: string, second?: string) {
  await page.goto('/')
  await expect.poll(() => pathOf(page)).toBe('/onboarding/business')
  await completeBusinessStep(page, business)
  await page.getByRole('button', { name: 'Connect your bank' }).click()
  await connectSandboxBank(page, TD)
  await expect.poll(() => pathOf(page), { timeout: 60_000 }).toBe('/onboarding/accounts')
  if (second) {
    await page.getByRole('button', { name: 'Connect another bank' }).click()
    await connectSandboxBank(page, second)
    await expect(page.getByRole('heading', { level: 2, name: second })).toBeVisible({ timeout: 60_000 })
  }
  await page.goto(SETTINGS)
  await expect(page.getByRole('heading', { level: 2, name: 'Bank connections' })).toBeVisible()
}

const bankCard = (page: Page, name: string) => page.getByRole('region', { name })

/** Reloads until the bank's first sync, which runs after the connect, shows as done. */
async function untilSynced(page: Page, bank: string) {
  await expect
    .poll(
      async () => {
        await page.reload()
        return bankCard(page, bank).getByText(/^Synced today at /).count()
      },
      { timeout: 90_000, intervals: [2_000] },
    )
    .toBe(1)
}

/** The Plaid Link iframe that is open: the page holds one per Link token. */
const openLink = (page: Page) => page.locator('iframe[id^="plaid-link-iframe"]:visible').contentFrame()

test.describe('bank settings', () => {
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

  test('C13 phone width keyboard and axe', async ({ page }, testInfo) => {
    test.setTimeout(240_000)
    await page.setViewportSize({ width: 375, height: 812 })
    await ownerWithBank(page, `Harbor ${Date.now()}`)
    const card = bankCard(page, TD)
    await untilSynced(page, TD)

    // Count savings as cash with the mouse, so a second radio ("Make primary") exists.
    const savings = card.getByRole('row', { name: 'Plaid Saving' })
    await savings.getByRole('switch').click()
    await expect(savings.getByRole('radio', { name: 'Make primary' })).toBeVisible({ timeout: 15_000 })

    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
    const main = page.locator('main')
    const controls = [
      main.getByRole('button'),
      main.getByRole('switch'),
      main.locator('label').filter({ has: page.getByRole('radio') }),
      main.getByRole('link'),
    ]
    for (const control of controls) {
      for (const box of await Promise.all((await control.all()).map((c) => c.boundingBox()))) {
        expect(box?.height ?? 0).toBeGreaterThanOrEqual(44)
      }
    }
    await testInfo.attach('bank-settings-375', {
      body: await page.screenshot({ fullPage: true }),
      contentType: 'image/png',
    })
    const axe = await new AxeBuilder({ page }).analyze()
    expect(axe.violations).toEqual([])

    await page.locator('body').focus()
    await tabTo(page, page.getByRole('button', { name: 'Connect another bank' }))
    for (const toggle of await card.getByRole('switch').all()) await tabTo(page, toggle, 80)
    await page.locator('body').focus()
    await tabTo(page, card.getByRole('button', { name: 'Disconnect' }), 80)
    await tabTo(page, card.getByRole('radio', { name: 'Primary', exact: true }), 80)
    await tabTo(page, savings.getByRole('radio', { name: 'Make primary' }), 80)
  })

  test('C18 owner changes cash accounts and the primary account', async ({ page }) => {
    test.setTimeout(240_000)
    await ownerWithBank(page, `Harbor ${Date.now()}`)
    const savings = () => bankCard(page, TD).getByRole('row', { name: 'Plaid Saving' })

    await savings().getByRole('switch').click()
    await expect(savings().getByRole('switch')).toHaveAttribute('aria-checked', 'true', { timeout: 15_000 })
    await savings().getByRole('radio', { name: 'Make primary' }).click()
    await expect(savings().getByRole('radio', { name: 'Primary', exact: true })).toHaveAttribute('aria-checked', 'true', {
      timeout: 15_000,
    })

    await page.reload()
    await expect(savings().getByRole('switch')).toHaveAttribute('aria-checked', 'true')
    await expect(savings().getByRole('radio', { name: 'Primary', exact: true })).toHaveAttribute(
      'aria-checked',
      'true',
    )
    await expect(bankCard(page, TD).getByRole('radio', { checked: true })).toHaveCount(1)
  })

  test('C35 a bank that needs a login is repaired through Link update mode', async ({ page }) => {
    test.setTimeout(300_000)
    const business = `Harbor ${Date.now()}`
    await ownerWithBank(page, business)
    await untilSynced(page, TD)

    execFileSync('uv', ['run', 'python', '-m', 'tests.sandbox_reset_login', business], {
      cwd: '../services/core',
      stdio: 'inherit',
    })
    await page.reload()
    const card = bankCard(page, TD)
    await expect(card.getByRole('alert')).toContainText(
      "TD Canada Trust asked you to log in again. Until you do, your forecast is missing this bank's latest data.",
    )

    await card.getByRole('button', { name: 'Reconnect' }).click()
    const link = openLink(page)
    try {
      await link.getByRole('button', { name: 'Continue without phone number' }).click({ timeout: 30_000 })
    } catch {
      // No phone screen this time.
    }
    // Update mode remembers the username and asks only for the password.
    const password = link.locator('input[type="password"]')
    await password.waitFor({ timeout: 60_000 })
    if (await link.locator('input[type="text"]').count()) {
      await link.locator('input[type="text"]').fill('user_good')
    }
    await password.fill('pass_good')
    await link.getByRole('button', { name: 'Submit' }).click()
    // Update mode may ask to confirm accounts and to save the phone number; both are optional.
    for (const name of ['Continue', 'Finish without saving']) {
      try {
        await link.getByRole('button', { name, exact: true }).click({ timeout: 15_000 })
      } catch {
        // Not shown this time.
      }
    }

    await expect(card.getByText(/^Synced today at /)).toBeVisible({ timeout: 60_000 })
    await expect(card.getByRole('alert')).toHaveCount(0)
    expect(pathOf(page)).toBe(SETTINGS)
  })

  test('C49 owner disconnects one of two banks', async ({ page }) => {
    test.setTimeout(300_000)
    await ownerWithBank(page, `Harbor ${Date.now()}`, RBC)
    await expect(bankCard(page, RBC)).toBeVisible()

    await bankCard(page, RBC).getByRole('button', { name: 'Disconnect' }).click()
    const dialog = page.getByRole('dialog', { name: `Disconnect ${RBC}?` })
    await dialog.getByRole('button', { name: 'Disconnect' }).click()

    await expect(dialog).toBeHidden({ timeout: 30_000 })
    await expect(bankCard(page, RBC)).toHaveCount(0)
    await expect(page.getByText(`${RBC} disconnected`)).toBeVisible()
    await expect(bankCard(page, TD)).toBeVisible()
    expect(pathOf(page)).toBe(SETTINGS)
  })
})
