import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page } from '@playwright/test'

const URL = '/dev/components'
const WHITE = 'rgb(255, 255, 255)'

async function css(locator: Locator, property: string): Promise<string> {
  return locator.evaluate(
    (el, prop) => getComputedStyle(el).getPropertyValue(prop),
    property,
  )
}

async function box(locator: Locator) {
  const b = await locator.boundingBox()
  if (!b) throw new Error('element has no box')
  return b
}

// Colour transitions and open animations change computed values for a few hundred ms; read the
// settled state. Infinite animations (the skeleton pulse) never finish, so they are skipped.
async function settle(page: Page) {
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getComputedTiming().iterations !== Infinity)
        .map((a) => a.finished.catch(() => undefined)),
    ),
  )
}

function section(page: Page, name: string): Locator {
  return page.getByRole('region', { name, exact: true })
}

function fontStack(value: string): string[] {
  return value.split(',').map((family) => family.trim().replace(/^["']|["']$/g, ''))
}

function expectInOrder(stack: string[], expected: string[]) {
  const positions = expected.map((family) => stack.indexOf(family))
  expect(positions.every((p) => p >= 0), `${stack.join(', ')} has ${expected.join(', ')}`).toBe(true)
  expect([...positions].sort((a, b) => a - b)).toEqual(positions)
}

test.describe('theme', () => {
  test('dark os keeps light theme (C4)', async ({ browser }) => {
    const context = await browser.newContext({ colorScheme: 'dark' })
    const page = await context.newPage()
    await page.goto(URL)
    const body = page.locator('body')
    expect(await css(body, 'background-color')).toBe('rgb(245, 243, 238)')
    expect(await css(body, 'color')).toBe('rgb(22, 32, 43)')
    await context.close()
  })

  test('body font is plex (C5)', async ({ page }) => {
    await page.goto(URL)
    const stack = fontStack(await css(page.locator('body'), 'font-family'))
    expect(stack[0]).toMatch(/IBM Plex Sans/)
    expectInOrder(stack, [stack[0], 'Segoe UI', 'system-ui', 'sans-serif'])
  })

  test('heading font is fraunces (C6)', async ({ page }) => {
    await page.goto(URL)
    const stack = fontStack(await css(page.getByRole('heading', { level: 1 }), 'font-family'))
    expect(stack[0]).toMatch(/Fraunces/)
    expectInOrder(stack, [stack[0], 'Georgia', 'serif'])
  })

  test('tabular numbers (C8)', async ({ page }) => {
    await page.goto(URL)
    expect(await css(page.locator('body'), 'font-variant-numeric')).toBe('tabular-nums')
  })
})

test.describe('components', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(URL)
  })

  const VARIANTS: Array<[string, 'button' | 'link', string, Record<string, string>]> = [
    ['primary', 'button', 'Primary: Add expected payment', { 'background-color': 'rgb(29, 78, 137)', color: WHITE }],
    ['secondary', 'button', 'Secondary: Dismiss', { 'background-color': WHITE, 'border-top-color': 'rgb(214, 208, 196)' }],
    ['outline', 'button', 'Outline: See all fixes', { 'background-color': WHITE, 'border-top-color': 'rgb(22, 32, 43)' }],
    ['link', 'link', 'Text link: Manage', { color: 'rgb(29, 78, 137)' }],
    ['destructive', 'button', 'Destructive: Disconnect', { color: 'rgb(142, 27, 27)', 'border-top-color': 'rgb(239, 199, 194)' }],
  ]
  for (const [variant, role, name, colours] of VARIANTS) {
    test(`button variant ${variant} (C10)`, async ({ page }) => {
      const control = section(page, 'Buttons').getByRole(role, { name })
      expect((await box(control)).height).toBeGreaterThanOrEqual(44)
      expect(await css(control, 'border-top-left-radius')).toBe('10px')
      expect(await css(control, 'font-size')).toBe('15px')
      for (const [property, value] of Object.entries(colours)) {
        expect(await css(control, property), property).toBe(value)
      }
    })
  }

  test('disabled button (C11)', async ({ page }) => {
    const control = section(page, 'Buttons').getByRole('button', { name: 'Disabled: Continue' })
    expect(await css(control, 'background-color')).toBe('rgb(233, 229, 220)')
    expect(await css(control, 'color')).toBe('rgb(90, 99, 112)')
    expect(await css(control, 'opacity')).toBe('1')
  })

  test('field metrics (C12)', async ({ page }) => {
    const fields = [
      page.getByLabel('Business name'),
      page.getByRole('combobox', { name: 'Province or territory' }),
    ]
    for (const field of fields) {
      expect((await box(field)).height).toBe(48)
      expect(await css(field, 'font-size')).toBe('16px')
      expect(await css(field, 'border-top-left-radius')).toBe('10px')
      expect(await css(field, 'border-top-width')).toBe('1px')
      expect(await css(field, 'border-top-color')).toBe('rgb(214, 208, 196)')
    }
  })

  test('invalid field (C13)', async ({ page }) => {
    const amount = section(page, 'Form controls').getByLabel('Amount')
    await expect(amount).toHaveAttribute('aria-invalid', 'true')
    expect(await css(amount, 'border-top-width')).toBe('2px')
    expect(await css(amount, 'border-top-color')).toBe('rgb(142, 27, 27)')
    const describedBy = await amount.getAttribute('aria-describedby')
    expect(describedBy).toBeTruthy()
    await expect(page.locator(`[id="${describedBy}"]`)).toHaveText('Enter an amount greater than $0.')
  })

  test('touch target (C14)', async ({ page }) => {
    const form = section(page, 'Form controls')
    const targets = [
      ...(await form.getByRole('switch').all()),
      form.locator('label', { hasText: 'Primary account' }),
      form.locator('label', { hasText: 'Make primary' }),
      ...(await form.getByRole('radiogroup', { name: 'Direction' }).getByRole('radio').all()),
    ]
    expect(targets).toHaveLength(6)
    for (const target of targets) {
      const b = await box(target)
      expect(b.width).toBeGreaterThanOrEqual(44)
      expect(b.height).toBeGreaterThanOrEqual(44)
    }
  })

  test('segmented control (C15)', async ({ page }) => {
    const group = page.getByRole('radiogroup', { name: 'Direction' })
    const out = group.getByRole('radio', { name: 'Money out' })
    const into = group.getByRole('radio', { name: 'Money in' })
    expect(await css(out, 'background-color')).toBe(WHITE)
    expect(await css(out, 'box-shadow')).not.toBe('none')
    expect(await css(into, 'background-color')).toBe('rgba(0, 0, 0, 0)')
    await into.click()
    await expect(into).toHaveAttribute('aria-checked', 'true')
    await settle(page)
    expect(await css(into, 'background-color')).toBe(WHITE)
    expect(await css(into, 'box-shadow')).not.toBe('none')
    expect(await css(out, 'background-color')).toBe('rgba(0, 0, 0, 0)')
  })

  const BADGES: Array<[string, string, string, string]> = [
    ['neutral', 'Primary', WHITE, 'rgb(69, 79, 92)'],
    ['muted', 'Recurring', 'rgb(241, 238, 231)', 'rgb(69, 79, 92)'],
    ['positive', 'Synced', 'rgb(234, 244, 238)', 'rgb(30, 107, 69)'],
    ['warning', 'Needs attention', 'rgb(255, 244, 226)', 'rgb(122, 67, 0)'],
    ['danger', 'Overdraws Operating', 'rgb(142, 27, 27)', WHITE],
  ]
  for (const [variant, label, background, color] of BADGES) {
    test(`badge variant ${variant} (C16)`, async ({ page }) => {
      const badge = section(page, 'Badges').getByText(label, { exact: true })
      await expect(badge).toHaveAttribute('data-variant', variant)
      expect(await css(badge, 'background-color')).toBe(background)
      expect(await css(badge, 'color')).toBe(color)
      expect(await css(badge, 'border-top-left-radius')).toBe('6px')
    })
  }

  test('card style (C17)', async ({ page }) => {
    const card = section(page, 'Form controls').locator('[data-slot="card"]')
    expect(await css(card, 'background-color')).toBe(WHITE)
    expect(await css(card, 'border-top-width')).toBe('1px')
    expect(await css(card, 'border-top-color')).toBe('rgb(226, 221, 211)')
    expect(await css(card, 'border-top-left-radius')).toBe('14px')
  })

  test('dialog desktop (C18)', async ({ page }) => {
    await page.getByRole('button', { name: 'Open dialog' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await settle(page)
    const b = await box(page.getByRole('dialog'))
    expect(Math.round(b.width)).toBe(480)
    expect(Math.abs(b.x - (1440 - (b.x + b.width)))).toBeLessThanOrEqual(1)
  })

  test('focus ring (C21)', async ({ page }) => {
    const last = page.getByRole('button', { name: 'Show toast' })
    let reached = 0
    for (let i = 0; i < 40; i += 1) {
      await page.keyboard.press('Tab')
      await settle(page)
      const ring = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement
        const s = getComputedStyle(el)
        return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.outlineOffset, el.textContent]
      })
      expect(ring.slice(0, 4), `focus ring on "${ring[4]}"`).toEqual(['solid', '2px', 'rgb(29, 78, 137)', '2px'])
      reached += 1
      if (await last.evaluate((el) => el === document.activeElement)) break
    }
    await expect(last).toBeFocused()
    expect(reached).toBeGreaterThanOrEqual(17)
  })
})

