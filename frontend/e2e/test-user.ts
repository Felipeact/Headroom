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
