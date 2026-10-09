import { render, screen } from '@testing-library/react'
import { NextIntlClientProvider, createTranslator } from 'next-intl'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import MinimumBalanceStepPage from '@/app/onboarding/minimum-balance/page'
import { api } from '@/lib/api/client'
import messages from '@/messages/en.json'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), PUT: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('@/app/onboarding/minimum-balance/actions', () => ({ saveMinimumBalance: vi.fn() }))
vi.mock('next-intl/server', () => ({
  getTranslations: async () => createTranslator({ locale: 'en', messages }),
}))
const redirect = vi.hoisted(() =>
  vi.fn((url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`)
  }),
)
vi.mock('next/navigation', () => ({ redirect, useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }))

type Result = Awaited<ReturnType<typeof api.GET>>
const MINIMUM = messages.Onboarding.Minimum
const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const CONNECTION = { id: 'c1', institution_name: 'Harbor Community Bank', accounts: [] }

function reply(status: number, body?: unknown) {
  return {
    data: status < 300 ? body : undefined,
    error: status < 300 ? undefined : { status },
    response: new Response(null, { status }),
  } as unknown as Result
}

function arrange({
  businesses = { items: [{ id: BUSINESS, name: 'Harbor Street Plumbing' }] } as unknown,
  connections = { items: [CONNECTION] } as unknown,
  minimum = { amount_cents: null, currency: 'CAD', suggested_cents: 500000, updated_at: null } as unknown,
  minimumStatus = 200,
} = {}) {
  vi.mocked(api.GET).mockImplementation(((path: string) => {
    if (path === '/v1/businesses') return Promise.resolve(reply(200, businesses))
    if (path.endsWith('/bank/connections')) return Promise.resolve(reply(200, connections))
    return Promise.resolve(reply(minimumStatus, minimum))
  }) as unknown as typeof api.GET)
}

async function renderPage() {
  const tree = await MinimumBalanceStepPage()
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {tree}
    </NextIntlClientProvider>,
  )
}

const input = () => screen.getByRole('textbox', { name: MINIMUM.label }) as HTMLInputElement

beforeEach(() => {
  vi.mocked(api.GET).mockReset()
  redirect.mockClear()
})

describe('minimum balance page', () => {
  test('C20 suggested', async () => {
    arrange()
    await renderPage()

    expect(screen.getByRole('banner').textContent).toContain('Step 4 of 5')
    expect(screen.getByRole('heading', { level: 1, name: MINIMUM.title })).toBeDefined()
    expect(screen.getByText(MINIMUM.intro)).toBeDefined()
    expect(input().value).toBe('5,000')
    expect(screen.getByText('Suggested: $5,000, about two weeks of your typical spending.')).toBeDefined()
    expect(screen.getByText(MINIMUM.alertsTitle)).toBeDefined()
    expect(
      screen.getByText(
        'If your forecast dips below $5,000, you get an email that names the payments causing it and suggests ways to fix it.',
      ),
    ).toBeDefined()
    expect(screen.getByText(MINIMUM.settingsNote)).toBeDefined()
    expect(screen.getByRole('button', { name: MINIMUM.continue })).toBeDefined()
    expect(api.GET).toHaveBeenCalledWith('/v1/businesses/{business_id}/minimum-balance', {
      params: { path: { business_id: BUSINESS } },
      headers: { Authorization: 'Bearer tok_test' },
    })
  })

  test('C21 stored', async () => {
    arrange({
      minimum: { amount_cents: 1200000, currency: 'CAD', suggested_cents: 500000, updated_at: '2026-10-09T12:00:00Z' },
    })
    await renderPage()

    expect(input().value).toBe('12,000')
    expect(screen.getByText(/If your forecast dips below \$12,000,/)).toBeDefined()
  })

  test('C22 no suggestion', async () => {
    arrange({ minimum: { amount_cents: null, currency: 'CAD', suggested_cents: null, updated_at: null } })
    await renderPage()

    expect(input().value).toBe('')
    expect(screen.queryByText(/Suggested:/)).toBeNull()
    expect(screen.getByText(MINIMUM.alertsBodyNoAmount)).toBeDefined()
  })

  test('C27 load fails', async () => {
    arrange({ minimumStatus: 500, minimum: undefined })
    await renderPage()

    expect(screen.getByRole('heading', { name: messages.States.errorTitle })).toBeDefined()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.queryByRole('button', { name: MINIMUM.continue })).toBeNull()
  })

  test('C33 redirects', async () => {
    arrange({ businesses: { items: [] } })
    await expect(renderPage()).rejects.toThrow('NEXT_REDIRECT')
    expect(redirect).toHaveBeenCalledWith('/onboarding/business')

    redirect.mockClear()
    arrange({ connections: { items: [] } })
    await expect(renderPage()).rejects.toThrow('NEXT_REDIRECT')
    expect(redirect).toHaveBeenCalledWith('/onboarding/bank')
  })
})
