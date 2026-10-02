import { clerk, clerkSetup } from '@clerk/testing/playwright'
import { test as setup } from '@playwright/test'
import { SIGNED_IN_STATE, testUser } from './test-user'

setup.describe.configure({ mode: 'serial' })

setup('clerk testing token', async () => {
  await clerkSetup()
})

setup('sign in the test user', async ({ page }) => {
  // Sign-in token (ticket) path: a password sign-in from a new browser stops at Clerk's
  // client-trust email check.
  await page.goto('/sign-in')
  await clerk.signIn({ page, emailAddress: (await testUser()).email })
  await page.goto('/')
  await page.getByTestId('shell').waitFor()
  await page.context().storageState({ path: SIGNED_IN_STATE })
})
