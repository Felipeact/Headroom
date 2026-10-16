import { existsSync } from 'node:fs'
import { render, screen } from '@testing-library/react'
import { NextIntlClientProvider, createTranslator } from 'next-intl'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import AccountsStepPage from '@/app/onboarding/accounts/page'
import { api } from '@/lib/api/client'
import messages from '@/messages/en.json'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('@/app/onboarding/bank/actions', () => ({ connectBank: vi.fn() }))
vi.mock('@/app/onboarding/accounts/actions', () => ({ updateAccount: vi.fn() }))
vi.mock('next-intl/server', () => ({
  getTranslations: async () => createTranslator({ locale: 'en', messages }),
}))
const usePlaidLink = vi.hoisted(() =>
  vi.fn<(options: unknown) => { open: () => void; ready: boolean }>(() => ({ open: vi.fn(), ready: true })),
)
vi.mock('react-plaid-link', () => ({ usePlaidLink }))
const redirect = vi.hoisted(() =>
  vi.fn((url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`)
  }),
)
vi.mock('next/navigation', () => ({ redirect, useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }))

type Result = Awaited<ReturnType<typeof api.GET>>
const ACCOUNTS = messages.Onboarding.Accounts
const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const ONE_BUSINESS = { items: [{ id: BUSINESS, name: 'Harbor Street Plumbing' }] }
const CONNECTION = {
  id: 'c1',
  institution_name: 'Harbor Community Bank',
  created_at: '2026-10-04T15:00:00Z',
  accounts: [
    {
      id: 'a1',
      name: 'Operating checking',
      type: 'checking',
      mask: '2381',
      currency: 'CAD',
      balance_cents: 800000,
      available_cents: 800000,
      included: true,
      primary: true,
    },
  ],
}

function reply(status: number, body?: unknown) {
  return {
    data: status < 300 ? body : undefined,
    error: status < 300 ? undefined : { status },
    response: new Response(null, { status }),
  } as unknown as Result
}

type Answer = number | 'reject'

function answer(status: Answer, body: unknown) {
  return status === 'reject' ? Promise.reject(new TypeError('fetch failed')) : Promise.resolve(reply(status, body))
}

function arrange({
  businesses = 200 as Answer,
  businessBody = ONE_BUSINESS as unknown,
  connections = 200 as Answer,
  connectionBody = { items: [CONNECTION] } as unknown,
  link = 200 as Answer,
} = {}) {
  vi.mocked(api.GET).mockImplementation(((path: string) =>
    path === '/v1/businesses'
      ? answer(businesses, businessBody)
      : answer(connections, connectionBody)) as unknown as typeof api.GET)
  vi.mocked(api.POST).mockImplementation((() =>
    answer(link, { link_token: 'link-sandbox-123', expiration: '2026-10-04T16:00:00Z' })) as unknown as typeof api.POST)
}

async function renderPage() {
  const tree = await AccountsStepPage()
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {tree}
    </NextIntlClientProvider>,
  )
}

const continueButton = () => screen.queryByRole('button', { name: ACCOUNTS.continue })

beforeEach(() => {
  vi.mocked(api.GET).mockReset()
  vi.mocked(api.POST).mockReset()
  usePlaidLink.mockClear()
  redirect.mockClear()
})

describe('accounts page', () => {
  test('no business: sent to step 2', async () => {
    arrange({ businessBody: { items: [] } })

    await expect(renderPage()).rejects.toThrow('NEXT_REDIRECT')

    expect(redirect).toHaveBeenCalledWith('/onboarding/business')
  })

  test('no connection: sent to step 3', async () => {
    arrange({ connectionBody: { items: [] } })

    await expect(renderPage()).rejects.toThrow('NEXT_REDIRECT')

    expect(redirect).toHaveBeenCalledWith('/onboarding/bank')
  })

  test('a business with a connection: the view gets the list and the link token', async () => {
    arrange()

    await renderPage()

    expect(redirect).not.toHaveBeenCalled()
    expect(continueButton()).not.toBeNull()
    expect(screen.getByText('Operating checking')).toBeDefined()
    expect(usePlaidLink).toHaveBeenCalledWith(expect.objectContaining({ token: 'link-sandbox-123' }))
    expect(api.GET).toHaveBeenCalledWith('/v1/businesses/{business_id}/bank/connections', {
      params: { path: { business_id: BUSINESS } },
      headers: { Authorization: 'Bearer tok_test' },
    })
  })

  test('header: the wordmark, step 3 of 5, and three of five segments filled', async () => {
    arrange()

    await renderPage()

    const header = screen.getByRole('banner')
    const text = header.textContent ?? ''
    const wordmark = text.indexOf(messages.Shell.wordmark)
    const step = text.indexOf('Step 3 of 5')
    expect(wordmark).toBeGreaterThanOrEqual(0)
    expect(step).toBeGreaterThan(wordmark)
    const bar = screen.getByTestId('step-bar')
    expect(bar.getAttribute('aria-hidden')).toBe('true')
    const segments = Array.from(bar.children)
    expect(segments).toHaveLength(5)
    expect(segments.filter((segment) => segment.className.includes('bg-accent'))).toHaveLength(3)
    const heading = screen.getByRole('heading', { level: 1, name: ACCOUNTS.title })
    expect(header.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  const failures: [string, Parameters<typeof arrange>[0]][] = [
    ['businesses answer 500', { businesses: 500 }],
    ['businesses reject', { businesses: 'reject' }],
    ['connections answer 500', { connections: 500 }],
    ['connections reject', { connections: 'reject' }],
    ['link token answers 502', { link: 502 }],
  ]

  test.each(failures)('%s: error state, no Continue button', async (_, options) => {
    arrange(options)

    await renderPage()

    expect(screen.getByText(messages.States.errorTitle)).toBeDefined()
    expect(continueButton()).toBeNull()
  })

  test('uses the onboarding loading state', () => {
    expect(existsSync('app/onboarding/loading.tsx')).toBe(true)
    expect(existsSync('app/onboarding/accounts/loading.tsx')).toBe(false)
  })
})
