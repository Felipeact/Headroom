import AxeBuilder from '@axe-core/playwright'
import { clerk } from '@clerk/testing/playwright'
import { expect, test, type Locator, type Page } from '@playwright/test'
import { completeBusinessStep, connectSandboxBank, tabTo } from './onboarding-steps'
import { createOnboardingUser, deleteUser, SIGNED_OUT } from './test-user'

const PAGE = '/expected-payments'
const API = 'http://localhost:8100'

type Payment = { description: string; amount_cents: number; repeats: string | null; date: string }

function pathOf(page: Page): string {
  return new URL(page.url()).pathname
}

/** A fresh owner through onboarding with a sandbox bank, then on Expected payments. */
async function ownerWithBank(page: Page) {
  await page.goto('/')
  await expect.poll(() => pathOf(page)).toBe('/onboarding/business')
  await completeBusinessStep(page, `Harbor ${Date.now()}`)
  await page.getByRole('button', { name: 'Connect your bank' }).click()
  await connectSandboxBank(page)
  await expect.poll(() => pathOf(page), { timeout: 60_000 }).toBe('/onboarding/accounts')
  await page.goto(PAGE)
  await expect(page.getByRole('heading', { level: 1, name: 'Expected payments' })).toBeVisible()
}

/** The owner's expected payments, read from the API with their Clerk session token. */
async function apiPayments(page: Page): Promise<Payment[]> {
  // Clerk loads after the page; its session is there once it has.
  await page.waitForFunction(() => Boolean((window as unknown as { Clerk?: { session?: unknown } }).Clerk?.session))
  const token = await page.evaluate(async () => {
    const clerkJs = (window as unknown as { Clerk: { session: { getToken: () => Promise<string> } } }).Clerk
    return clerkJs.session.getToken()
  })
  const headers = { Authorization: `Bearer ${token}` }
  const businesses = await (await page.request.get(`${API}/v1/businesses`, { headers })).json()
  const response = await page.request.get(`${API}/v1/businesses/${businesses.items[0].id}/expected-payments`, {
    headers,
  })
  expect(response.status()).toBe(200)
  return (await response.json()).items
}

