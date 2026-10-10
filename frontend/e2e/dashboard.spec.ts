import AxeBuilder from '@axe-core/playwright'
import { clerk } from '@clerk/testing/playwright'
import { expect, test, type Page } from '@playwright/test'
import { callApi, getDashboard, loadSample } from './dashboard-steps'
import { completeBusinessStep, tabTo } from './onboarding-steps'
import { createOnboardingUser, deleteUser, SIGNED_OUT } from './test-user'

// Spec 26. The sample's forecast is computed on the real clock, so forecast-derived values are
// read from the owner's own GET .../dashboard; balances, accounts and the 2026-09-26 sync are fixed.

const WIDE = { width: 1280, height: 900 }
const PHONE = { width: 375, height: 812 }
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

const money = (cents: number) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 })
    .format(Math.round(Math.abs(cents) / 100))
    .replace(/^/, cents < 0 ? '−' : '')

async function signIn(page: Page, email: string) {
  await page.goto('/sign-in')
  await clerk.signIn({ page, emailAddress: email })
}

async function openDashboard(page: Page) {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: 'Cash flow' })).toBeVisible({ timeout: 30_000 })
}

/** Sets the minimum $5,000 above the projected low, so the sample has a cash gap on any day. */
async function raiseMinimum(page: Page) {
  const before = await getDashboard(page)
  const low = before.projected_low?.balance_cents ?? 0
  await callApi(page, 'PUT', (id) => `/v1/businesses/${id}/minimum-balance`, { amount_cents: Math.max(0, low) + 500000 })
  await expect.poll(async () => (await getDashboard(page)).alerts.length, { timeout: 30_000 }).toBeGreaterThan(0)
}

async function settle(page: Page) {
  await page.getByTestId('chart-summary').waitFor({ state: 'attached' })
  await page.waitForTimeout(1500)
}

