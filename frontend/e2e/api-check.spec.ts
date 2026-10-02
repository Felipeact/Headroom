import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

// Needs the API on port 8100; playwright.config.ts starts it.
const URL = '/dev/api-check'

test('live status', async ({ page }) => {
  const response = await page.goto(URL)

  expect(response?.status()).toBe(200)
  await expect(page.getByRole('heading', { level: 1, name: 'API check' })).toBeVisible()
  await expect(page.getByText('status: ok', { exact: true })).toBeVisible()
})

test('live status over http', async ({ page }) => {
  await page.goto(URL)

  await expect(page.getByText('status: ok', { exact: true })).toBeVisible()
  await expect(page.getByText('HTTP 200', { exact: true })).toBeVisible()
})

test('a11y and 375', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto(URL)
  await expect(page.getByText('status: ok', { exact: true })).toBeVisible()

  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations).toEqual([])

  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
  expect(scrollWidth).toBeLessThanOrEqual(375)

  // The page has no controls, so Tab must not leave focus stuck on any element.
  const focused: string[] = []
  for (let i = 0; i < 5; i++) {
    await page.keyboard.press('Tab')
    focused.push(await page.evaluate(() => document.activeElement?.outerHTML.slice(0, 80) ?? 'none'))
  }
  const nothingFocusable = focused.every((html) => html.startsWith('<body'))
  expect(nothingFocusable || new Set(focused).size > 1).toBe(true)
})