test('dialog phone (C19)', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto(URL)
  await page.getByRole('button', { name: 'Open dialog' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await settle(page)
  const b = await box(page.getByRole('dialog'))
  expect([Math.round(b.x), Math.round(b.y), Math.round(b.width), Math.round(b.height)]).toEqual([0, 0, 375, 812])
})

test('toast lasts 4 seconds (C20)', async ({ page }) => {
  await page.goto(URL)
  const toast = page.locator('[data-sonner-toast]')
  const shownAt = Date.now()
  await page.getByRole('button', { name: 'Show toast' }).click()
  await expect(toast).toBeVisible()
  await page.waitForTimeout(3500 - (Date.now() - shownAt))
  await expect(toast).toBeVisible()
  await expect(toast).toHaveCount(0, { timeout: Math.max(5000 - (Date.now() - shownAt), 1) })
})

test('toast stays light under a dark os (C20)', async ({ browser }) => {
  const context = await browser.newContext({ colorScheme: 'dark' })
  const page = await context.newPage()
  await page.goto(URL)
  await page.getByRole('button', { name: 'Show toast' }).click()
  const toast = page.locator('[data-sonner-toast]')
  await expect(toast).toBeVisible()
  expect(await css(toast, 'background-color')).toBe(WHITE)
  await context.close()
})

test('reduced motion (C22)', async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: 'reduce' })
  const page = await context.newPage()
  await page.goto(URL)
  await page.getByRole('button', { name: 'Open dialog' }).click()
  const content = page.locator('[data-slot="dialog-content"]')
  await expect(content).toBeVisible()
  const seconds = parseFloat(await css(content, 'animation-duration'))
  expect(seconds).toBeLessThanOrEqual(0.00001)
  await context.close()
})

