// @vitest-environment node
import { afterEach, expect, test, vi } from 'vitest'
import { auth } from '@clerk/nextjs/server'
import { authHeaders } from '@/lib/api/auth'

vi.mock('server-only', () => ({}))
vi.mock('@clerk/nextjs/server', () => ({ auth: vi.fn() }))

type AuthResult = Awaited<ReturnType<typeof auth>>

function signedInWith(token: string | null, fresh: string | null = null) {
  const getToken = vi.fn((options?: { expiresInSeconds?: number }) =>
    Promise.resolve(options?.expiresInSeconds ? fresh : token),
  )
  vi.mocked(auth).mockResolvedValue({ getToken } as unknown as AuthResult)
  return getToken
}

// A JWT-shaped token whose payload expires `seconds` from now; the signature is irrelevant here.
function tokenExpiringIn(seconds: number): string {
  const payload = { exp: Math.floor(Date.now() / 1000) + seconds }
  return `h.${Buffer.from(JSON.stringify(payload)).toString('base64url')}.s`
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

test('authHeaders keeps a token with time left', async () => {
  const token = tokenExpiringIn(50)
  const getToken = signedInWith(token, 'tok_fresh')

  expect(await authHeaders()).toEqual({ Authorization: `Bearer ${token}` })
  expect(getToken).toHaveBeenCalledTimes(1)
})

test('authHeaders mints a fresh token when the current one is about to expire', async () => {
  const getToken = signedInWith(tokenExpiringIn(5), 'tok_fresh')

  expect(await authHeaders()).toEqual({ Authorization: 'Bearer tok_fresh' })
  expect(getToken).toHaveBeenLastCalledWith({ expiresInSeconds: 60 })
})
