// @vitest-environment node
import { afterEach, expect, test, vi } from 'vitest'
import { auth } from '@clerk/nextjs/server'
import { authHeaders } from '@/lib/api/auth'

vi.mock('server-only', () => ({}))
vi.mock('@clerk/nextjs/server', () => ({ auth: vi.fn() }))

type AuthResult = Awaited<ReturnType<typeof auth>>

function signedInWith(token: string | null) {
  vi.mocked(auth).mockResolvedValue({
    getToken: vi.fn().mockResolvedValue(token),
  } as unknown as AuthResult)
}

const consoleMethods = ['log', 'info', 'warn', 'error', 'debug'] as const

function spyOnConsole() {
  return consoleMethods.map((method) => vi.spyOn(console, method).mockImplementation(() => {}))
}

afterEach(() => {
  vi.restoreAllMocks()
})

test('authHeaders sends the session token as a bearer token', async () => {
  const spies = spyOnConsole()
  signedInWith('tok_abc')

  expect(await authHeaders()).toEqual({ Authorization: 'Bearer tok_abc' })
  for (const spy of spies) expect(spy).not.toHaveBeenCalled()
})

test('authHeaders rejects without a session token', async () => {
  const spies = spyOnConsole()
  signedInWith(null)

  await expect(authHeaders()).rejects.toThrow()
  for (const spy of spies) expect(spy).not.toHaveBeenCalled()
})
