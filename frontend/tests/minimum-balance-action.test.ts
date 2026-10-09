import { beforeEach, describe, expect, test, vi } from 'vitest'
import { saveMinimumBalance } from '@/app/onboarding/minimum-balance/actions'
import { api } from '@/lib/api/client'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { PUT: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))

const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'

function answers(status: number) {
  vi.mocked(api.PUT).mockResolvedValue({
    data: status < 300 ? {} : undefined,
    error: status < 300 ? undefined : { status },
    response: new Response(null, { status }),
  } as never)
}

beforeEach(() => {
  vi.mocked(api.PUT).mockReset()
})

describe('saveMinimumBalance', () => {
  test('C25 puts cents', async () => {
    answers(200)
    expect(await saveMinimumBalance(BUSINESS, 750000)).toEqual({ error: null })
    expect(api.PUT).toHaveBeenCalledWith('/v1/businesses/{business_id}/minimum-balance', {
      params: { path: { business_id: BUSINESS } },
      body: { amount_cents: 750000 },
      headers: { Authorization: 'Bearer tok_test' },
    })
  })

  test('C26 save failed', async () => {
    answers(500)
    expect(await saveMinimumBalance(BUSINESS, 750000)).toEqual({ error: 'saveFailed' })
    vi.mocked(api.PUT).mockRejectedValue(new TypeError('fetch failed'))
    expect(await saveMinimumBalance(BUSINESS, 750000)).toEqual({ error: 'saveFailed' })
  })
})
