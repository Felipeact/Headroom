import { render, screen } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { createTranslator } from 'next-intl'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import Loading from '@/app/onboarding/loading'
import BusinessStepPage from '@/app/onboarding/business/page'
import { api } from '@/lib/api/client'
import messages from '@/messages/en.json'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('@/app/onboarding/business/actions', () => ({ createBusiness: vi.fn() }))
vi.mock('next-intl/server', () => ({
  getTranslations: async () => createTranslator({ locale: 'en', messages }),
}))
const redirect = vi.hoisted(() =>
  vi.fn((url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`)
  }),
)
vi.mock('next/navigation', () => ({ redirect, useRouter: () => ({ refresh: vi.fn() }) }))

type GetResult = Awaited<ReturnType<typeof api.GET>>

function answers(status: number, body?: unknown) {
  vi.mocked(api.GET).mockResolvedValue({
    data: status === 200 ? body : undefined,
    error: status === 200 ? undefined : { status },
    response: new Response(null, { status }),
  } as unknown as GetResult)
}

async function renderPage() {
  const tree = await BusinessStepPage()
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {tree}
    </NextIntlClientProvider>,
  )
}

const formHeading = () =>
  screen.queryByRole('heading', { name: messages.Onboarding.Business.title })

beforeEach(() => {
  vi.mocked(api.GET).mockReset()
  redirect.mockClear()
})

describe('onboarding page', () => {
  test('a user with a business is sent to the dashboard', async () => {
    answers(200, { items: [{ id: 'b1', name: 'Harbor Street Plumbing' }] })

    await expect(renderPage()).rejects.toThrow('NEXT_REDIRECT')

    expect(redirect).toHaveBeenCalledWith('/')
  })

  test('no business: the form renders', async () => {
    answers(200, { items: [] })

    await renderPage()

    expect(redirect).not.toHaveBeenCalled()
    expect(formHeading()).not.toBeNull()
    expect(screen.getByRole('button', { name: messages.Onboarding.Business.continue })).toBeDefined()
  })

  test('the call fails with 500: error state, no form', async () => {
    answers(500)

    await renderPage()

    expect(screen.getByText(messages.States.errorTitle)).toBeDefined()
    expect(formHeading()).toBeNull()
  })

  test('the call rejects: error state, no form', async () => {
    vi.mocked(api.GET).mockRejectedValue(new TypeError('fetch failed'))

    await renderPage()

    expect(screen.getByText(messages.States.errorTitle)).toBeDefined()
    expect(formHeading()).toBeNull()
  })
})

test('loading state', () => {
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <Loading />
    </NextIntlClientProvider>,
  )

  const busy = screen.getByLabelText(messages.States.loading)
  expect(busy.getAttribute('aria-busy')).toBe('true')
})
