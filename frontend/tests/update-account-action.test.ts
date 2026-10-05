import { beforeEach, describe, expect, test, vi } from 'vitest'
import { updateAccount } from '@/app/onboarding/accounts/actions'
import { api } from '@/lib/api/client'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { PATCH: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
const revalidatePath = vi.hoisted(() => vi.fn())
vi.mock('next/cache', () => ({ revalidatePath }))

type PatchResult = Awaited<ReturnType<typeof api.PATCH>>

const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const ACCOUNT = '0b7e4a2c-0000-4000-8000-000000000002'

function answers(status: number) {
  vi.mocked(api.PATCH).mockResolvedValue({
    data: status === 200 ? { id: ACCOUNT } : undefined,
    error: status === 200 ? undefined : { status },
    response: new Response(null, { status }),
  } as unknown as PatchResult)
}

beforeEach(() => {
  vi.mocked(api.PATCH).mockReset()
  revalidatePath.mockClear()
})

describe('update account action', () => {
  const bodies = [
    { included: false },
    { included: true },
    { primary: true as const },
    { included: true, primary: true as const },
  ]

  test.each(bodies)('200 sends %o for the business and account, and revalidates', async (body) => {
    answers(200)

    const result = await updateAccount(BUSINESS, ACCOUNT, body)

    expect(result).toEqual({ error: null })
    expect(api.PATCH).toHaveBeenCalledWith('/v1/businesses/{business_id}/bank/accounts/{account_id}', {
      params: { path: { business_id: BUSINESS, account_id: ACCOUNT } },
      body,
      headers: { Authorization: 'Bearer tok_test' },
    })
    expect(revalidatePath).toHaveBeenCalledWith('/onboarding/accounts')
  })

  test.each([409, 404, 500])('%i returns the error result and does not revalidate', async (status) => {
    answers(status)

    const result = await updateAccount(BUSINESS, ACCOUNT, { included: true })

    expect(result).toEqual({ error: 'saveFailed' })
    expect(revalidatePath).not.toHaveBeenCalled()
  })

  test('a rejected call returns the error result and does not revalidate', async () => {
    vi.mocked(api.PATCH).mockRejectedValue(new TypeError('fetch failed'))

    const result = await updateAccount(BUSINESS, ACCOUNT, { included: true })

    expect(result).toEqual({ error: 'saveFailed' })
    expect(revalidatePath).not.toHaveBeenCalled()
  })
})
