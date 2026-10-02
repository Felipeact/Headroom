import { render, screen } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { beforeEach, expect, test, vi } from 'vitest'
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
vi.mock('next/navigation', () => ({ usePathname: () => '/', useRouter: () => ({ refresh: vi.fn() }) }))

type GetResult = Awaited<ReturnType<typeof api.GET>>

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
})

test('me fails with 401: error state, no page', async () => {
  vi.mocked(api.GET).mockResolvedValue({
    error: { status: 401 },
    response: new Response(null, { status: 401 }),
  } as unknown as GetResult)

  await renderLayout()

  expect(screen.getByText(messages.States.errorTitle)).toBeDefined()
  expect(screen.queryByText('page content')).toBeNull()
})

test('me fails when the call rejects: error state, no page', async () => {
  vi.mocked(api.GET).mockRejectedValue(new TypeError('fetch failed'))

  await renderLayout()

  expect(screen.getByText(messages.States.errorTitle)).toBeDefined()
  expect(screen.queryByText('page content')).toBeNull()
})

test('me succeeds: the page renders and the call carries the token', async () => {
  vi.mocked(api.GET).mockResolvedValue({
    data: {},
    response: new Response('{}', { status: 200 }),
  } as unknown as GetResult)

  await renderLayout()

  expect(screen.getByText('page content')).toBeDefined()
  expect(api.GET).toHaveBeenCalledWith('/v1/me', {
    headers: { Authorization: 'Bearer tok_test' },
  })
})
