import { beforeEach, describe, expect, test, vi } from 'vitest'
import { connectBank } from '@/app/onboarding/bank/actions'
import { api } from '@/lib/api/client'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { POST: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
const redirect = vi.hoisted(() =>
  vi.fn((url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`)
  }),
)
vi.mock('next/navigation', () => ({ redirect }))

type PostResult = Awaited<ReturnType<typeof api.POST>>

const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const PUBLIC_TOKEN = 'public-sandbox-1'

function answers(status: number) {
  vi.mocked(api.POST).mockResolvedValue({
    data: status === 201 ? { id: 'c1' } : undefined,
    error: status === 201 ? undefined : { status },
    response: new Response(null, { status }),
  } as unknown as PostResult)
}

beforeEach(() => {
  vi.mocked(api.POST).mockReset()
  redirect.mockClear()
})

describe('connect bank action', () => {
  test('201 redirects to choosing accounts, with the business, the body and the token', async () => {
    answers(201)

    await expect(connectBank(BUSINESS, PUBLIC_TOKEN)).rejects.toThrow('NEXT_REDIRECT')

    expect(redirect).toHaveBeenCalledWith('/onboarding/accounts')
    expect(api.POST).toHaveBeenCalledWith('/v1/businesses/{business_id}/bank/connections', {
      params: { path: { business_id: BUSINESS } },
      body: { provider: 'plaid', public_token: PUBLIC_TOKEN },
      headers: { Authorization: 'Bearer tok_test' },
    })
  })

  test('201 from bank settings redirects back to bank settings (spec 17)', async () => {
    answers(201)

    await expect(connectBank(BUSINESS, PUBLIC_TOKEN, '/settings/banks')).rejects.toThrow('NEXT_REDIRECT')

    expect(redirect).toHaveBeenCalledWith('/settings/banks')
  })

  test('201 with a destination outside the list redirects to choosing accounts', async () => {
    answers(201)

    await expect(
      connectBank(BUSINESS, PUBLIC_TOKEN, 'https://evil.example' as '/settings/banks'),
    ).rejects.toThrow('NEXT_REDIRECT')

    expect(redirect).toHaveBeenCalledWith('/onboarding/accounts')
  })

  test('409 returns the duplicate result and does not redirect', async () => {
    answers(409)

    await expect(connectBank(BUSINESS, PUBLIC_TOKEN)).resolves.toEqual({
      error: 'alreadyConnected',
    })
    expect(redirect).not.toHaveBeenCalled()
  })

  test.each([400, 502, 500])('%i returns the generic error and does not redirect', async (status) => {
    answers(status)

    await expect(connectBank(BUSINESS, PUBLIC_TOKEN)).resolves.toEqual({ error: 'connectFailed' })
    expect(redirect).not.toHaveBeenCalled()
  })

  test('a rejected call returns the generic error and does not redirect', async () => {
    vi.mocked(api.POST).mockRejectedValue(new TypeError('fetch failed'))

    await expect(connectBank(BUSINESS, PUBLIC_TOKEN)).resolves.toEqual({ error: 'connectFailed' })
    expect(redirect).not.toHaveBeenCalled()
  })
})
