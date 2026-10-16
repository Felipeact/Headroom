import { render, screen } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import AppLayout from '@/app/(app)/layout'
import { api } from '@/lib/api/client'
import messages from '@/messages/en.json'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@/lib/user-name', () => ({ getUserName: vi.fn().mockResolvedValue('Ada Lovelace') }))
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))
vi.mock('@clerk/nextjs', () => ({
  SignOutButton: ({ children }: { children: React.ReactNode }) => children,
}))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
const redirect = vi.hoisted(() =>
  vi.fn((url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`)
  }),
)
vi.mock('next/navigation', () => ({
  redirect,
  usePathname: () => '/',
  useRouter: () => ({ refresh: vi.fn() }),
}))

type GetResult = Awaited<ReturnType<typeof api.GET>>

const HARBOR = {
  id: '6f1c1b1e-7d55-4a43-9a8e-3c1f3c2a9b10',
  name: 'Harbor Street Plumbing',
  province: 'ON',
  time_zone: 'America/Toronto',
  country: 'CA',
  currency: 'CAD',
  role: 'owner',
  created_at: '2026-10-04T12:00:00Z',
}

function answers(status: number, body?: unknown) {
  vi.mocked(api.GET).mockResolvedValue({
    data: status === 200 ? body : undefined,
    error: status === 200 ? undefined : { status },
    response: new Response(JSON.stringify(body ?? {}), { status }),
  } as unknown as GetResult)
}

async function renderLayout() {
  const tree = await AppLayout({
    children: <p>page content</p>,
    params: Promise.resolve({}),
  } as Parameters<typeof AppLayout>[0])
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {tree}
    </NextIntlClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(api.GET).mockReset()
  redirect.mockClear()
})

describe('businesses', () => {
  test('no business: redirects to onboarding step 2', async () => {
    answers(200, { items: [] })

    await expect(renderLayout()).rejects.toThrow('NEXT_REDIRECT')

    expect(redirect).toHaveBeenCalledWith('/onboarding/business')
  })

  test('a business: the page renders with its name in the header', async () => {
    answers(200, { items: [HARBOR] })

    await renderLayout()

    expect(redirect).not.toHaveBeenCalled()
    expect(screen.getByText('page content')).toBeDefined()
    expect(screen.getByTestId('header-phone-identity').textContent).toBe('Harbor Street Plumbing')
    expect(screen.getByTestId('header-desktop-identity').textContent).toContain(
      'Harbor Street Plumbing',
    )
    expect(api.GET).toHaveBeenCalledWith('/v1/businesses', {
      headers: { Authorization: 'Bearer tok_test' },
    })
  })

  test('the call fails with 500: error state, no page', async () => {
    answers(500)

    await renderLayout()

    expect(screen.getByText(messages.States.errorTitle)).toBeDefined()
    expect(screen.queryByText('page content')).toBeNull()
    expect(redirect).not.toHaveBeenCalled()
  })

  test('the call fails with 401: error state, no page', async () => {
    answers(401)

    await renderLayout()

    expect(screen.getByText(messages.States.errorTitle)).toBeDefined()
    expect(screen.queryByText('page content')).toBeNull()
  })

  test('the call rejects: error state, no page', async () => {
    vi.mocked(api.GET).mockRejectedValue(new TypeError('fetch failed'))

    await renderLayout()

    expect(screen.getByText(messages.States.errorTitle)).toBeDefined()
    expect(screen.queryByText('page content')).toBeNull()
  })
})
