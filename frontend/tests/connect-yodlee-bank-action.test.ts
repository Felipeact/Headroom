import { beforeEach, describe, expect, test, vi } from 'vitest'
import { connectYodleeBank, launchFastLink } from '@/app/onboarding/bank/actions'
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
const CONNECTION = '9a1c2b0e-0000-4000-8000-000000000002'

function answers(status: number, data?: unknown) {
  vi.mocked(api.POST).mockResolvedValue({
    data: status < 300 ? (data ?? { id: 'c1' }) : undefined,
    error: status < 300 ? undefined : { status },
    response: new Response(null, { status }),
  } as unknown as PostResult)
}

beforeEach(() => {
  vi.mocked(api.POST).mockReset()
  redirect.mockClear()
})

describe('connect yodlee bank action (spec 17b)', () => {
  test('sends the yodlee provider and the provider account, then redirects', async () => {
    answers(201)

    await expect(connectYodleeBank(BUSINESS, '4242')).rejects.toThrow('NEXT_REDIRECT')

    expect(api.POST).toHaveBeenCalledWith('/v1/businesses/{business_id}/bank/connections', {
      params: { path: { business_id: BUSINESS } },
      body: { provider: 'yodlee', provider_account_id: '4242' },
      headers: { Authorization: 'Bearer tok_test' },
    })
    expect(redirect).toHaveBeenCalledWith('/onboarding/accounts')
  })

  test('409 is already connected, anything else is a failure', async () => {
    answers(409)
    await expect(connectYodleeBank(BUSINESS, '4242')).resolves.toEqual({ error: 'alreadyConnected' })

    answers(503)
    await expect(connectYodleeBank(BUSINESS, '4242')).resolves.toEqual({ error: 'connectFailed' })
    expect(redirect).not.toHaveBeenCalled()
  })
})

describe('launch fastlink action (spec 17b)', () => {
  test('sends the business, and the connection only when reconnecting', async () => {
    answers(200, { fastlink_url: 'https://f.test', access_token: 't', config_name: 'c', expires_in: 1, provider_account_id: null })

    await launchFastLink(BUSINESS)
    await launchFastLink(BUSINESS, CONNECTION)

    expect(vi.mocked(api.POST).mock.calls.map((call) => (call[1] as { body: unknown }).body)).toEqual([
      {},
      { connection_id: CONNECTION },
    ])
  })

  test('a failed call is launchFailed', async () => {
    answers(503)

    await expect(launchFastLink(BUSINESS)).resolves.toEqual({ error: 'launchFailed' })
  })
})
