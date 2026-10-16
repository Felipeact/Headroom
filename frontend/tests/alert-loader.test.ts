import * as Sentry from '@sentry/nextjs'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { loadAlert } from '@/lib/api/alerts'
import { api } from '@/lib/api/client'
import { ALERT } from './fixtures/dashboard-sample'

// Spec 27 C23: what the alert page's loader makes of each API answer.

vi.mock('server-only', () => ({}))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))

const answer = (status: number, data?: unknown) =>
  ({ data, response: new Response(null, { status }) }) as unknown as Awaited<ReturnType<typeof api.GET>>

beforeEach(() => {
  vi.mocked(api.GET).mockReset()
  vi.mocked(Sentry.captureMessage).mockClear()
  vi.mocked(Sentry.captureException).mockClear()
})

describe('C23 the alert loader', () => {
  test('200 returns the alert', async () => {
    vi.mocked(api.GET).mockResolvedValue(answer(200, ALERT))
    expect(await loadAlert('biz-1', ALERT.id)).toEqual(ALERT)
    expect(api.GET).toHaveBeenCalledWith('/v1/businesses/{business_id}/alerts/{alert_id}', {
      params: { path: { business_id: 'biz-1', alert_id: ALERT.id } },
      headers: { Authorization: 'Bearer tok_test' },
    })
  })

  test.each([404, 422])('%i is not_found, unreported', async (status) => {
    vi.mocked(api.GET).mockResolvedValue(answer(status))
    expect(await loadAlert('biz-1', 'not-a-uuid')).toBe('not_found')
    expect(Sentry.captureMessage).not.toHaveBeenCalled()
    expect(Sentry.captureException).not.toHaveBeenCalled()
  })

  test('500 is null and reported', async () => {
    vi.mocked(api.GET).mockResolvedValue(answer(500))
    expect(await loadAlert('biz-1', ALERT.id)).toBeNull()
    expect(Sentry.captureMessage).toHaveBeenCalledTimes(1)
  })

  test('a thrown fetch is null and reported', async () => {
    vi.mocked(api.GET).mockRejectedValue(new TypeError('fetch failed'))
    expect(await loadAlert('biz-1', ALERT.id)).toBeNull()
    expect(Sentry.captureException).toHaveBeenCalledTimes(1)
  })
})