test.describe('the dashboard with the sample', () => {
  test.use({ storageState: SIGNED_OUT, timezoneId: 'America/Toronto', viewport: WIDE })

  let user: { id: string; email: string }

  test.beforeEach(async ({ page }) => {
    test.setTimeout(180_000)
    user = await createOnboardingUser()
    loadSample(user.id)
    await signIn(page, user.email)
  })

  test.afterEach(async () => {
    await deleteUser(user.id)
  })

  test('C25 shows the sample', async ({ page }) => {
    await openDashboard(page)
    await raiseMinimum(page)
    await page.reload()
    const api = await getDashboard(page)

    const cash = page.getByRole('region', { name: 'Cash on hand' })
    await expect(cash).toContainText('$42,300')
    await expect(cash).toContainText('Operating + Reserve · 2 accounts')
    await expect(page.getByRole('region', { name: 'Available credit' })).toContainText('$20,000')
    await expect(page.getByTestId('status-line')).toContainText('Updated Sep 26 at 6:02 AM · 2 banks synced')
    const low = api.projected_low as NonNullable<typeof api.projected_low>
    await expect(page.getByRole('region', { name: 'Projected low' })).toContainText(money(low.balance_cents))

    const accounts = page.getByRole('region', { name: 'Accounts' })
    for (const [name, amount] of [
      ['Operating checking', '$8,000'],
      ['Reserve savings', '$34,300'],
      ['Business Visa', '$2,450'],
      ['Line of credit', '$20,000'],
    ]) {
      await expect(accounts.getByRole('listitem').filter({ hasText: name })).toContainText(amount)
    }

    await expect(page.getByTestId('alert-card')).toHaveCount(api.alerts.length)
    await expect(page.locator('[data-slot="chart"]')).toHaveAttribute('data-points', '14')
    expect(api.forecast?.weeks).toHaveLength(13)
    await expect(page.getByTestId('upcoming-table').locator('tbody tr')).toHaveCount(api.upcoming.length)
  })

  test('C26 dismisses an alert', async ({ page }) => {
    await openDashboard(page)
    await raiseMinimum(page)
    await page.reload()
    const { alerts } = await getDashboard(page)
    const first = page.getByTestId('alert-card').first()
    await first.getByRole('button', { name: 'Dismiss' }).click()
    await expect(page.getByText('Alert dismissed')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByTestId('alert-card')).toHaveCount(alerts.length - 1)
    const dismissed = await callApi(page, 'GET', (id) => `/v1/businesses/${id}/alerts?state=dismissed`)
    expect(dismissed.items.map((a: { id: string }) => a.id)).toContain(alerts[0].id)
  })

  test('C27 adds an expected payment from the dashboard', async ({ page }) => {
    await openDashboard(page)
    const day = await page.evaluate(() => {
      const d = new Date()
      d.setDate(d.getDate() + 3)
      const pad = (n: number) => String(n).padStart(2, '0')
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
    })
    await page.getByRole('button', { name: 'Add expected payment' }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog.getByRole('heading', { name: 'Add expected payment' })).toBeVisible()
    await dialog.getByRole('radio', { name: 'Money in' }).click()
    await dialog.getByLabel('Amount').fill('1,234')
    await dialog.getByLabel('Date').fill(day)
    await dialog.getByLabel('Description').fill('Dashboard test payment')
    await dialog.getByRole('button', { name: 'Add payment' }).click()
    await expect(dialog).toBeHidden({ timeout: 30_000 })
    await expect
      .poll(
        async () => {
          await page.reload()
          return page.getByTestId('upcoming-table').getByRole('row').filter({ hasText: 'Dashboard test payment' }).count()
        },
        { timeout: 30_000 },
      )
      .toBe(1)
    await expect(page.getByTestId('upcoming-table').getByRole('row').filter({ hasText: 'Dashboard test payment' })).toContainText(
      '+$1,234',
    )
  })

  test('C33 sample owner sees the out-of-date banner', async ({ page }) => {
    await openDashboard(page)
    const banner = page.getByText('Some bank data is more than 2 days old, so this forecast may be off.')
    await expect(banner).toBeVisible()
    const order = await banner.evaluate((el) => {
      const card = document.querySelector('[data-testid="summary-card"]')
      return card ? Boolean(el.compareDocumentPosition(card) & Node.DOCUMENT_POSITION_FOLLOWING) : false
    })
    expect(order).toBe(true)
  })

  test('C35 axe finds no violations on the sample', async ({ page }) => {
    await openDashboard(page)
    await raiseMinimum(page)
    for (const viewport of [PHONE, WIDE]) {
      await page.setViewportSize(viewport)
      await page.reload()
      await settle(page)
      const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze()
      expect(results.violations, `${viewport.width}px`).toEqual([])
    }
  })

  test('C36 fits a phone', async ({ page }) => {
    await page.setViewportSize(PHONE)
    await openDashboard(page)
    await raiseMinimum(page)
    await page.reload()
    await settle(page)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
    const small = await page.locator('main').evaluate((main) =>
      Array.from(main.querySelectorAll('a, button'))
        .filter((el) => (el as HTMLElement).offsetParent !== null)
        .map((el) => ({ text: el.textContent?.trim(), box: el.getBoundingClientRect() }))
        .filter(({ box }) => box.width < 44 || box.height < 44)
        .map(({ text, box }) => `${text} ${Math.round(box.width)}x${Math.round(box.height)}`),
    )
    expect(small).toEqual([])
  })

  test('C37 works by keyboard', async ({ page }) => {
    await openDashboard(page)
    await raiseMinimum(page)
    await page.reload()
    await settle(page)
    await page.keyboard.press('Tab')
    const accent = await page.evaluate(() => {
      const probe = document.createElement('span')
      probe.style.color = 'var(--accent)'
      document.body.append(probe)
      const color = getComputedStyle(probe).color
      probe.remove()
      return color
    })
    const targets = [
      page.getByRole('button', { name: 'Add expected payment' }),
      page.getByTestId('alert-card').first().getByRole('link', { name: /^See / }),
      page.getByTestId('alert-card').first().getByRole('button', { name: 'Dismiss' }),
      page.getByRole('region', { name: 'Accounts' }).getByRole('link', { name: 'Manage' }),
    ]
    for (const target of targets) {
      await tabTo(page, target)
      await expect(target).toBeFocused()
      // Buttons animate their colours; read the outline once the transition has settled.
      await expect
        .poll(() =>
          target.evaluate((el) => {
            const style = getComputedStyle(el)
            return { width: style.outlineWidth, color: style.outlineColor }
          }),
        )
        .toEqual({ width: '2px', color: accent })
    }
    await page.keyboard.press('Shift+Tab')
    await tabTo(page, targets[0], 80)
    await page.keyboard.press('Enter')
    await expect(page.getByRole('dialog')).toBeVisible()
  })
})

test.describe('the dashboard without a bank', () => {
  test.use({ storageState: SIGNED_OUT, viewport: PHONE })

  let user: { id: string; email: string }

  test.beforeEach(async ({ page }) => {
    test.setTimeout(120_000)
    user = await createOnboardingUser()
    await signIn(page, user.email)
    await page.goto('/')
    await expect.poll(() => new URL(page.url()).pathname).toBe('/onboarding/business')
    await completeBusinessStep(page, `Harbor ${Date.now()}`)
    await page.goto('/')
  })

  test.afterEach(async () => {
    await deleteUser(user.id)
  })

  test('C33 shows the empty state', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'No bank connected yet' })).toBeVisible({ timeout: 30_000 })
    await expect(page.getByRole('link', { name: 'Connect your bank' })).toHaveAttribute('href', '/onboarding/bank')
  })

  test('C35 axe finds no violations on the empty state', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'No bank connected yet' })).toBeVisible({ timeout: 30_000 })
    await page.waitForTimeout(1000)
    const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze()
    expect(results.violations).toEqual([])
  })
})
