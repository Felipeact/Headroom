import { beforeEach, describe, expect, test, vi } from 'vitest'
import { dismissAlert } from '@/app/(app)/actions'
import { api } from '@/lib/api/client'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { POST: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
const revalidatePath = vi.hoisted(() => vi.fn())
vi.mock('next/cache', () => ({ revalidatePath }))

const PATH = '/v1/businesses/{business_id}/alerts/{alert_id}/dismiss'

function answer(status: number) {
  vi.mocked(api.POST).mockResolvedValue({ response: new Response(null, { status }) } as never)
}

beforeEach(() => {
  vi.mocked(api.POST).mockReset()
  revalidatePath.mockClear()
})

describe('dismiss', () => {
  test('dismiss posts, revalidates the dashboard, and reports failures', async () => {
    answer(200)
    expect(await dismissAlert('biz-1', 'alert-1')).toEqual({ error: null })
    expect(api.POST).toHaveBeenCalledWith(PATH, {
      params: { path: { business_id: 'biz-1', alert_id: 'alert-1' } },
      headers: { Authorization: 'Bearer tok_test' },
    })
    expect(revalidatePath).toHaveBeenCalledWith('/')

    revalidatePath.mockClear()
    answer(500)
    expect(await dismissAlert('biz-1', 'alert-1')).toEqual({ error: 'dismissFailed' })
    expect(revalidatePath).not.toHaveBeenCalled()

    vi.mocked(api.POST).mockRejectedValue(new Error('network down'))
    expect(await dismissAlert('biz-1', 'alert-1')).toEqual({ error: 'dismissFailed' })
    expect(revalidatePath).not.toHaveBeenCalled()
  })
})