test.describe('mockup', () => {
  test('sections in order (C24)', async ({ page }) => {
    const response = await page.goto(URL)
    expect(response?.status()).toBe(200)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Components and states')
    await expect(page.getByRole('heading', { level: 2 })).toHaveText([
      'Colors',
      'Type',
      'Buttons',
      'Form controls',
      'Badges',
      'Alert cards',
      'States',
      'Dialog and toast',
    ])
  })

  test('colour swatches (C25)', async ({ page }) => {
    await page.goto(URL)
    const swatches: Array<[string, string]> = [
      ['Background', '--bg · #F5F3EE'],
      ['Surface', '--surface · #FFFFFF'],
      ['Surface muted', '--surface-muted · #F1EEE7'],
      ['Border', '--border · #E2DDD3'],
      ['Ink', '--ink · #16202B'],
      ['Ink 2', '--ink-2 · #454F5C'],
      ['Ink 3', '--ink-3 · #5A6370'],
      ['Accent', '--accent · #1D4E89'],
      ['Positive', '--positive · #1E6B45'],
      ['Warning background', '--warning-bg · #FFF4E2'],
      ['Warning text', '--warning-text · #7A4300'],
      ['Warning line', '--warning-line · #B26B00'],
      ['Danger background', '--danger-bg · #FCEDEB'],
      ['Danger text', '--danger-text · #8E1B1B'],
    ]
    const items = section(page, 'Colors').getByRole('listitem')
    await expect(items).toHaveCount(14)
    for (const [i, [name, caption]] of swatches.entries()) {
      await expect(items.nth(i).getByText(name, { exact: true })).toBeVisible()
      await expect(items.nth(i).getByText(caption, { exact: true })).toBeVisible()
    }
  })

  test('type scale (C26)', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(URL)
    const rows: Array<[string, string, string]> = [
      ['Cash flow', '40px', '600'],
      ['$42,300', '36px', '600'],
      ['Cash falls below your $5,000 minimum the week of Nov 9', '19px', '600'],
      ['13-week forecast', '18px', '600'],
      ['Payroll of $11,200 leaves Operating checking on Friday, Oct 2.', '15px', '400'],
      ['Updated today at 6:02 AM', '13px', '400'],
      ['Cash gap', '12px', '600'],
    ]
    const type = section(page, 'Type')
    await expect(type.getByRole('listitem')).toHaveCount(7)
    for (const [text, size, weight] of rows) {
      const sample = type.getByText(text, { exact: true })
      expect(await css(sample, 'font-size'), text).toBe(size)
      expect(await css(sample, 'font-weight'), text).toBe(weight)
    }
    expect(await css(type.getByText('Cash gap', { exact: true }), 'text-transform')).toBe('uppercase')
  })

  test('button labels (C27)', async ({ page }) => {
    await page.goto(URL)
    await expect(section(page, 'Buttons').locator('button, a')).toHaveText([
      'Primary: Add expected payment',
      'Secondary: Dismiss',
      'Outline: See all fixes',
      'Text link: Manage',
      'Destructive: Disconnect',
      'Disabled: Continue',
    ])
  })

  test('form controls (C28)', async ({ page }) => {
    await page.goto(URL)
    const form = section(page, 'Form controls')
    await expect(form.getByRole('textbox', { name: 'Business name' })).toHaveValue('Harbor Street Plumbing')
    await expect(form.getByText('Hint text sits under the field.', { exact: true })).toBeVisible()
    await expect(form.getByRole('textbox', { name: 'Amount' })).toBeVisible()
    await expect(form.getByText('$', { exact: true })).toBeVisible()
    await expect(form.getByText('Enter an amount greater than $0.', { exact: true })).toBeVisible()
    await expect(form.getByRole('combobox', { name: 'Province or territory' })).toHaveText('Ontario')
    const switches = form.getByRole('switch', { name: 'Counts as cash' })
    await expect(switches).toHaveCount(2)
    await expect(switches.nth(0)).toHaveAttribute('aria-checked', 'true')
    await expect(switches.nth(1)).toHaveAttribute('aria-checked', 'false')
    await expect(form.getByRole('radio', { name: 'Primary account' })).toHaveAttribute('aria-checked', 'true')
    await expect(form.getByRole('radio', { name: 'Make primary' })).toHaveAttribute('aria-checked', 'false')
    await expect(form.getByRole('radiogroup', { name: 'Direction' }).getByRole('radio')).toHaveText([
      'Money out',
      'Money in',
    ])
  })

  test('badge labels (C29)', async ({ page }) => {
    await page.goto(URL)
    await expect(section(page, 'Badges').locator('[data-slot="badge"]')).toHaveText([
      'Primary',
      'Recurring',
      'Expected',
      'Synced',
      'Needs attention',
      'Overdraws Operating',
    ])
  })

  test('alert cards (C30)', async ({ page }) => {
    await page.goto(URL)
    const cards = section(page, 'Alert cards').getByRole('article')
    await expect(cards).toHaveCount(2)
    expect(await css(cards.nth(0), 'background-color')).toBe('rgb(255, 244, 226)')
    await expect(cards.nth(0).getByText('Cash gap · warning', { exact: true })).toBeVisible()
    await expect(
      cards.nth(0).getByText('Cash falls below your $5,000 minimum the week of Nov 9', { exact: true }),
    ).toBeVisible()
    expect(await css(cards.nth(1), 'background-color')).toBe('rgb(252, 237, 235)')
    await expect(cards.nth(1).getByText('Account shortfall · danger (later)', { exact: true })).toBeVisible()
    await expect(
      cards.nth(1).getByText('Operating checking will be overdrawn on Friday, Oct 2', { exact: true }),
    ).toBeVisible()
  })

  test('state cards (C31)', async ({ page }) => {
    await page.goto(URL)
    const states = section(page, 'States')
    const loading = states.locator('[data-slot="card"]', { hasText: 'Loading' })
    expect(await loading.locator('[data-slot="skeleton"]').count()).toBeGreaterThanOrEqual(4)
    const withIcons: Array<[Locator, string]> = [
      [states.locator('[data-slot="card"]', { hasText: 'No bank connected yet' }), 'Connect your bank'],
      [states.locator('[data-slot="card"]', { hasText: "We couldn't load your forecast" }), 'Try again'],
      [states.getByTestId('partial-banner'), 'Reconnect'],
    ]
    for (const [card, action] of withIcons) {
      await expect(card.getByRole('button', { name: action })).toBeVisible()
      await expect(card.locator('svg[aria-hidden="true"]')).toHaveCount(1)
    }
  })

  test('dialog and toast section (C32)', async ({ page }) => {
    await page.goto(URL)
    const demo = section(page, 'Dialog and toast')
    await demo.getByRole('button', { name: 'Open dialog' }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog.getByRole('heading')).toHaveCount(1)
    await expect(dialog.getByRole('textbox')).toHaveCount(1)
    const labels = await dialog.getByRole('button').allTextContents()
    const cancel = labels.indexOf('Cancel')
    expect(cancel).toBeGreaterThanOrEqual(0)
    const primary = dialog.getByRole('button').nth(cancel + 1)
    await expect(primary).toHaveAttribute('data-variant', 'primary')
    await page.keyboard.press('Escape')
    await demo.getByRole('button', { name: 'Show toast' }).click()
    await expect(page.locator('[data-sonner-toast]')).toContainText('Expected payment added')
  })
})

