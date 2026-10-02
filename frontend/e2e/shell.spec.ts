import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page } from '@playwright/test'
import messages from '../messages/en.json'

const PAGES = [
  { path: '/', title: 'Dashboard' },
  { path: '/expected-payments', title: 'Expected payments' },
  { path: '/alerts', title: 'Alerts' },
  { path: '/settings', title: 'Settings' },
] as const

const NAV_ORDER = PAGES.map(({ title, path }) => ({ name: title, href: path }))

const DESKTOP = { width: 1440, height: 900 }
const PHONE = { width: 375, height: 812 }

function messageValues(node: unknown): string[] {
  if (typeof node === 'string') return [node]
  return Object.values(node as Record<string, unknown>).flatMap(messageValues)
}
const MESSAGE_VALUES = new Set(messageValues(messages))

async function css(locator: Locator, property: string): Promise<string> {
  return locator.evaluate((el, prop) => getComputedStyle(el).getPropertyValue(prop), property)
}

// Colour transitions change computed values for a few hundred ms; read the settled state.
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

function mainNav(page: Page): Locator {
  return page.getByRole('navigation', { name: 'Main', exact: true })
}

// Every non-blank text node and aria-label in the page, minus the Next.js dev tools overlay.
async function pageStrings(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const found: string[] = []
    const skip = (el: Element | null) =>
      !!el?.closest('nextjs-portal, script, style, noscript, template, next-route-announcer')
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.textContent?.trim()
      if (text && !skip(node.parentElement)) found.push(text)
    }
    for (const el of document.body.querySelectorAll('[aria-label]')) {
      if (!skip(el)) found.push(el.getAttribute('aria-label') ?? '')
    }
    return found
  })
}

test('shell pages (C1)', async ({ page }) => {
  for (const { path, title } of PAGES) {
    const response = await page.goto(path)
    expect(response?.status(), path).toBe(200)
    await expect(page.locator('header')).toHaveCount(1)
    await expect(page.locator('main')).toHaveCount(1)
    await expect(page.locator('main h1')).toHaveText(title)
  }
})

test.describe('desktop', () => {
  test.use({ viewport: DESKTOP })

  test('wordmark (C2)', async ({ page }) => {
    await page.goto('/')
    const wordmark = page.getByTestId('header-desktop-identity').getByText('Headroom', { exact: true })
    await expect(wordmark).toBeVisible()
    expect((await css(wordmark, 'font-family')).split(',')[0]).toContain('Fraunces')
    expect(await css(wordmark, 'font-size')).toBe('22px')
    expect(await css(wordmark, 'font-weight')).toBe('600')
  })

  test('nav links (C3)', async ({ page }) => {
    await page.goto('/')
    const links = mainNav(page).getByRole('link')
    await expect(links).toHaveCount(4)
    for (const [i, { name, href }] of NAV_ORDER.entries()) {
      await expect(links.nth(i)).toHaveText(name)
      await expect(links.nth(i)).toHaveAttribute('href', href)
    }
  })

  test('current link (C4)', async ({ page }) => {
    for (const { path, title } of PAGES) {
      await page.goto(path)
      await settle(page)
      for (const { name } of NAV_ORDER) {
        const link = mainNav(page).getByRole('link', { name, exact: true })
        if (name === title) {
          await expect(link).toHaveAttribute('aria-current', 'page')
          expect(await css(link, 'background-color'), `${path} ${name}`).toBe('rgb(233, 229, 220)')
          expect(await css(link, 'font-weight')).toBe('600')
        } else {
          await expect(link).not.toHaveAttribute('aria-current')
          expect(await css(link, 'background-color'), `${path} ${name}`).toBe('rgba(0, 0, 0, 0)')
          expect(await css(link, 'color')).toBe('rgb(69, 79, 92)')
          expect(await css(link, 'font-weight')).toBe('500')
        }
      }
    }
  })

  test('link metrics (C5)', async ({ page }) => {
    await page.goto('/')
    const links = mainNav(page).getByRole('link')
    for (let i = 0; i < 4; i += 1) {
      const link = links.nth(i)
      expect((await link.boundingBox())!.height).toBeGreaterThanOrEqual(44)
      expect(await css(link, 'border-radius')).toBe('10px')
      expect(await css(link, 'font-size')).toBe('15px')
    }
  })

  test('header border (C14)', async ({ page }) => {
    await page.goto('/')
    const header = page.locator('header')
    expect(await css(header, 'border-bottom-width')).toBe('1px')
    expect(await css(header, 'border-bottom-style')).toBe('solid')
    expect(await css(header, 'border-bottom-color')).toBe('rgb(226, 221, 211)')
    expect(await css(page.locator('body'), 'background-color')).toBe('rgb(245, 243, 238)')
  })

  test('keyboard nav (C16)', async ({ page }) => {
    await page.goto('/')
    await page.keyboard.press('Tab')
    for (const { name } of NAV_ORDER) {
      await page.keyboard.press('Tab')
      const link = mainNav(page).getByRole('link', { name, exact: true })
      await expect(link).toBeFocused()
      await settle(page)
      expect(await css(link, 'outline-style')).toBe('solid')
      expect(await css(link, 'outline-width')).toBe('2px')
      expect(await css(link, 'outline-color')).toBe('rgb(29, 78, 137)')
      expect(await css(link, 'outline-offset')).toBe('2px')
    }
  })
})

