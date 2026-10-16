import AxeBuilder from '@axe-core/playwright'
import { clerk } from '@clerk/testing/playwright'
import { expect, test, type Locator, type Page } from '@playwright/test'
import { SIGNED_OUT, testUser } from './test-user'

const DESKTOP = { width: 1440, height: 900 }
const PHONE = { width: 375, height: 812 }
const PROTECTED = ['/', '/alerts', '/expected-payments', '/settings', '/dev/components']

function pathOf(page: Page): string {
  return new URL(page.url()).pathname
}

// Waits out open/close animations so sizes and colours are read in their settled state.
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

async function signInFresh(page: Page) {
  await page.goto('/sign-in')
  await clerk.signIn({ page, emailAddress: (await testUser()).email })
  await page.goto('/')
  await page.getByTestId('shell').waitFor()
}

// Presses Tab until `target` has focus; fails after `limit` presses.
async function tabTo(page: Page, target: Locator, limit = 40) {
  for (let i = 0; i < limit; i++) {
    await page.keyboard.press('Tab')
    if (await target.evaluate((el) => el === document.activeElement)) return
  }
  throw new Error(`Tab never reached ${target}`)
}

const identifierInput = (page: Page) => page.locator('input[name="identifier"]')
const continueButton = (page: Page) => page.getByRole('button', { name: 'Continue', exact: true })
const signUpInput = (page: Page) =>
  page.locator('input[name="emailAddress"], input[name="username"]').first()

test.describe('signed out', () => {
  test.use({ storageState: SIGNED_OUT })

  test('C16 signed out redirects', async ({ page }) => {
    for (const path of PROTECTED) {
      await page.goto(path)
      await expect.poll(() => pathOf(page), { message: path }).toBe('/sign-in')
    }
  })

  test('C17 auth pages without shell', async ({ page }) => {
    for (const [path, input] of [
      ['/sign-in', identifierInput],
      ['/sign-up', signUpInput],
    ] as const) {
      const response = await page.goto(path)
      expect(response?.status(), path).toBe(200)
      await expect(input(page), path).toBeVisible()
      await expect(continueButton(page), path).toBeVisible()
      await expect(page.getByTestId('shell'), path).toHaveCount(0)
    }
  })

  test('C25 themed with tokens', async ({ page }) => {
    await page.goto('/sign-in')
    await expect(continueButton(page)).toBeVisible()
    await settle(page)

    const accent = await page.evaluate(() => {
      const probe = document.createElement('div')
      probe.style.backgroundColor = 'var(--accent)'
      document.body.append(probe)
      const value = getComputedStyle(probe).backgroundColor
      probe.remove()
      return value
    })
    const buttonBackground = await continueButton(page).evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    )
    expect(buttonBackground).toBe(accent)

    const plexFamily = await page.evaluate(() =>
      getComputedStyle(document.documentElement)
        .getPropertyValue('--font-plex-sans')
        .split(',')[0]
        .trim(),
    )
    expect(plexFamily).toMatch(/IBM Plex Sans/)
    const formFont = await identifierInput(page).evaluate((el) => getComputedStyle(el).fontFamily)
    expect(formFont.split(',')[0].trim()).toBe(plexFamily)
  })

  test('C26 auth pages 375 keyboard axe', async ({ page }) => {
    await page.setViewportSize(PHONE)
    for (const [path, input] of [
      ['/sign-in', identifierInput],
      ['/sign-up', signUpInput],
    ] as const) {
      await page.goto(path)
      await expect(input(page), path).toBeVisible()
      await settle(page)

      const width = await page.evaluate(() => document.documentElement.scrollWidth)
      expect(width, path).toBeLessThanOrEqual(375)

      await tabTo(page, input(page))
      await tabTo(page, continueButton(page))
      // Leaving a field fades in Clerk's field error; check contrast once it has settled.
      await settle(page)

      const axe = await new AxeBuilder({ page }).analyze()
      expect(axe.violations, path).toEqual([])
    }
  })
})

test('C18 shows the name', async ({ page }) => {
  await page.setViewportSize(DESKTOP)
  await page.goto('/')

  await expect(page.getByTestId('shell')).toBeVisible()
  await expect(page.getByTestId('header-user')).toContainText((await testUser()).fullName)
})

test.describe('sign out', () => {
  // A fresh session per test: signing out revokes it, and the shared one must survive.
  test.use({ storageState: SIGNED_OUT })

  test('C23 sign out desktop', async ({ page }) => {
    await page.setViewportSize(DESKTOP)
    await signInFresh(page)

    await page.getByTestId('header-user').getByRole('button', { name: 'Sign out' }).click()
    await expect.poll(() => pathOf(page)).toBe('/sign-in')

    await page.goto('/')
    await expect.poll(() => pathOf(page)).toBe('/sign-in')
  })

  test('C24 sign out phone', async ({ page }) => {
    await page.setViewportSize(PHONE)
    await signInFresh(page)

    await page.getByRole('button', { name: 'Open menu' }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog.getByTestId('menu-user')).toContainText((await testUser()).fullName)
    await dialog.getByRole('button', { name: 'Sign out' }).click()

    await expect.poll(() => pathOf(page)).toBe('/sign-in')
  })
})

test('C27 sign out reachable', async ({ page }) => {
  await page.setViewportSize(DESKTOP)
  await page.goto('/')
  const desktopSignOut = page.getByTestId('header-user').getByRole('button', { name: 'Sign out' })
  await expect(desktopSignOut).toBeVisible()
  await settle(page)

  const desktopBox = await desktopSignOut.boundingBox()
  expect(desktopBox?.width).toBeGreaterThanOrEqual(44)
  expect(desktopBox?.height).toBeGreaterThanOrEqual(44)
  await tabTo(page, desktopSignOut)
  const axe = await new AxeBuilder({ page }).analyze()
  expect(axe.violations).toEqual([])

  await page.setViewportSize(PHONE)
  await page.goto('/')
  const menuButton = page.getByRole('button', { name: 'Open menu' })
  await tabTo(page, menuButton)
  await page.keyboard.press('Enter')
  const phoneSignOut = page.getByRole('dialog').getByRole('button', { name: 'Sign out' })
  await expect(phoneSignOut).toBeVisible()
  await settle(page)

  const phoneBox = await phoneSignOut.boundingBox()
  expect(phoneBox?.width).toBeGreaterThanOrEqual(44)
  expect(phoneBox?.height).toBeGreaterThanOrEqual(44)
  await tabTo(page, phoneSignOut)
  const phoneAxe = await new AxeBuilder({ page }).analyze()
  expect(phoneAxe.violations).toEqual([])
})