/** Today plus `days`, as the date input wants it (YYYY-MM-DD), in the browser's time zone. */
async function isoDay(page: Page, days: number): Promise<string> {
  return page.evaluate((offset) => {
    const day = new Date()
    day.setDate(day.getDate() + offset)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`
  }, days)
}

const dialog = (page: Page) => page.getByRole('dialog')
const row = (page: Page, description: string) => page.getByRole('row').filter({ hasText: description })

async function choose(page: Page, combobox: Locator, option: string) {
  await combobox.click()
  await page.getByRole('option', { name: option }).click()
}

test.describe('expected payments', () => {
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

  test('C45 round trip', async ({ page }) => {
    test.setTimeout(240_000)
    await ownerWithBank(page)
    const day = await isoDay(page, 10)

    await page.getByRole('button', { name: 'Add expected payment' }).click()
    await dialog(page).getByLabel('Amount').fill('1,234.56')
    await dialog(page).getByLabel('Date').fill(day)
    await dialog(page).getByLabel('Description').fill('E2E deposit')
    await dialog(page).getByRole('button', { name: 'Add payment' }).click()
    await expect(dialog(page)).toBeHidden({ timeout: 30_000 })
    await expect(page.getByText('Expected payment added')).toBeVisible()

    await page.reload()
    await expect(row(page, 'E2E deposit')).toContainText('−$1,235')
    expect(await apiPayments(page)).toMatchObject([
      { description: 'E2E deposit', amount_cents: -123456, repeats: null, date: day },
    ])

    await page.getByRole('button', { name: 'Edit E2E deposit' }).click()
    await expect(dialog(page).getByLabel('Amount')).toHaveValue('1,234.56')
    await dialog(page).getByLabel('Amount').fill('2,000.00')
    await choose(page, dialog(page).getByRole('combobox', { name: 'Repeats' }), 'Every month')
    await dialog(page).getByRole('button', { name: 'Save changes' }).click()
    await expect(dialog(page)).toBeHidden({ timeout: 30_000 })
    await expect(page.getByText('Expected payment updated')).toBeVisible()

    await page.reload()
    await expect(row(page, 'E2E deposit')).toContainText('−$2,000')
    await expect(row(page, 'E2E deposit')).toContainText('Every month')
    expect(await apiPayments(page)).toMatchObject([
      { description: 'E2E deposit', amount_cents: -200000, repeats: 'monthly', date: day },
    ])

    await page.getByRole('button', { name: 'Delete E2E deposit' }).click()
    await dialog(page).getByRole('button', { name: 'Delete payment' }).click()
    await expect(dialog(page)).toBeHidden({ timeout: 30_000 })

    await page.reload()
    await expect(page.getByRole('heading', { name: 'No expected payments yet' })).toBeVisible()
    expect(await apiPayments(page)).toEqual([])
  })

  test('C46 phone keyboard and axe', async ({ page }, testInfo) => {
    test.setTimeout(240_000)
    await page.setViewportSize({ width: 375, height: 812 })
    await ownerWithBank(page)

    // The empty state.
    await expect(page.getByRole('heading', { name: 'No expected payments yet' })).toBeVisible()
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])

    // Add one with the keyboard only.
    const add = page.getByRole('button', { name: 'Add expected payment' })
    await page.locator('body').focus()
    await tabTo(page, add)
    await page.keyboard.press('Enter')
    await expect(dialog(page)).toBeVisible()
    const box = await dialog(page).boundingBox()
    expect(box).toMatchObject({ x: 0, y: 0, width: 375, height: 812 })
    for (const control of await dialog(page).locator('button, input, [role="combobox"]').all()) {
      if (!(await control.isVisible())) continue
      expect((await control.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44)
    }
    expect((await new AxeBuilder({ page }).include('[role="dialog"]').analyze()).violations).toEqual([])

    const moneyIn = dialog(page).getByRole('radio', { name: 'Money in' })
    await tabTo(page, dialog(page).getByRole('radio', { name: 'Money out' }))
    await page.keyboard.press('ArrowRight')
    await expect(moneyIn).toBeFocused()
    await page.keyboard.press('Space')
    await expect(moneyIn).toHaveAttribute('aria-checked', 'true')
    await page.keyboard.press('Tab')
    await expect(dialog(page).getByLabel('Amount')).toBeFocused()
    await page.keyboard.type('500')
    await page.keyboard.press('Tab')
    await expect(dialog(page).getByLabel('Date')).toBeFocused()
    await dialog(page).getByLabel('Date').fill(await isoDay(page, 5))
    await page.keyboard.press('Tab')
    await tabTo(page, dialog(page).getByLabel('Description'), 5)
    await page.keyboard.type('Keyboard invoice')
    await tabTo(page, dialog(page).getByRole('button', { name: 'Add payment' }), 10)
    await page.keyboard.press('Enter')
    await expect(dialog(page)).toBeHidden({ timeout: 30_000 })
    await expect(row(page, 'Keyboard invoice')).toBeVisible()

    // The phone layout: no sideways scroll, and the row stacks.
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
    const description = await row(page, 'Keyboard invoice').getByText('Keyboard invoice').boundingBox()
    const amount = await row(page, 'Keyboard invoice').getByText('+$500').boundingBox()
    const date = await row(page, 'Keyboard invoice').getByRole('cell').first().boundingBox()
    expect(description && date && description.y < date.y).toBe(true)
    expect(amount && date && amount.y < date.y).toBe(true)
    for (const control of await page.locator('main').locator('button, a, input').all()) {
      if (!(await control.isVisible())) continue
      expect((await control.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44)
    }
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
    await testInfo.attach('expected-payments-375', {
      body: await page.screenshot({ fullPage: true }),
      contentType: 'image/png',
    })

    // Edit and delete open from the keyboard; Escape closes them and focus goes back.
    const edit = page.getByRole('button', { name: 'Edit Keyboard invoice' })
    await page.locator('body').focus()
    await tabTo(page, edit)
    await page.keyboard.press('Enter')
    await expect(dialog(page).getByRole('heading', { name: 'Edit expected payment' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog(page)).toBeHidden()
    await expect(edit).toBeFocused()

    const remove = page.getByRole('button', { name: 'Delete Keyboard invoice' })
    await page.keyboard.press('Tab')
    await expect(remove).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(dialog(page).getByRole('heading', { name: 'Delete Keyboard invoice?' })).toBeVisible()
    expect((await new AxeBuilder({ page }).include('[role="dialog"]').analyze()).violations).toEqual([])
    await page.keyboard.press('Escape')
    await expect(dialog(page)).toBeHidden()
    await expect(remove).toBeFocused()

    await page.locator('body').focus()
    await tabTo(page, add)
    await page.keyboard.press('Enter')
    await expect(dialog(page).getByRole('heading', { name: 'Add expected payment' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(add).toBeFocused()
  })
})
