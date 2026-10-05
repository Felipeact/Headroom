import { clerk, clerkSetup } from '@clerk/testing/playwright'
import { test as setup } from '@playwright/test'
import { completeBusinessStep } from './onboarding-steps'
import { deleteStaleOnboardingUsers, SIGNED_IN_STATE, testUser } from './test-user'

setup.describe.configure({ mode: 'serial' })

setup('clerk testing token', async () => {
  await clerkSetup()
  await deleteStaleOnboardingUsers()
})

setup('sign in the test user', async ({ page }) => {
  // Sign-in token (ticket) path: a password sign-in from a new browser stops at Clerk's
  // client-trust email check.
  await page.goto('/sign-in')
  await clerk.signIn({ page, emailAddress: (await testUser()).email })
  await page.goto('/')
  // Since spec 11 the shell needs a business; give the test user one on its first run.
  await page.waitForURL(/\/(onboarding\/business)?$/)
  if (page.url().endsWith('/onboarding/business')) {
    await completeBusinessStep(page, 'Harbor Street Plumbing')
    // Step 3 (spec 12) does not force a bank, so the dashboard is reachable without one.
    await page.goto('/')
  }
  await page.getByTestId('shell').waitFor()
  await page.context().storageState({ path: SIGNED_IN_STATE })
})
