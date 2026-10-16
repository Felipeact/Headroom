import AxeBuilder from '@axe-core/playwright'
import { clerk } from '@clerk/testing/playwright'
import { expect, test, type Page } from '@playwright/test'
import { callApi, getDashboard, loadSample, money, raiseMinimum } from './dashboard-steps'
import { tabTo } from './onboarding-steps'
import { createOnboardingUser, deleteUser, SIGNED_OUT } from './test-user'

// Spec 27. The sample's forecast is computed on the real clock, so every value is read from the
// owner's own GET .../alerts/{id}.

const WIDE = { width: 1280, height: 900 }
const PHONE = { width: 375, height: 812 }
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']
const UNKNOWN = '00000000-0000-0000-0000-000000000000'

type AlertJson = {
  id: string
  lowest_week_starts_on: string
  lowest_balance_cents: number
  minimum_cents: number
  shortfall_cents: number
  items: { kind: 'cause' | 'arrives_after' }[]
  fixes: { new_lowest_balance_cents: number }[]
}

/** "Nov 9" for a plain date, as lib/format.ts writes it. */
const shortDate = (iso: string) =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'UTC', month: 'short', day: 'numeric' }).format(new Date(`${iso}T00:00:00Z`))

async function signIn(page: Page, email: string) {
  await page.goto('/sign-in')
  await clerk.signIn({ page, emailAddress: email })
}

/** The sample's first alert, with its page open. */
async function openFirstAlert(page: Page): Promise<AlertJson> {
  const { alerts } = await getDashboard(page)
  const alert: AlertJson = await callApi(page, 'GET', (id) => `/v1/businesses/${id}/alerts/${alerts[0].id}`)
  await page.goto(`/alerts/${alert.id}`)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 30_000 })
  return alert
}

