// @vitest-environment node
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { dismissAlert } from '@/app/(app)/actions'
import { createExpectedPayment, deleteExpectedPayment, updateExpectedPayment } from '@/app/(app)/expected-payments/actions'
import { connectBank } from '@/app/onboarding/bank/actions'
import { createBusiness } from '@/app/onboarding/business/actions'
import { saveMinimumBalance } from '@/app/onboarding/minimum-balance/actions'
import { capture } from '@/lib/analytics'
import { api } from '@/lib/api/client'

// Spec 32 C7-C11, C14: each step sends its event only when the API said yes.
vi.mock('server-only', () => ({}))
vi.mock('@/lib/analytics', () => ({ capture: vi.fn() }))
vi.mock('@/lib/api/client', () => ({ api: { POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({ authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }) }))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }))
vi.mock('@clerk/nextjs/server', () => ({ auth: vi.fn().mockResolvedValue({ userId: 'user_1' }) }))
vi.mock('posthog-node', () => ({
  PostHog: vi.fn(function () {
    return { captureImmediate: vi.fn().mockRejectedValue(new Error('PostHog is down')) }
  }),
}))
const redirect = vi.hoisted(() =>
  vi.fn((url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`)
  }),
)
vi.mock('next/navigation', () => ({ redirect }))

const BODY = { description: 'Rent', amount_cents: -250000, date: '2026-11-01', repeats: 'monthly' } as never
const capturing = vi.mocked(capture)

function answer(method: 'POST' | 'PUT' | 'DELETE', status: number, data?: unknown) {
  vi.mocked(api[method]).mockResolvedValue({
    data,
    error: undefined,
    response: new Response(null, { status }),
  } as never)
}

beforeEach(() => {
  capturing.mockReset().mockResolvedValue(undefined)
  redirect.mockClear()
  for (const method of ['POST', 'PUT', 'DELETE'] as const) vi.mocked(api[method]).mockReset()
})

describe('create business', () => {
  test('201 sends business_created with the new id before the redirect', async () => {
    answer('POST', 201, { id: 'b1' })
    await expect(createBusiness({ name: 'Harbor', province: 'ON', time_zone: 'America/Toronto' })).rejects.toThrow(
      'NEXT_REDIRECT /onboarding/bank',
    )
    expect(capturing).toHaveBeenCalledExactlyOnceWith('business_created', { business_id: 'b1' })
  })

  test.each([409, 422, 500])('%i sends nothing', async (status) => {
    answer('POST', status)
    await createBusiness({ name: 'Harbor', province: 'ON', time_zone: 'America/Toronto' }).catch(() => {})
    expect(capturing).not.toHaveBeenCalled()
  })
})

describe('connect bank', () => {
  test.each(['/onboarding/accounts', '/settings/banks'] as const)('201 sends bank_connected, returning to %s', async (to) => {
    answer('POST', 201)
    await expect(connectBank('b1', 'public-token', to)).rejects.toThrow(`NEXT_REDIRECT ${to}`)
    expect(capturing).toHaveBeenCalledExactlyOnceWith('bank_connected', { business_id: 'b1' })
  })

  test.each([409, 500])('%i sends nothing', async (status) => {
    answer('POST', status)
    await connectBank('b1', 'public-token')
    expect(capturing).not.toHaveBeenCalled()
  })
})

describe('save minimum balance', () => {
  test('200 sends minimum_balance_set', async () => {
    answer('PUT', 200)
    expect(await saveMinimumBalance('b1', 500000)).toEqual({ error: null })
    expect(capturing).toHaveBeenCalledExactlyOnceWith('minimum_balance_set', { business_id: 'b1' })
  })

  test.each([422, 500])('%i sends nothing', async (status) => {
    answer('PUT', status)
    expect(await saveMinimumBalance('b1', 500000)).toEqual({ error: 'saveFailed' })
    expect(capturing).not.toHaveBeenCalled()
  })
})

describe('dismiss alert', () => {
  test('200 sends alert_dismissed with both ids', async () => {
    answer('POST', 200)
    expect(await dismissAlert('b1', 'a1')).toEqual({ error: null })
    expect(capturing).toHaveBeenCalledExactlyOnceWith('alert_dismissed', { business_id: 'b1', alert_id: 'a1' })
  })

  test.each([409, 500])('%i sends nothing', async (status) => {
    answer('POST', status)
    expect(await dismissAlert('b1', 'a1')).toEqual({ error: 'dismissFailed' })
    expect(capturing).not.toHaveBeenCalled()
  })
})

describe('expected payment', () => {
  test('201 sends expected_payment_added', async () => {
    answer('POST', 201)
    expect(await createExpectedPayment('b1', BODY)).toEqual({ ok: true })
    expect(capturing).toHaveBeenCalledExactlyOnceWith('expected_payment_added', { business_id: 'b1' })
  })

  test.each([409, 500])('create with %i sends nothing', async (status) => {
    answer('POST', status)
    expect(await createExpectedPayment('b1', BODY)).toMatchObject({ ok: false })
    expect(capturing).not.toHaveBeenCalled()
  })

  test('update and delete send nothing', async () => {
    answer('PUT', 200)
    answer('DELETE', 204)
    expect(await updateExpectedPayment('b1', 'p1', BODY)).toEqual({ ok: true })
    expect(await deleteExpectedPayment('b1', 'p1')).toEqual({ ok: true })
    expect(capturing).not.toHaveBeenCalled()
  })
})

describe('a failing capture does not change the result', () => {
  test('create expected payment still returns ok when PostHog rejects', async () => {
    vi.stubEnv('POSTHOG_KEY', 'phc_test')
    const actual = await vi.importActual<typeof import('@/lib/analytics')>('@/lib/analytics')
    capturing.mockImplementation(actual.capture as typeof capture)
    answer('POST', 201)

    expect(await createExpectedPayment('b1', BODY)).toEqual({ ok: true })
    vi.unstubAllEnvs()
  })
})
