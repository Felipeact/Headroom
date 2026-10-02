// @vitest-environment node
import { beforeEach, expect, test, vi } from 'vitest'
import { currentUser } from '@clerk/nextjs/server'
import { getUserName } from '@/lib/user-name'

vi.mock('server-only', () => ({}))
vi.mock('@clerk/nextjs/server', () => ({ currentUser: vi.fn() }))

type ClerkUser = Awaited<ReturnType<typeof currentUser>>

function user(fields: {
  fullName: string | null
  email: string | null
  username?: string | null
}): ClerkUser {
  return {
    fullName: fields.fullName,
    primaryEmailAddress: fields.email ? { emailAddress: fields.email } : null,
    username: fields.username ?? null,
  } as unknown as ClerkUser
}

beforeEach(() => {
  vi.mocked(currentUser).mockReset()
})

test('display name is the full name', async () => {
  vi.mocked(currentUser).mockResolvedValue(
    user({ fullName: 'Ada Lovelace', email: 'ada@example.test' }),
  )
  expect(await getUserName()).toBe('Ada Lovelace')
})

test('display name falls back to the primary email', async () => {
  vi.mocked(currentUser).mockResolvedValue(user({ fullName: null, email: 'ada@example.test' }))
  expect(await getUserName()).toBe('ada@example.test')
})
