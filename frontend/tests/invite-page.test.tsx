import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { NextIntlClientProvider, createTranslator } from 'next-intl'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { acceptInvitation } from '@/app/invite/[token]/actions'
import InvitePage from '@/app/invite/[token]/page'
import { loadInvitation } from '@/lib/api/members'
import messages from '@/messages/en.json'

vi.mock('server-only', () => ({}))
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('next-intl/server', () => ({
  getTranslations: async (namespace: string) =>
    createTranslator({ locale: 'en', messages, namespace: namespace as 'Invite' }),
}))
vi.mock('next/link', () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}))
vi.mock('@/lib/api/members', () => ({ loadInvitation: vi.fn() }))
vi.mock('@/app/invite/[token]/actions', () => ({ acceptInvitation: vi.fn() }))

const PARAMS = { params: Promise.resolve({ token: 'tok' }) } as never

async function renderPage(found: Awaited<ReturnType<typeof loadInvitation>>) {
  vi.mocked(loadInvitation).mockResolvedValue(found)
  const page = await InvitePage(PARAMS)
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {page}
    </NextIntlClientProvider>,
  )
}

const READY = { status: 'found', invitation: { business_name: 'Harbor Street Plumbing', status: 'pending' } } as const

beforeEach(() => {
  vi.mocked(acceptInvitation).mockReset()
})

describe('invite page', () => {
  test('invite page: ready', async () => {
    await renderPage(READY)

    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Join Harbor Street Plumbing on Headroom')
    expect(screen.getByRole('button', { name: 'Accept invitation' })).toBeTruthy()
    expect(acceptInvitation).not.toHaveBeenCalled()
  })

  test('invite page: accepting shows the dashboard link', async () => {
    vi.mocked(acceptInvitation).mockResolvedValue({ status: 'accepted' })
    await renderPage(READY)

    fireEvent.click(screen.getByRole('button', { name: 'Accept invitation' }))

    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('You now have access to Harbor Street Plumbing'),
    )
    expect(screen.getByRole('link', { name: 'Go to the dashboard' }).getAttribute('href')).toBe('/')
    expect(acceptInvitation).toHaveBeenCalledWith('tok')
  })

  test.each([
    ['expired', 'This invitation has expired'],
    ['wrongAddress', 'This invitation is for a different email address'],
    ['alreadyOwner', 'You already own this business'],
    ['notFound', "We can't find this invitation"],
  ] as const)('invite page: accept ends %s', async (status, title) => {
    vi.mocked(acceptInvitation).mockResolvedValue({ status })
    await renderPage(READY)

    fireEvent.click(screen.getByRole('button', { name: 'Accept invitation' }))

    await waitFor(() => expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(title))
  })

  test('invite page: a failed accept can be tried again', async () => {
    vi.mocked(acceptInvitation).mockResolvedValue({ status: 'failed' })
    await renderPage(READY)

    fireEvent.click(screen.getByRole('button', { name: 'Accept invitation' }))

    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toBe("We couldn't accept the invitation. Try again."),
    )
    await waitFor(() => expect(screen.getByRole('button', { name: 'Accept invitation' })).toBeTruthy())
  })

  test.each([
    ['expired', 'This invitation has expired'],
    ['accepted', 'This invitation was already used'],
  ] as const)('invite page: a %s link', async (status, title) => {
    await renderPage({ status: 'found', invitation: { business_name: 'Harbor Street Plumbing', status } })

    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(title)
    expect(screen.queryByRole('button', { name: 'Accept invitation' })).toBeNull()
  })

  test('invite page: unknown link and load error', async () => {
    const { unmount } = await renderPage({ status: 'not_found' })
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe("We can't find this invitation")
    unmount()

    await renderPage({ status: 'error' })
    expect(screen.getByRole('alert').textContent).toContain("We couldn't load this page")
  })
})