test.describe('access', () => {
  for (const [width, height] of [[1440, 900], [375, 812]]) {
    test(`axe at ${width} (C34)`, async ({ page }) => {
      await page.setViewportSize({ width, height })
      await page.goto(URL)
      await expect(section(page, 'Colors').getByText('--bg · #F5F3EE')).toBeVisible()
      // The Next.js dev tools overlay is not part of the page under test.
      const results = await new AxeBuilder({ page }).exclude('nextjs-portal').analyze()
      expect(results.violations).toEqual([])
    })
  }

  test('phone layout (C35)', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto(URL)
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(375)
    const below = async (first: Locator, second: Locator) => {
      const a = await box(first)
      const b = await box(second)
      expect(b.y).toBeGreaterThanOrEqual(a.y + a.height)
    }
    const swatches = section(page, 'Colors').getByRole('listitem')
    await below(swatches.nth(0), swatches.nth(1))
    await below(page.getByLabel('Business name'), section(page, 'Form controls').getByLabel('Amount'))
    const cards = section(page, 'States').locator('[data-slot="card"]')
    await below(cards.nth(0), cards.nth(1))
  })

  test('page width (C36)', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1000 })
    await page.goto(URL)
    const main = page.locator('main')
    expect(await css(main, 'padding-left')).toBe('48px')
    expect(await css(main, 'padding-right')).toBe('48px')
    const content = await main.evaluate((el) => el.clientWidth - 96)
    expect(content).toBeLessThanOrEqual(1344)
    await page.setViewportSize({ width: 375, height: 812 })
    expect(await css(main, 'padding-left')).toBe('16px')
    expect(await css(main, 'padding-right')).toBe('16px')
  })

  test('keyboard order (C37)', async ({ page }) => {
    await page.goto(URL)
    const buttons = section(page, 'Buttons')
    const form = section(page, 'Form controls')
    const order: Locator[] = [
      buttons.getByRole('button', { name: 'Primary: Add expected payment' }),
      buttons.getByRole('button', { name: 'Secondary: Dismiss' }),
      buttons.getByRole('button', { name: 'Outline: See all fixes' }),
      buttons.getByRole('link', { name: 'Text link: Manage' }),
      buttons.getByRole('button', { name: 'Destructive: Disconnect' }),
      buttons.getByRole('button', { name: 'Disabled: Continue' }),
      form.getByLabel('Business name'),
      form.getByLabel('Amount'),
      form.getByRole('combobox', { name: 'Province or territory' }),
      form.getByRole('switch').nth(0),
      form.getByRole('switch').nth(1),
      form.getByRole('radio', { name: 'Primary account' }),
      form.getByRole('radiogroup', { name: 'Direction' }).getByRole('radio', { name: 'Money out' }),
      page.getByRole('button', { name: 'Connect your bank' }),
      page.getByRole('button', { name: 'Try again' }),
      page.getByRole('button', { name: 'Reconnect' }),
      page.getByRole('button', { name: 'Open dialog' }),
    ]
    for (const target of order) {
      await page.keyboard.press('Tab')
      await expect(target).toBeFocused()
    }
    await page.keyboard.press('Enter')
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toBeHidden()
    await expect(page.getByRole('button', { name: 'Open dialog' })).toBeFocused()
  })
})
