import { beforeEach, describe, expect, test, vi } from 'vitest'
import { saveEmailPreferences } from '@/app/(app)/settings/email/actions'
import { api } from '@/lib/api/client'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { PUT: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
const revalidatePath = vi.hoisted(() => vi.fn())
vi.mock('next/cache', () => ({ revalidatePath }))

function answers(status: number) {
  vi.mocked(api.PUT).mockResolvedValue({
    data: status < 300 ? { alerts: true, weekly_digest: false } : undefined,
    error: status < 300 ? undefined : { status },
    response: new Response(null, { status }),
  } as never)
}

beforeEach(() => {
  vi.mocked(api.PUT).mockReset()
  revalidatePath.mockClear()
})

describe('email preferences save action', () => {
  test('save action puts both values with the session headers', async () => {
    answers(200)

    expect(await saveEmailPreferences({ alerts: true, weekly_digest: false })).toEqual({ ok: true })
    expect(api.PUT).toHaveBeenCalledWith('/v1/me/email-preferences', {
      body: { alerts: true, weekly_digest: false },
      headers: { Authorization: 'Bearer tok_test' },
    })
    expect(revalidatePath).toHaveBeenCalledWith('/settings/email')
  })

  test.each([401, 422, 500])('save action: %i is not ok', async (status) => {
    answers(status)

    expect(await saveEmailPreferences({ alerts: false, weekly_digest: false })).toEqual({ ok: false })
  })

  test('save action: a thrown error is not ok, and never throws', async () => {
    vi.mocked(api.PUT).mockRejectedValue(new Error('network'))

    await expect(saveEmailPreferences({ alerts: false, weekly_digest: true })).resolves.toEqual({ ok: false })
  })
})
