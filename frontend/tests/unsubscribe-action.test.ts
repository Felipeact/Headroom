import { beforeEach, describe, expect, test, vi } from 'vitest'
import { unsubscribe } from '@/app/unsubscribe/[token]/actions'
import { api } from '@/lib/api/client'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { POST: vi.fn() } }))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))

const TOKEN = 'tok_' + 'a'.repeat(39)

function answers(status: number) {
  vi.mocked(api.POST).mockResolvedValue({
    data: status === 200 ? { status: 'unsubscribed' } : undefined,
    error: status === 200 ? undefined : { status },
    response: new Response(null, { status }),
  } as never)
}

beforeEach(() => {
  vi.mocked(api.POST).mockReset()
})

describe('unsubscribe action', () => {
  test('unsubscribe action posts the token with no Authorization header', async () => {
    answers(200)

    expect(await unsubscribe(TOKEN)).toEqual({ status: 'unsubscribed' })
    expect(api.POST).toHaveBeenCalledTimes(1)
    const [path, init] = vi.mocked(api.POST).mock.calls[0] as unknown as [string, Record<string, unknown>]
    expect(path).toBe('/v1/unsubscribe/{token}')
    expect(init).toEqual({ params: { path: { token: TOKEN } } })
    expect(JSON.stringify(init)).not.toContain('Authorization')
  })

  test('unsubscribe action: 404 is invalid', async () => {
    answers(404)

    expect(await unsubscribe(TOKEN)).toEqual({ status: 'invalid' })
  })

  test.each([401, 422, 429, 500, 503])('unsubscribe action: %i is error', async (status) => {
    answers(status)

    expect(await unsubscribe(TOKEN)).toEqual({ status: 'error' })
  })

  test('unsubscribe action: a thrown error is error', async () => {
    vi.mocked(api.POST).mockRejectedValue(new Error('network'))

    expect(await unsubscribe(TOKEN)).toEqual({ status: 'error' })
  })
})
