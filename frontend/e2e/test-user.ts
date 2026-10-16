/** Where the setup project saves the signed-in test user's browser state (spec 10). */
export const SIGNED_IN_STATE = 'playwright/.clerk/user.json'

/** A browser state with no session, for tests that start signed out. */
export const SIGNED_OUT = { cookies: [], origins: [] }

type ClerkUser = {
  first_name: string | null
  last_name: string | null
  primary_email_address_id: string | null
  email_addresses: { id: string; email_address: string }[]
}

/**
 * The Clerk test user named by E2E_CLERK_USER_USERNAME, read from the Clerk Backend API with
 * CLERK_SECRET_KEY (both from .env.local).
 */
export async function testUser(): Promise<{ email: string; fullName: string }> {
  const username = process.env.E2E_CLERK_USER_USERNAME
  const secret = process.env.CLERK_SECRET_KEY
  if (!username || !secret) {
    throw new Error('Set E2E_CLERK_USER_USERNAME and CLERK_SECRET_KEY in .env.local')
  }
  const response = await fetch(
    `https://api.clerk.com/v1/users?username=${encodeURIComponent(username)}`,
    { headers: { Authorization: `Bearer ${secret}` } },
  )
  const users = (await response.json()) as ClerkUser[]
  if (users.length !== 1) throw new Error(`Expected one Clerk user named ${username}`)
  const [user] = users
  const email = user.email_addresses.find((e) => e.id === user.primary_email_address_id)
  if (!email) throw new Error(`Clerk user ${username} has no primary email`)
  return {
    email: email.email_address,
    fullName: [user.first_name, user.last_name].filter(Boolean).join(' '),
  }
}

const CLERK_API = 'https://api.clerk.com/v1'
const ONBOARDING_PREFIX = 'e2e-onboarding-'

function clerkSecret(): string {
  const secret = process.env.CLERK_SECRET_KEY
  if (!secret) throw new Error('Set CLERK_SECRET_KEY in .env.local')
  return secret
}

async function clerkApi(path: string, init: RequestInit = {}): Promise<unknown> {
  const response = await fetch(`${CLERK_API}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${clerkSecret()}`,
      'Content-Type': 'application/json',
      ...init.headers,
    },
  })
  if (!response.ok) throw new Error(`Clerk ${init.method ?? 'GET'} ${path}: ${response.status}`)
  return response.json()
}

/**
 * A Clerk user created for one test on the development instance, so it has no business
 * (spec 11). Delete it with `deleteUser` when the test ends; `deleteStaleOnboardingUsers`
 * removes any a crashed run left behind.
 */
export async function createOnboardingUser(): Promise<{ id: string; email: string }> {
  const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const email = `${ONBOARDING_PREFIX}${suffix}+clerk_test@example.com`
  const user = (await clerkApi('/users', {
    method: 'POST',
    body: JSON.stringify({
      username: `${ONBOARDING_PREFIX}${suffix}`,
      email_address: [email],
      skip_password_requirement: true,
      skip_legal_checks: true,
    }),
  })) as { id: string }
  return { id: user.id, email }
}

export async function deleteUser(id: string): Promise<void> {
  await clerkApi(`/users/${id}`, { method: 'DELETE' })
}

/** Deletes onboarding users older than an hour, left behind by a run that crashed. */
export async function deleteStaleOnboardingUsers(): Promise<void> {
  const users = (await clerkApi(
    `/users?query=${encodeURIComponent(ONBOARDING_PREFIX)}&limit=100`,
  )) as { id: string; username: string | null; created_at: number }[]
  const hourAgo = Date.now() - 60 * 60 * 1000
  for (const user of users) {
    if (user.username?.startsWith(ONBOARDING_PREFIX) && user.created_at < hourAgo) {
      await deleteUser(user.id)
    }
  }
}
