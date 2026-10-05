import { expect, type Locator, type Page } from '@playwright/test'

/** Fills onboarding step 2 with the mouse and presses Continue; it lands on step 3 (spec 12). */
export async function completeBusinessStep(page: Page, name: string) {
  await page.getByLabel('Business name').fill(name)
  await page.getByRole('combobox', { name: 'Province or territory' }).click()
  await page.getByRole('option', { name: 'Ontario' }).click()
  await page.getByRole('combobox', { name: 'Time zone' }).click()
  await page.getByRole('option', { name: 'Eastern Time (Toronto)' }).click()
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page.getByRole('heading', { name: 'Connect your bank' })).toBeVisible()
}

export const plaidLink = (page: Page) => page.frameLocator('iframe[id^="plaid-link-iframe"]')

/** Presses Tab until `target` has focus; fails after `limit` presses. */
export async function tabTo(page: Page, target: Locator, limit = 40) {
  for (let i = 0; i < limit; i++) {
    await page.keyboard.press('Tab')
    if (await target.evaluate((el) => el === document.activeElement)) return
  }
  throw new Error(`Tab never reached ${target}`)
}

/**
 * Goes through the Plaid Link sandbox for `bank` with Plaid's test credentials. Link asks for a
 * phone number only the first time in a page, so that screen is optional.
 */
export async function connectSandboxBank(page: Page, bank = 'TD Canada Trust') {
  const link = plaidLink(page)
  const phone = link.getByRole('button', { name: 'Continue without phone number' })
  try {
    await phone.click({ timeout: 15_000 })
  } catch {
    // No phone screen this time.
  }
  await link.locator('input').first().fill(bank)
  await link.getByText(bank, { exact: true }).first().click()
  await link.getByRole('button', { name: bank, exact: true }).click()
  await link.locator('input[type="text"]').fill('user_good')
  await link.locator('input[type="password"]').fill('pass_good')
  await link.getByRole('button', { name: 'Submit' }).click()
  await link.getByRole('button', { name: 'Continue', exact: true }).click()
  await link.getByRole('button', { name: 'Finish without saving' }).click()
}