for (const width of [1440, 1024]) {
  test(`desktop nav at ${width} (C6)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/')
    for (const { name } of NAV_ORDER) {
      await expect(mainNav(page).getByRole('link', { name, exact: true })).toBeVisible()
    }
    await expect(page.getByRole('button', { name: 'Open menu' })).toHaveCount(0)
  })
}

for (const width of [375, 1023]) {
  test(`phone menu button at ${width} (C7)`, async ({ page }) => {
    await page.setViewportSize({ width, height: 812 })
    await page.goto('/')
    const button = page.getByRole('button', { name: 'Open menu' })
    await expect(button).toBeVisible()
    const b = (await button.boundingBox())!
    expect([b.width, b.height]).toEqual([44, 44])
    for (const { name } of NAV_ORDER) {
      await expect(page.getByRole('link', { name, exact: true })).toBeHidden()
    }
  })
}

test.describe('phone', () => {
  test.use({ viewport: PHONE })

  test('menu dialog (C8)', async ({ page }) => {
    await page.goto('/alerts')
    await page.getByRole('button', { name: 'Open menu' }).click()
    const dialog = page.getByRole('dialog', { name: 'Menu' })
    await expect(dialog).toBeVisible()
    const links = dialog.getByRole('link')
    await expect(links).toHaveCount(4)
    for (const [i, { name, href }] of NAV_ORDER.entries()) {
      await expect(links.nth(i)).toHaveText(name)
      await expect(links.nth(i)).toHaveAttribute('href', href)
      if (name === 'Alerts') {
        await expect(links.nth(i)).toHaveAttribute('aria-current', 'page')
      } else {
        await expect(links.nth(i)).not.toHaveAttribute('aria-current')
      }
    }
  })

  test('menu navigates (C9)', async ({ page }) => {
    await page.goto('/alerts')
    await page.getByRole('button', { name: 'Open menu' }).click()
    await page.getByRole('dialog', { name: 'Menu' }).getByRole('link', { name: 'Settings' }).click()
    await expect(page).toHaveURL(/\/settings$/)
    await expect(page.locator('main h1')).toHaveText('Settings')
    await expect(page.getByRole('dialog')).toHaveCount(0)
  })

  test('menu focus (C17)', async ({ page }) => {
    await page.goto('/')
    const button = page.getByRole('button', { name: 'Open menu' })
    await button.click()
    const dialog = page.getByRole('dialog', { name: 'Menu' })
    await expect(dialog).toBeVisible()
    for (let i = 0; i < 10; i += 1) {
      await page.keyboard.press('Tab')
      const inside = await page.evaluate(
        () => !!document.activeElement?.closest('[role="dialog"]'),
      )
      expect(inside, `Tab ${i + 1}`).toBe(true)
    }
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await expect(button).toBeFocused()
  })
})

test('no business yet (C11)', async ({ page }) => {
  for (const viewport of [DESKTOP, PHONE]) {
    await page.setViewportSize(viewport)
    for (const { path } of PAGES) {
      await page.goto(path)
      await expect(page.getByText('Business', { exact: true })).toHaveCount(0)
    }
  }
  await page.goto('/')
  await expect(page.getByTestId('header-phone-identity')).toHaveText('Headroom')
})

test('phone layout (C12)', async ({ page }) => {
  await page.setViewportSize(PHONE)
  for (const { path } of PAGES) {
    await page.goto(path)
    expect(await page.evaluate(() => document.documentElement.scrollWidth), path).toBe(375)
    const shell = page.getByTestId('shell')
    expect(await css(shell, 'padding-left')).toBe('16px')
    expect(await css(shell, 'padding-right')).toBe('16px')
  }
})

test('desktop width (C13)', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 })
  await page.goto('/')
  const shell = page.getByTestId('shell')
  expect(await css(shell, 'padding-left')).toBe('48px')
  expect(await css(shell, 'padding-right')).toBe('48px')
  const width = (await shell.boundingBox())!.width
  expect(width - 96).toBeLessThanOrEqual(1344)
})

test('skip link (C15)', async ({ page }) => {
  for (const { path } of PAGES) {
    await page.goto(path)
    await page.keyboard.press('Tab')
    const skip = page.getByRole('link', { name: 'Skip to main content' })
    await expect(skip).toBeFocused()
    const b = (await skip.boundingBox())!
    expect(b.width, path).toBeGreaterThan(1)
    expect(b.height, path).toBeGreaterThan(1)
    await page.keyboard.press('Enter')
    await expect(page.locator('main')).toBeFocused()
  }
})

for (const [label, viewport] of [['1440', DESKTOP], ['375', PHONE]] as const) {
  test(`axe at ${label} (C18)`, async ({ page }) => {
    await page.setViewportSize(viewport)
    for (const { path, title } of PAGES) {
      await page.goto(path)
      await expect(page.locator('main h1')).toHaveText(title)
      // The Next.js dev tools overlay is not part of the page under test.
      const results = await new AxeBuilder({ page }).exclude('nextjs-portal').analyze()
      expect(results.violations, path).toEqual([])
    }
  })
}

test('axe on the open menu (C18)', async ({ page }) => {
  await page.setViewportSize(PHONE)
  await page.goto('/')
  await page.getByRole('button', { name: 'Open menu' }).click()
  await expect(page.getByRole('dialog', { name: 'Menu' })).toBeVisible()
  await settle(page)
  const results = await new AxeBuilder({ page }).exclude('nextjs-portal').analyze()
  expect(results.violations).toEqual([])
})

test('html lang (C19)', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
})

test('text from messages (C20)', async ({ page }) => {
  for (const viewport of [DESKTOP, PHONE]) {
    await page.setViewportSize(viewport)
    for (const { path } of PAGES) {
      await page.goto(path)
      for (const text of await pageStrings(page)) {
        expect(MESSAGE_VALUES, `${path} at ${viewport.width}: "${text}"`).toContain(text)
      }
    }
  }
  await page.setViewportSize(PHONE)
  await page.goto('/')
  await page.getByRole('button', { name: 'Open menu' }).click()
  await expect(page.getByRole('dialog', { name: 'Menu' })).toBeVisible()
  for (const text of await pageStrings(page)) {
    expect(MESSAGE_VALUES, `menu: "${text}"`).toContain(text)
  }
})

test('title (C21)', async ({ page }) => {
  for (const { path } of PAGES) {
    await page.goto(path)
    await expect(page).toHaveTitle('Headroom')
  }
})

// Run with NEXT_PUBLIC_SENTRY_DSN set to empty (see C42's proof); a DSN would make it fail.
test('no sentry without dsn (C42)', async ({ page }) => {
  const errors: string[] = []
  const sentryRequests: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('request', (request) => {
    if (new URL(request.url()).hostname.includes('sentry')) sentryRequests.push(request.url())
  })
  for (const { path, title } of PAGES) {
    await page.goto(path)
    await expect(page.locator('main h1')).toHaveText(title)
  }
  expect(errors).toEqual([])
  expect(sentryRequests).toEqual([])
})
