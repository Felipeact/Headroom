import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { tabTo } from './onboarding-steps'

const STEP = '/onboarding/bank'
const YODLEE_NAME = 'Connect another way'

// Spec 17b C44. The test user has a business (global setup) and no bank, and the page does not
// require one. The API runs with the Yodlee sandbox settings, so the second action shows.
test('C44 yodlee action: layout, keyboard and axe', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto(STEP)
  const yodlee = page.getByRole('button', { name: YODLEE_NAME })
  await expect(yodlee).toBeEnabled()

  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
  for (const button of [yodlee, page.getByRole('button', { name: 'Connect your bank' })]) {
    const box = await button.boundingBox()
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44)
  }
  const axe = await new AxeBuilder({ page }).analyze()
  expect(axe.violations).toEqual([])

  // Keyboard alone: reach the action and open FastLink with Enter.
  await tabTo(page, yodlee)
  await page.keyboard.press('Enter')
  await expect(page.locator('#container-fastlink')).toBeVisible({ timeout: 30_000 })
})
