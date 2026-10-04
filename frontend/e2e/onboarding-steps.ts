import { expect, type Page } from '@playwright/test'

/** Fills onboarding step 2 with the mouse and presses Continue (spec 11). */
export async function completeBusinessStep(page: Page, name: string) {
  await page.getByLabel('Business name').fill(name)
  await page.getByRole('combobox', { name: 'Province or territory' }).click()
  await page.getByRole('option', { name: 'Ontario' }).click()
  await page.getByRole('combobox', { name: 'Time zone' }).click()
  await page.getByRole('option', { name: 'Eastern Time (Toronto)' }).click()
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page.getByTestId('shell')).toBeVisible()
}
