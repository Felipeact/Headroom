import { render, screen, within } from '@testing-library/react'
import { NextIntlClientProvider, createTranslator } from 'next-intl'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import ForecastStepPage from '@/app/onboarding/forecast/page'
import { api } from '@/lib/api/client'
import messages from '@/messages/en.json'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('next-intl/server', () => ({
  getTranslations: async () => createTranslator({ locale: 'en', messages }),
}))
const redirect = vi.hoisted(() =>
  vi.fn((url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`)
  }),
)
const refresh = vi.hoisted(() => vi.fn())
vi.mock('next/navigation', () => ({ redirect, useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh }) }))

type Result = Awaited<ReturnType<typeof api.GET>>
const FORECAST = messages.Onboarding.Forecast
const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const CONNECTION = { id: 'c1', institution_name: 'Harbor Community Bank', accounts: [] }
const BUILDING = {
  state: 'building',
  institution_names: ['Harbor Community Bank'],
  transactions_read: true,
  history_months: 24,
  recurring_count: 11,
  recurring_names: ['Payroll', 'Rent'],
}
const SET = { amount_cents: 500000, currency: 'CAD', suggested_cents: 500000, updated_at: '2026-10-09T12:00:00Z' }

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
  minimum = SET as unknown,
  status = BUILDING as unknown,
  statusCode = 200,
} = {}) {
  vi.mocked(api.GET).mockImplementation(((path: string) => {
    if (path === '/v1/businesses') return Promise.resolve(reply(200, businesses))
    if (path.endsWith('/bank/connections')) return Promise.resolve(reply(200, connections))
    if (path.endsWith('/minimum-balance')) return Promise.resolve(reply(200, minimum))
    return Promise.resolve(reply(statusCode, status))
  }) as unknown as typeof api.GET)
}

async function renderPage() {
  const tree = await ForecastStepPage()
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {tree}
    </NextIntlClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(api.GET).mockReset()
  redirect.mockClear()
  refresh.mockClear()
})

describe('forecast step page', () => {
  test('C29 building', async () => {
    arrange()
    await renderPage()

    const header = screen.getByRole('banner')
    expect(header.textContent).toContain('Step 5 of 5')
    const segments = within(header).getByTestId('step-bar').children
    expect([...segments].every((s) => s.className.includes('bg-accent'))).toBe(true)
    expect(screen.getByRole('heading', { level: 1, name: FORECAST.title })).toBeDefined()
    expect(screen.getByText(FORECAST.intro)).toBeDefined()
    const status = screen.getByRole('status')
    expect(status.getAttribute('aria-live')).toBe('polite')
    const steps = within(status).getAllByRole('listitem')
    expect(steps.map((s) => [s.textContent, s.getAttribute('data-state')])).toEqual([
      ['Connected Harbor Community Bank', 'done'],
      ['Read 24 months of transactions', 'done'],
      ['Finding recurring paymentsPayroll, Rent, and 9 others so far', 'active'],
      ['Building your 13-week forecast', 'pending'],
    ])
    expect(screen.getByText(FORECAST.footer)).toBeDefined()
    expect(api.GET).toHaveBeenCalledWith('/v1/businesses/{business_id}/forecast/status', {
      params: { path: { business_id: BUSINESS } },
      headers: { Authorization: 'Bearer tok_test' },
    })
  })

  test('C32 states: ready shows every step done, with no server redirect', async () => {
    arrange({ status: { ...BUILDING, state: 'ready' } })
    await renderPage()
    expect(redirect).not.toHaveBeenCalled()
    const steps = within(screen.getByRole('status')).getAllByRole('listitem')
    expect(steps.map((s) => s.getAttribute('data-state'))).toEqual(['done', 'done', 'done', 'done'])
  })

  test('C32 states: needs attention', async () => {
    arrange({ status: { ...BUILDING, state: 'needs_attention' } })
    await renderPage()
    expect(screen.getByText(FORECAST.needsAttention)).toBeDefined()
    expect(screen.getByRole('link', { name: FORECAST.fixBank }).getAttribute('href')).toBe('/settings/banks')
  })

  test('C32 states: load fails', async () => {
    arrange({ statusCode: 500, status: undefined })
    await renderPage()
    expect(screen.getByRole('heading', { name: messages.States.errorTitle })).toBeDefined()
    expect(screen.queryByRole('status')).toBeNull()
  })

  test('C32 states: no minimum balance goes back to step 4', async () => {
    arrange({ minimum: { ...SET, amount_cents: null, updated_at: null } })
    await expect(renderPage()).rejects.toThrow('NEXT_REDIRECT')
    expect(redirect).toHaveBeenCalledWith('/onboarding/minimum-balance')
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
