// @vitest-environment node
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

// Spec 32 C1-C5: the one place that talks to PostHog.
vi.mock('server-only', () => ({}))
const auth = vi.hoisted(() => vi.fn())
vi.mock('@clerk/nextjs/server', () => ({ auth }))
const sentry = vi.hoisted(() => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('@sentry/nextjs', () => sentry)
const captureImmediate = vi.hoisted(() => vi.fn())
const identify = vi.hoisted(() => vi.fn())
const PostHog = vi.hoisted(() =>
  vi.fn(function () {
    return { captureImmediate, identify }
  }),
)
vi.mock('posthog-node', () => ({ PostHog }))

async function load() {
  vi.resetModules()
  return import('@/lib/analytics')
}

beforeEach(() => {
  vi.stubEnv('POSTHOG_KEY', 'phc_test')
  vi.stubEnv('POSTHOG_HOST', 'https://eu.i.posthog.test')
  auth.mockReset().mockResolvedValue({ userId: 'user_clerk_1' })
  captureImmediate.mockReset().mockResolvedValue(undefined)
  identify.mockReset()
  PostHog.mockClear()
  sentry.captureException.mockClear()
  sentry.captureMessage.mockClear()
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.useRealTimers()
})

describe('capture', () => {
  test('captures with the Clerk user id and never identifies', async () => {
    const { capture } = await load()
    await capture('business_created', { business_id: 'b1' })

    expect(PostHog).toHaveBeenCalledWith('phc_test', expect.objectContaining({ host: 'https://eu.i.posthog.test' }))
    expect(captureImmediate).toHaveBeenCalledTimes(1)
    expect(captureImmediate).toHaveBeenCalledWith({
      distinctId: 'user_clerk_1',
      event: 'business_created',
      properties: { business_id: 'b1' },
    })
    expect(identify).not.toHaveBeenCalled()
  })

  test('event keys are fixed', async () => {
    const { EVENT_KEYS } = await load()
    expect(EVENT_KEYS).toEqual({
      sign_up_completed: [],
      business_created: ['business_id'],
      bank_connected: ['business_id'],
      minimum_balance_set: ['business_id'],
      dashboard_viewed: ['business_id', 'role'],
      alert_opened: ['business_id', 'alert_id', 'role'],
      alert_dismissed: ['business_id', 'alert_id'],
      expected_payment_added: ['business_id'],
    })
    const allowed = new Set(['business_id', 'alert_id', 'role'])
    for (const keys of Object.values(EVENT_KEYS)) for (const key of keys) expect(allowed.has(key)).toBe(true)
  })

  test('rejects a property outside the allowlist', async () => {
    const { capture } = await load()
    for (const extra of ['amount_cents', 'description', 'email', 'name']) {
      // The type already refuses it; the runtime guard is the second lock.
      await capture('business_created', { business_id: 'b1', [extra]: 'secret-value' } as never)
    }
    await capture('dashboard_viewed', { business_id: 'b1', role: 'owner', alert_id: 'a1' } as never)

    expect(captureImmediate).not.toHaveBeenCalled()
    expect(sentry.captureMessage).toHaveBeenCalledTimes(5)
    expect(JSON.stringify(sentry.captureMessage.mock.calls)).not.toContain('secret-value')
  })

  test('no key means no call', async () => {
    vi.stubEnv('POSTHOG_KEY', '')
    const { capture } = await load()
    await expect(capture('business_created', { business_id: 'b1' })).resolves.toBeUndefined()
    expect(PostHog).not.toHaveBeenCalled()
    expect(captureImmediate).not.toHaveBeenCalled()
    expect(auth).not.toHaveBeenCalled()
  })

  test('a failed capture is reported not thrown', async () => {
    const boom = new Error('network down')
    captureImmediate.mockRejectedValue(boom)
    const { capture } = await load()
    await expect(capture('alert_dismissed', { business_id: 'b1', alert_id: 'a1' })).resolves.toBeUndefined()

    expect(sentry.captureException).toHaveBeenCalledWith(boom)
    expect(JSON.stringify(sentry.captureException.mock.calls.flat().map(String))).not.toContain('a1')
  })

  test('gives up after 2 seconds', async () => {
    vi.useFakeTimers()
    captureImmediate.mockReturnValue(new Promise(() => {}))
    const { capture } = await load()
    let done = false
    const pending = capture('business_created', { business_id: 'b1' }).then(() => {
      done = true
    })

    await vi.advanceTimersByTimeAsync(1999)
    expect(done).toBe(false)
    await vi.advanceTimersByTimeAsync(1)
    await pending
    expect(done).toBe(true)
  })

  test('sends nothing without a signed-in user', async () => {
    auth.mockResolvedValue({ userId: null })
    const { capture } = await load()
    await capture('business_created', { business_id: 'b1' })
    expect(captureImmediate).not.toHaveBeenCalled()
  })
})
