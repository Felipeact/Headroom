import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { inviteBookkeeper, removeMember } from '@/app/(app)/settings/members/actions'
import Loading from '@/app/(app)/settings/members/loading'
import MembersSettingsPage from '@/app/(app)/settings/members/page'
import { MembersSection } from '@/components/settings/members-section'
import { loadBusinesses } from '@/lib/api/businesses'
import { loadMembers } from '@/lib/api/members'
import messages from '@/messages/en.json'

vi.mock('server-only', () => ({}))
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('next/navigation', () => ({
  redirect: vi.fn((url: string) => {
    throw new Error(`NEXT_REDIRECT ${url}`)
  }),
}))
vi.mock('@/lib/api/businesses', () => ({ loadBusinesses: vi.fn() }))
vi.mock('@/lib/api/members', () => ({ loadMembers: vi.fn() }))
vi.mock('@/app/(app)/settings/members/actions', () => ({ inviteBookkeeper: vi.fn(), removeMember: vi.fn() }))
vi.mock('sonner', async (original) => ({ ...(await original<typeof import('sonner')>()), toast: vi.fn() }))

const BUSINESS = { id: 'b1', name: 'Harbor Street Plumbing' }
const OWNER = { user_id: 'u1', role: 'owner', name: 'Dana', email: 'dana@example.test', receive_alert_emails: false } as const
const PAT = { user_id: 'u2', role: 'bookkeeper', name: 'Pat', email: 'pat@example.test', receive_alert_emails: false } as const
const PENDING = { id: 'i1', created_at: '2026-10-15T09:00:00Z', expires_at: '2026-10-22T09:00:00Z' }

function wrap(node: React.ReactNode) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {node}
    </NextIntlClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(inviteBookkeeper).mockReset()
  vi.mocked(removeMember).mockReset()
  vi.mocked(loadMembers).mockReset()
})

describe('members section', () => {
  test('members section: loading state', () => {
    wrap(<Loading />)

    expect(screen.getByRole('status', { name: 'Loading' })).toBeTruthy()
  })

  test('members section: empty state', () => {
    wrap(<MembersSection businessId="b1" members={{ items: [OWNER], invitations: [] }} />)

    expect(screen.getByText('No bookkeepers yet')).toBeTruthy()
    expect(screen.getByText('Invite your bookkeeper by email, and they can see your forecast.')).toBeTruthy()
    expect(screen.getAllByTestId('member-row')).toHaveLength(1)
  })

  test('members section: error state', async () => {
    vi.mocked(loadBusinesses).mockResolvedValue([{ ...BUSINESS, role: 'owner' }] as never)
    vi.mocked(loadMembers).mockResolvedValue(null)

    await expect(MembersSettingsPage()).rejects.toThrow('Members could not be loaded')
  })

  test('members section: a bookkeeper is sent to email preferences', async () => {
    vi.mocked(loadBusinesses).mockResolvedValue([{ ...BUSINESS, role: 'bookkeeper' }] as never)

    await expect(MembersSettingsPage()).rejects.toThrow('NEXT_REDIRECT /settings/email')
    expect(loadMembers).not.toHaveBeenCalled()
  })

  test('members section: one row per member and pending invitation', () => {
    wrap(<MembersSection businessId="b1" members={{ items: [OWNER, PAT], invitations: [PENDING] }} />)

    const rows = screen.getAllByTestId('member-row')
    expect(rows.map((row) => row.textContent)).toEqual([
      'DanaOwner · dana@example.test',
      'PatBookkeeper · pat@example.testRemove',
    ])
    expect(screen.getByTestId('pending-invitation').textContent).toBe('Invitation sent Oct 15, expires Oct 22')
    expect(screen.queryByTestId('members-empty')).toBeNull()
  })

  test('members section: removing asks first', async () => {
    vi.mocked(removeMember).mockResolvedValue({ error: null })
    wrap(<MembersSection businessId="b1" members={{ items: [OWNER, PAT], invitations: [] }} />)

    fireEvent.click(screen.getByRole('button', { name: 'Remove Pat' }))
    expect(screen.getByText('Remove Pat?')).toBeTruthy()
    expect(removeMember).not.toHaveBeenCalled()
    fireEvent.click(screen.getAllByRole('button', { name: 'Remove' }).at(-1)!)

    await waitFor(() => expect(removeMember).toHaveBeenCalledWith('b1', 'u2'))
  })

  test('members section: invite sends the trimmed address, and an invalid one is refused first', async () => {
    vi.mocked(inviteBookkeeper).mockResolvedValue({ error: 'alreadyInvited' })
    wrap(<MembersSection businessId="b1" members={{ items: [OWNER], invitations: [] }} />)
    const input = screen.getByLabelText("Bookkeeper's email address")

    fireEvent.change(input, { target: { value: 'not-an-email' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send invitation' }))
    expect(screen.getByRole('alert').textContent).toBe('Enter a valid email address.')
    expect(inviteBookkeeper).not.toHaveBeenCalled()

    fireEvent.change(input, { target: { value: '  pat@example.test ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send invitation' }))
    await waitFor(() => expect(inviteBookkeeper).toHaveBeenCalledWith('b1', 'pat@example.test'))
    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toBe('That address already has a pending invitation.'),
    )
  })
})
