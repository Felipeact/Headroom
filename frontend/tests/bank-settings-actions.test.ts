import { beforeEach, describe, expect, test, vi } from 'vitest'
import { disconnectBank, repairConnection, updateBankAccount } from '@/app/(app)/settings/banks/actions'
import { api } from '@/lib/api/client'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { PATCH: vi.fn(), POST: vi.fn(), DELETE: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
const revalidatePath = vi.hoisted(() => vi.fn())
vi.mock('next/cache', () => ({ revalidatePath }))

const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const CONNECTION = '0b7e4a2c-0000-4000-8000-00000000c001'
const ACCOUNT = '0b7e4a2c-0000-4000-8000-000000000002'
const PAGE = '/settings/banks'
const HEADERS = { Authorization: 'Bearer tok_test' }
const PATH = { business_id: BUSINESS, connection_id: CONNECTION }

function answers(method: 'PATCH' | 'POST' | 'DELETE', status: number) {
  vi.mocked(api[method]).mockResolvedValue({
    data: status < 300 ? {} : undefined,
    error: status < 300 ? undefined : { status },
    response: new Response(null, { status }),
  } as never)
}

beforeEach(() => {
  vi.mocked(api.PATCH).mockReset()
  vi.mocked(api.POST).mockReset()
  vi.mocked(api.DELETE).mockReset()
  revalidatePath.mockClear()
})

describe('bank settings actions', () => {
  test('update action sends the change and revalidates the settings page', async () => {
    answers('PATCH', 200)

    expect(await updateBankAccount(BUSINESS, ACCOUNT, { included: true })).toEqual({ error: null })
    expect(api.PATCH).toHaveBeenCalledWith('/v1/businesses/{business_id}/bank/accounts/{account_id}', {
      params: { path: { business_id: BUSINESS, account_id: ACCOUNT } },
      body: { included: true },
      headers: HEADERS,
    })
    expect(revalidatePath).toHaveBeenCalledWith(PAGE)
  })

  test.each([409, 500])('update action: %i is saveFailed', async (status) => {
    answers('PATCH', status)

    expect(await updateBankAccount(BUSINESS, ACCOUNT, { primary: true })).toEqual({ error: 'saveFailed' })
    expect(revalidatePath).not.toHaveBeenCalled()
  })

  test('C30 repair action posts to repair and revalidates on 200', async () => {
    answers('POST', 200)

    expect(await repairConnection(BUSINESS, CONNECTION)).toEqual({ error: null })
    expect(api.POST).toHaveBeenCalledWith(
      '/v1/businesses/{business_id}/bank/connections/{connection_id}/repair',
      { params: { path: PATH }, headers: HEADERS },
    )
    expect(revalidatePath).toHaveBeenCalledWith(PAGE)
  })

  test.each([409, 502, 'reject'] as const)('repair action: %s is reconnectFailed', async (status) => {
    if (status === 'reject') vi.mocked(api.POST).mockRejectedValue(new TypeError('fetch failed'))
    else answers('POST', status)

    expect(await repairConnection(BUSINESS, CONNECTION)).toEqual({ error: 'reconnectFailed' })
  })

  test('C47 disconnect action sends DELETE and revalidates on 204', async () => {
    answers('DELETE', 204)

    expect(await disconnectBank(BUSINESS, CONNECTION)).toEqual({ error: null })
    expect(api.DELETE).toHaveBeenCalledWith('/v1/businesses/{business_id}/bank/connections/{connection_id}', {
      params: { path: PATH },
      headers: HEADERS,
    })
    expect(revalidatePath).toHaveBeenCalledWith(PAGE)
  })

  test.each([404, 502, 'reject'] as const)('disconnect action: %s is disconnectFailed', async (status) => {
    if (status === 'reject') vi.mocked(api.DELETE).mockRejectedValue(new TypeError('fetch failed'))
    else answers('DELETE', status)

    expect(await disconnectBank(BUSINESS, CONNECTION)).toEqual({ error: 'disconnectFailed' })
    expect(revalidatePath).not.toHaveBeenCalled()
  })
})