test.describe('the alert page with the sample', () => {
  test.use({ storageState: SIGNED_OUT, timezoneId: 'America/Toronto', viewport: PHONE })

  let user: { id: string; email: string }

  test.beforeEach(async ({ page }) => {
    test.setTimeout(180_000)
    user = await createOnboardingUser()
    loadSample(user.id)
    await signIn(page, user.email)
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1, name: 'Cash flow' })).toBeVisible({ timeout: 30_000 })
    await raiseMinimum(page)
  })

  test.afterEach(async () => {
    await deleteUser(user.id)
  })

  test('C15 opens from the dashboard and shows the alert', async ({ page }) => {
    await page.reload()
    const { alerts } = await getDashboard(page)
    const alert: AlertJson = await callApi(page, 'GET', (id) => `/v1/businesses/${id}/alerts/${alerts[0].id}`)
    await page.getByTestId('alert-card').first().getByRole('link', { name: /^See / }).click()
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 30_000 }).toBe(`/alerts/${alert.id}`)
    const response = await page.goto(`/alerts/${alert.id}`)
    expect(response?.status()).toBe(200)

    await expect(page.getByRole('heading', { level: 1 })).toHaveText(
      `Cash falls below your ${money(alert.minimum_cents)} minimum the week of ${shortDate(alert.lowest_week_starts_on)}`,
    )
    const low = page.getByTestId('projected-low')
    await expect(low).toContainText(money(alert.lowest_balance_cents))
    await expect(low).toContainText(`Week of ${shortDate(alert.lowest_week_starts_on)}`)
    await expect(page.getByTestId('short-by')).toContainText(money(alert.shortfall_cents))
    const causes = alert.items.filter((i) => i.kind === 'cause').length
    const arrives = alert.items.filter((i) => i.kind === 'arrives_after').length
    await expect(page.getByTestId('cause-row')).toHaveCount(causes)
    await expect(page.getByTestId('arrives-row')).toHaveCount(arrives)
    const cards = page.getByTestId('fix-card')
    await expect(cards).toHaveCount(alert.fixes.length)
    for (const [i, fix] of alert.fixes.entries()) {
      await expect(cards.nth(i).getByTestId('fix-result')).toContainText(money(fix.new_lowest_balance_cents))
    }

    const order = await page.getByTestId('alert-page').evaluate((root) => {
      const pick = (selector: string) => Array.from(root.querySelectorAll(selector))
      const sequence = [
        ...pick('[data-testid="projected-low"]'),
        ...pick('[data-testid="short-by"]'),
        ...pick('[data-testid="cause-row"]'),
        ...pick('[data-testid="arrives-row"]'),
        ...pick('[data-testid="fix-card"]'),
        ...pick('button'),
      ]
      return sequence.every((el, i) => i === 0 || sequence[i - 1].compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)
    })
    expect(order).toBe(true)
    await expect(page.getByRole('button', { name: 'Dismiss alert' })).toBeVisible()
  })

  test('C20 dismisses and returns to the dashboard', async ({ page }) => {
    const alert = await openFirstAlert(page)
    await page.getByRole('button', { name: 'Dismiss alert' }).click()
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 30_000 }).toBe('/')
    await expect(page.getByText('Alert dismissed')).toBeVisible({ timeout: 15_000 })
    await expect(page.locator(`[id="alert-${alert.id}"]`)).toHaveCount(0)
    await page.reload()
    await expect(page.getByRole('heading', { level: 1, name: 'Cash flow' })).toBeVisible({ timeout: 30_000 })
    await expect(page.locator(`[id="alert-${alert.id}"]`)).toHaveCount(0)
    const dismissed = await callApi(page, 'GET', (id) => `/v1/businesses/${id}/alerts?state=dismissed`)
    expect(dismissed.items.map((a: { id: string }) => a.id)).toContain(alert.id)
  })

  test('C25 unknown and malformed ids show the not-found state', async ({ page }) => {
    for (const id of [UNKNOWN, 'not-a-uuid']) {
      await page.goto(`/alerts/${id}`)
      await expect(page.getByRole('heading', { name: "We couldn't find this alert" })).toBeVisible({ timeout: 30_000 })
      await expect(page.locator('meta[name="robots"]').first()).toHaveAttribute('content', /noindex/)
      await expect(page.getByRole('link', { name: 'Go to the dashboard' })).toHaveAttribute('href', '/')
      await expect(page.locator('header')).toBeVisible()
    }
  })

  test('C28 fits a phone and keeps one column on desktop', async ({ page }) => {
    await openFirstAlert(page)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
    const small = await page.locator('main').evaluate((main) =>
      Array.from(main.querySelectorAll('a, button'))
        .filter((el) => (el as HTMLElement).offsetParent !== null)
        .map((el) => ({ text: el.textContent?.trim(), box: el.getBoundingClientRect() }))
        .filter(({ box }) => box.width < 44 || box.height < 44)
        .map(({ text, box }) => `${text} ${Math.round(box.width)}x${Math.round(box.height)}`),
    )
    expect(small).toEqual([])
    const dismiss = await page.getByRole('button', { name: 'Dismiss alert' }).boundingBox()
    const card = await page.getByTestId('fix-card').first().boundingBox()
    expect(Math.abs((dismiss?.width ?? 0) - (card?.width ?? -10))).toBeLessThanOrEqual(1)

    await page.setViewportSize(WIDE)
    const column = await page.getByTestId('alert-page').boundingBox()
    expect(column?.width).toBeLessThanOrEqual(640)
  })

  test('C29 works by keyboard', async ({ page }) => {
    await openFirstAlert(page)
    const accent = await page.evaluate(() => {
      const probe = document.createElement('span')
      probe.style.color = 'var(--accent)'
      document.body.append(probe)
      const color = getComputedStyle(probe).color
      probe.remove()
      return color
    })
    const back = page.getByTestId('alert-page').getByRole('link', { name: 'Dashboard' })
    const dismiss = page.getByRole('button', { name: 'Dismiss alert' })
    for (const target of [back, dismiss]) {
      await tabTo(page, target)
      await expect(target).toBeFocused()
      await expect
        .poll(() =>
          target.evaluate((el) => {
            const style = getComputedStyle(el)
            return { width: style.outlineWidth, color: style.outlineColor }
          }),
        )
        .toEqual({ width: '2px', color: accent })
    }
    await page.keyboard.press('Enter')
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 30_000 }).toBe('/')
  })

  test('C30 axe finds no violations', async ({ page }) => {
    const alert = await openFirstAlert(page)
    for (const viewport of [PHONE, WIDE]) {
      await page.setViewportSize(viewport)
      await page.goto(`/alerts/${alert.id}`)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 30_000 })
      const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze()
      expect(results.violations, `${viewport.width}px`).toEqual([])
    }
    await page.setViewportSize(PHONE)
    await page.goto(`/alerts/${UNKNOWN}`)
    await expect(page.getByRole('heading', { name: "We couldn't find this alert" })).toBeVisible({ timeout: 30_000 })
    const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze()
    expect(results.violations, 'not found').toEqual([])
  })
})

test.describe('the alert page signed out', () => {
  test.use({ storageState: SIGNED_OUT })

  test('C27 redirects to sign-in', async ({ page }) => {
    await page.goto(`/alerts/${UNKNOWN}`)
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 30_000 }).toBe('/sign-in')
  })
})
