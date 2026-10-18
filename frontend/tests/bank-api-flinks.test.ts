import * as Sentry from '@sentry/nextjs'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { createFlinksConnectUrl } from '@/lib/api/bank'
import { api } from '@/lib/api/client'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { POST: vi.fn(), GET: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))

type PostResult = Awaited<ReturnType<typeof api.POST>>

const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const FLINKS = {
  connect_url: 'https://toolbox-iframe.private.fin.ag/v2/?authorizeToken=token-1',
  origin: 'https://toolbox-iframe.private.fin.ag',
}

function answers(status: number) {
  vi.mocked(api.POST).mockResolvedValue({
    data: status === 200 ? FLINKS : undefined,
    error: status === 200 ? undefined : { status },
    response: new Response(null, { status }),
  } as unknown as PostResult)
}

beforeEach(() => {
  vi.mocked(api.POST).mockReset()
  vi.mocked(Sentry.captureException).mockClear()
  vi.mocked(Sentry.captureMessage).mockClear()
})

describe('connect url loader', () => {
  test('200 returns the connect URL and its origin', async () => {
    answers(200)

    await expect(createFlinksConnectUrl(BUSINESS)).resolves.toEqual(FLINKS)
    expect(api.POST).toHaveBeenCalledWith('/v1/businesses/{business_id}/bank/flinks/connect-url', {
      params: { path: { business_id: BUSINESS } },
      headers: { Authorization: 'Bearer tok_test' },
    })
  })

  test('404 is Flinks off: null, and nothing reported', async () => {
    answers(404)

    await expect(createFlinksConnectUrl(BUSINESS)).resolves.toBeNull()
    expect(Sentry.captureException).not.toHaveBeenCalled()
    expect(Sentry.captureMessage).not.toHaveBeenCalled()
  })

  test('503 is a failure: null, reported to Sentry', async () => {
    answers(503)

    await expect(createFlinksConnectUrl(BUSINESS)).resolves.toBeNull()
    expect(Sentry.captureException).toHaveBeenCalledTimes(1)
  })

  test('a network error is a failure: null, reported to Sentry', async () => {
    const error = new TypeError('fetch failed')
    vi.mocked(api.POST).mockRejectedValue(error)

    await expect(createFlinksConnectUrl(BUSINESS)).resolves.toBeNull()
    expect(Sentry.captureException).toHaveBeenCalledWith(error)
  })
})
