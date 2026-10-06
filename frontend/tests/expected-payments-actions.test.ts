import { beforeEach, describe, expect, test, vi } from 'vitest'
import {
  createExpectedPayment,
  deleteExpectedPayment,
  updateExpectedPayment,
  type ExpectedPaymentBody,
} from '@/app/(app)/expected-payments/actions'
import { api } from '@/lib/api/client'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
const revalidatePath = vi.hoisted(() => vi.fn())
vi.mock('next/cache', () => ({ revalidatePath }))

const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const PAYMENT = '6f1c2b0e-0000-4000-8000-0000000000e1'
const PAGE = '/expected-payments'
const HEADERS = { Authorization: 'Bearer tok_test' }
const LIST = '/v1/businesses/{business_id}/expected-payments'
const ONE = '/v1/businesses/{business_id}/expected-payments/{payment_id}'
const BODY: ExpectedPaymentBody = {
  account_id: null,
  description: 'Van repair deposit',
  amount_cents: -230050,
  date: '2026-11-20',
  repeats: null,
}

function answers(method: 'POST' | 'PUT' | 'DELETE', status: number, detail?: string) {
  vi.mocked(api[method]).mockResolvedValue({
    data: status < 300 ? {} : undefined,
    error: status < 300 ? undefined : { status, detail },
    response: new Response(null, { status }),
  } as never)
}

beforeEach(() => {
  vi.mocked(api.POST).mockReset()
  vi.mocked(api.PUT).mockReset()
  vi.mocked(api.DELETE).mockReset()
  revalidatePath.mockClear()
})

describe('server actions', () => {
  test('create posts the body and revalidates on 201', async () => {
    answers('POST', 201)
    expect(await createExpectedPayment(BUSINESS, BODY)).toEqual({ ok: true })
    expect(api.POST).toHaveBeenCalledWith(LIST, {
      params: { path: { business_id: BUSINESS } },
      body: BODY,
      headers: HEADERS,
    })
    expect(revalidatePath).toHaveBeenCalledWith(PAGE)
  })

  test('update puts the body and revalidates on 200', async () => {
    answers('PUT', 200)
    expect(await updateExpectedPayment(BUSINESS, PAYMENT, BODY)).toEqual({ ok: true })
    expect(api.PUT).toHaveBeenCalledWith(ONE, {
      params: { path: { business_id: BUSINESS, payment_id: PAYMENT } },
      body: BODY,
      headers: HEADERS,
    })
    expect(revalidatePath).toHaveBeenCalledWith(PAGE)
  })

  test('delete deletes and revalidates on 204', async () => {
    answers('DELETE', 204)
    expect(await deleteExpectedPayment(BUSINESS, PAYMENT)).toEqual({ ok: true })
    expect(api.DELETE).toHaveBeenCalledWith(ONE, {
      params: { path: { business_id: BUSINESS, payment_id: PAYMENT } },
      headers: HEADERS,
    })
    expect(revalidatePath).toHaveBeenCalledWith(PAGE)
  })

  test('a problem response returns its status and detail, and revalidates nothing', async () => {
    answers('POST', 409, 'Choose an account you count as cash.')
    expect(await createExpectedPayment(BUSINESS, BODY)).toEqual({
      ok: false,
      status: 409,
      detail: 'Choose an account you count as cash.',
    })
    answers('PUT', 422)
    expect(await updateExpectedPayment(BUSINESS, PAYMENT, BODY)).toEqual({ ok: false, status: 422, detail: null })
    answers('DELETE', 404, 'Expected payment not found.')
    expect(await deleteExpectedPayment(BUSINESS, PAYMENT)).toEqual({
      ok: false,
      status: 404,
      detail: 'Expected payment not found.',
    })
    expect(revalidatePath).not.toHaveBeenCalled()
  })

  test('an unreachable API returns status 0', async () => {
    vi.mocked(api.POST).mockRejectedValue(new Error('down'))
    expect(await createExpectedPayment(BUSINESS, BODY)).toEqual({ ok: false, status: 0, detail: null })
  })
})
