import { existsSync } from 'node:fs'
import { render, screen } from '@testing-library/react'
import { NextIntlClientProvider, createTranslator } from 'next-intl'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import BankStepPage from '@/app/onboarding/bank/page'
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
vi.mock('next/navigation', () => ({ redirect, useRouter: () => ({ refresh: vi.fn() }) }))

type Result = Awaited<ReturnType<typeof api.GET>>
const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const ONE_BUSINESS = { items: [{ id: BUSINESS, name: 'Harbor Street Plumbing' }] }

function reply(status: number, body?: unknown) {
  return {
    data: status < 300 ? body : undefined,
    error: status < 300 ? undefined : { status },
    response: new Response(null, { status }),
  } as unknown as Result
}

function businesses(status: number, body?: unknown) {
  vi.mocked(api.GET).mockResolvedValue(reply(status, body))
}

function linkToken(status: number) {
  vi.mocked(api.POST).mockResolvedValue(
    reply(status, { link_token: 'link-sandbox-123', expiration: '2026-10-04T16:00:00Z' }),
  )
}

async function renderPage() {
  const tree = await BankStepPage()
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {tree}
    </NextIntlClientProvider>,
  )
}

const connectButton = () => screen.queryByRole('button', { name: messages.Onboarding.Bank.connect })

beforeEach(() => {
  vi.mocked(api.GET).mockReset()
  vi.mocked(api.POST).mockReset()
  usePlaidLink.mockClear()
  redirect.mockClear()
})

describe('bank page', () => {
  test('no business: sent to step 2', async () => {
    businesses(200, { items: [] })

    await expect(renderPage()).rejects.toThrow('NEXT_REDIRECT')

    expect(redirect).toHaveBeenCalledWith('/onboarding/business')
  })

  test('a business and a link token: the connect view gets the token', async () => {
    businesses(200, ONE_BUSINESS)
    linkToken(200)

    await renderPage()

    expect(redirect).not.toHaveBeenCalled()
    expect(connectButton()).not.toBeNull()
    expect(usePlaidLink).toHaveBeenCalledWith(expect.objectContaining({ token: 'link-sandbox-123' }))
    expect(api.POST).toHaveBeenCalledWith('/v1/businesses/{business_id}/bank/link-token', {
      params: { path: { business_id: BUSINESS } },
      headers: { Authorization: 'Bearer tok_test' },
    })
  })

  test('header: the wordmark, step 3 of 5, and three of five segments filled', async () => {
    businesses(200, ONE_BUSINESS)
    linkToken(200)

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
    // The header comes before the page heading, as in the mockup.
    const heading = screen.getByRole('heading', { level: 1, name: messages.Onboarding.Bank.title })
    expect(header.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  const failures: [string, () => void][] = [
    ['businesses answer 500', () => businesses(500)],
    ['businesses reject', () => vi.mocked(api.GET).mockRejectedValue(new TypeError('fetch failed'))],
    [
      'link token answers 502',
      () => {
        businesses(200, ONE_BUSINESS)
        linkToken(502)
      },
    ],
    [
      'link token rejects',
      () => {
        businesses(200, ONE_BUSINESS)
        vi.mocked(api.POST).mockRejectedValue(new TypeError('fetch failed'))
      },
    ],
  ]

  test.each(failures)('%s: error state, no connect button', async (_, arrange) => {
    arrange()

    await renderPage()

    expect(screen.getByText(messages.States.errorTitle)).toBeDefined()
    expect(connectButton()).toBeNull()
  })

  test('uses the onboarding loading state', () => {
    expect(existsSync('app/onboarding/loading.tsx')).toBe(true)
    expect(existsSync('app/onboarding/bank/loading.tsx')).toBe(false)
  })
})
