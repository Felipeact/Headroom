import * as Sentry from '@sentry/nextjs'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { NextIntlClientProvider, createTranslator } from 'next-intl'
import type { PlaidLinkOptionsWithLinkToken } from 'react-plaid-link'
import { toast } from 'sonner'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { disconnectBank, repairConnection, updateBankAccount } from '@/app/(app)/settings/banks/actions'
import Loading from '@/app/(app)/settings/banks/loading'
import BankSettingsPage from '@/app/(app)/settings/banks/page'
import { connectBank } from '@/app/onboarding/bank/actions'
import { api } from '@/lib/api/client'
import type { components } from '@/lib/api/schema'
import messages from '@/messages/en.json'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('@/app/(app)/settings/banks/actions', () => ({
  updateBankAccount: vi.fn(),
  repairConnection: vi.fn(),
  disconnectBank: vi.fn(),
}))
vi.mock('@/app/onboarding/bank/actions', () => ({ connectBank: vi.fn() }))
vi.mock('next-intl/server', () => ({
  getTranslations: async () => createTranslator({ locale: 'en', messages }),
}))
vi.mock('sonner', async (original) => ({ ...(await original<typeof import('sonner')>()), toast: vi.fn() }))
const plaid = vi.hoisted(() => ({
  open: vi.fn(),
  links: new Map<string, PlaidLinkOptionsWithLinkToken>(),
}))
vi.mock('react-plaid-link', () => ({
  usePlaidLink: (options: PlaidLinkOptionsWithLinkToken) => {
    plaid.links.set(options.token as string, options)
    return { open: plaid.open, ready: true }
  },
}))
vi.mock('next/navigation', () => ({
  redirect: vi.fn(),
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => '/settings/banks',
}))

type Connection = components['schemas']['Connection']
type Account = components['schemas']['Account']
type Result = Awaited<ReturnType<typeof api.GET>>
type Answer = number | 'reject'

const BANKS = messages.Settings.Banks
const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const BUSINESSES = {
  items: [{ id: BUSINESS, name: 'Harbor Street Plumbing', time_zone: 'America/Toronto', role: 'owner' }],
}

function account(name: string, overrides: Partial<Account> = {}): Account {
  return {
    id: `id-${name}`,
    name,
    type: 'checking',
    mask: '2381',
    currency: 'CAD',
    balance_cents: 800000,
    available_cents: null,
    included: true,
    primary: false,
    ...overrides,
  }
}

const CHECKING = account('Operating checking', { primary: true })
const SAVINGS = account('Reserve savings', { type: 'savings', mask: '9025', balance_cents: 3430000, included: false })
const LINE = account('Line of credit', {
  type: 'line_of_credit',
  mask: '7702',
  balance_cents: 0,
  available_cents: 2000000,
  included: false,
})
const CARD = account('Business Visa', {
  type: 'credit_card',
  mask: '5530',
  balance_cents: 245000,
  available_cents: 755000,
  included: false,
})

function bank(name: string, overrides: Partial<Connection> = {}): Connection {
  return {
    id: `c-${name}`,
    institution_name: name,
    created_at: '2026-10-04T15:00:00Z',
    accounts: [CHECKING],
    status: 'synced',
    last_synced_at: '2026-10-06T06:04:00Z',
    ...overrides,
  }
}

const TD = 'TD Canada Trust'

function reply(status: number, body?: unknown) {
  return {
    data: status < 300 ? body : undefined,
    error: status < 300 ? undefined : { status },
    response: new Response(null, { status }),
  } as unknown as Result
}

function answer(status: Answer, body: unknown) {
  return status === 'reject' ? Promise.reject(new TypeError('fetch failed')) : Promise.resolve(reply(status, body))
}

function arrange(connections: Connection[], status: Answer = 200) {
  vi.mocked(api.GET).mockImplementation(((path: string) =>
    path === '/v1/businesses'
      ? answer(200, BUSINESSES)
      : answer(status, { items: connections })) as unknown as typeof api.GET)
  vi.mocked(api.POST).mockImplementation(((path: string, init: { params: { path: { connection_id?: string } } }) =>
    answer(200, {
      link_token: path.includes('{connection_id}') ? `update-${init.params.path.connection_id}` : 'link-sandbox-123',
      expiration: '2026-10-06T18:00:00Z',
    })) as unknown as typeof api.POST)
}

async function renderPage(connections: Connection[], status: Answer = 200) {
  arrange(connections, status)
  const tree = await BankSettingsPage()
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {tree}
    </NextIntlClientProvider>,
  )
}

const card = (name: string) => within(screen.getByRole('region', { name }))
const row = (name: string) => within(screen.getByRole('row', { name }))

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-06T14:00:00Z'))
  vi.mocked(api.GET).mockReset()
  vi.mocked(api.POST).mockReset()
  vi.mocked(Sentry.captureException).mockClear()
  vi.mocked(Sentry.captureMessage).mockClear()
  vi.mocked(updateBankAccount).mockReset()
  vi.mocked(repairConnection).mockReset()
  vi.mocked(disconnectBank).mockReset()
  vi.mocked(connectBank).mockReset()
  vi.mocked(toast).mockClear()
  plaid.open.mockClear()
  plaid.links.clear()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('bank settings page', () => {
  test('C7 status lines', async () => {
    await renderPage([
      bank('Harbor Community Bank'),
      bank('Summit Federal', { last_synced_at: '2026-10-03T06:04:00Z' }),
      bank('RBC Royal Bank', { status: 'syncing', last_synced_at: null }),
      bank(TD, { status: 'login_required' }),
      bank('Scotiabank', { status: 'sync_failing' }),
    ])

    expect(card('Harbor Community Bank').getByText('Synced today at 2:04 AM')).toBeTruthy()
    expect(card('Summit Federal').getByText('Synced Oct 3 at 2:04 AM')).toBeTruthy()
    expect(card('RBC Royal Bank').getByText('Syncing…')).toBeTruthy()
    expect(card(TD).getByText('Needs attention')).toBeTruthy()
    expect(card('Scotiabank').getByText('Needs attention')).toBeTruthy()
    expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual([
      'Harbor Community Bank',
      'Summit Federal',
      'RBC Royal Bank',
      TD,
      'Scotiabank',
    ])
  })

  test('C9 account rows', async () => {
    await renderPage([bank('Harbor Community Bank', { accounts: [CHECKING, LINE, CARD] })])

    expect(row('Operating checking').getByText('••2381 · Checking')).toBeTruthy()
    expect(row('Operating checking').getByText('$8,000')).toBeTruthy()
    expect(row('Line of credit').getByText('••7702 · Credit')).toBeTruthy()
    expect(row('Line of credit').getByText('$20,000')).toBeTruthy()
    expect(row('Line of credit').getByText('available')).toBeTruthy()
    expect(row('Business Visa').getByText('••5530 · Credit card')).toBeTruthy()
    expect(row('Business Visa').getByText('$2,450')).toBeTruthy()
    expect(row('Business Visa').getByText('owed')).toBeTruthy()
  })

  test('C10 loading skeleton', () => {
    const { container } = render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <Loading />
      </NextIntlClientProvider>,
    )

    const busy = container.querySelector('[aria-busy="true"]')
    expect(busy).not.toBeNull()
    expect(busy?.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
  })

  test('C11 empty state', async () => {
    await renderPage([])

    expect(screen.getByRole('heading', { name: BANKS.emptyTitle })).toBeTruthy()
    expect(screen.getByText(BANKS.emptyBody)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: BANKS.connect }))
    expect(plaid.open).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('table')).toBeNull()
    expect(screen.queryByRole('button', { name: BANKS.disconnect })).toBeNull()
  })

  test.each([500, 'reject'] as const)('C12 load error: %s', async (status) => {
    await renderPage([], status)

    expect(screen.getByText(BANKS.errors.load)).toBeTruthy()
    expect(screen.getByRole('button', { name: messages.States.tryAgain })).toBeTruthy()
    expect(
      vi.mocked(Sentry.captureMessage).mock.calls.length + vi.mocked(Sentry.captureException).mock.calls.length,
    ).toBe(1)
  })

  test('C14 toggle counts as cash', async () => {
    vi.mocked(updateBankAccount).mockResolvedValue({ error: null })
    await renderPage([bank('Harbor Community Bank', { accounts: [CHECKING, SAVINGS] })])

    await act(async () => {
      fireEvent.click(row('Reserve savings').getByRole('switch', { name: 'Reserve savings counts as cash' }))
    })

    expect(updateBankAccount).toHaveBeenCalledWith(BUSINESS, SAVINGS.id, { included: true })
  })

  test('C15 credit rows', async () => {
    await renderPage([bank('Harbor Community Bank', { accounts: [CHECKING, SAVINGS, LINE, CARD] })])

    for (const name of ['Line of credit', 'Business Visa']) {
      expect(row(name).getByText(BANKS.creditNote)).toBeTruthy()
      expect(row(name).queryByRole('switch')).toBeNull()
    }
    for (const name of ['Reserve savings', 'Line of credit', 'Business Visa']) {
      expect(row(name).getByText(BANKS.notAvailable)).toBeTruthy()
      expect(row(name).queryByRole('radio')).toBeNull()
    }
  })

  test('C16 make primary', async () => {
    vi.mocked(updateBankAccount).mockResolvedValue({ error: null })
    const savings = { ...SAVINGS, included: true }
    await renderPage([bank('Harbor Community Bank', { accounts: [CHECKING, savings] })])

    const primary = row('Operating checking').getByRole('radio', { name: BANKS.primary })
    expect(primary.getAttribute('aria-checked')).toBe('true')
    const other = row('Reserve savings').getByRole('radio', { name: BANKS.makePrimary })
    expect(other.getAttribute('aria-checked')).toBe('false')

    await act(async () => {
      fireEvent.click(other)
    })

    expect(updateBankAccount).toHaveBeenCalledWith(BUSINESS, savings.id, { primary: true })
  })

  test('C17 save failed', async () => {
    vi.mocked(updateBankAccount).mockResolvedValue({ error: 'saveFailed' })
    await renderPage([bank('Harbor Community Bank', { accounts: [CHECKING, SAVINGS] })])
    const toggle = row('Reserve savings').getByRole('switch')

    await act(async () => {
      fireEvent.click(toggle)
    })

    expect(row('Reserve savings').getByRole('switch').getAttribute('aria-checked')).toBe('false')
    expect(screen.getByText(BANKS.errors.saveFailed)).toBeTruthy()
  })

  test('C27 login banner', async () => {
    await renderPage([bank(TD, { status: 'login_required' })])

    const alert = card(TD).getByRole('alert')
    expect(alert.textContent).toContain(
      "TD Canada Trust asked you to log in again. Until you do, your forecast is missing this bank's latest data.",
    )
    expect(within(alert).getByRole('button', { name: BANKS.reconnect })).toBeTruthy()
  })

  test('C28 sync failing banner', async () => {
    await renderPage([bank(TD, { status: 'sync_failing' }), bank('Harbor Community Bank')])

    expect(
      card(TD).getByText(
        "We couldn't sync TD Canada Trust for 3 nights. Until it works again, your forecast is missing this bank's latest data.",
      ),
    ).toBeTruthy()
    expect(card(TD).getByRole('button', { name: BANKS.reconnect })).toBeTruthy()
    const synced = card('Harbor Community Bank')
    expect(synced.queryByRole('button', { name: BANKS.reconnect })).toBeNull()
    expect(synced.queryByText(/your forecast is missing/)).toBeNull()
  })

  test('C30 update mode success', async () => {
    vi.mocked(repairConnection).mockResolvedValue({ error: null })
    const td = bank(TD, { status: 'login_required' })
    await renderPage([td])

    fireEvent.click(card(TD).getByRole('button', { name: BANKS.reconnect }))
    expect(plaid.open).toHaveBeenCalledTimes(1)
    const update = plaid.links.get(`update-${td.id}`)
    expect(update).toBeDefined()
    await act(async () => {
      update?.onSuccess('public-sandbox-update', {} as never)
    })

    expect(repairConnection).toHaveBeenCalledWith(BUSINESS, td.id)
    expect(connectBank).not.toHaveBeenCalled()
  })

  test('C34 reconnect errors', async () => {
    vi.mocked(repairConnection).mockResolvedValue({ error: 'reconnectFailed' })
    const td = bank(TD, { status: 'login_required' })
    await renderPage([td])
    const update = plaid.links.get(`update-${td.id}`)
    const failed = "We couldn't reconnect TD Canada Trust. Try again."

    await act(async () => {
      update?.onExit?.(null, {} as never)
    })
    expect(screen.queryByText(failed)).toBeNull()

    await act(async () => {
      update?.onSuccess('public-sandbox-update', {} as never)
    })
    expect(card(TD).getByText(failed)).toBeTruthy()
  })

  test('C36 disconnect dialog', async () => {
    await renderPage([bank(TD)])

    fireEvent.click(card(TD).getByRole('button', { name: BANKS.disconnect }))
    const dialog = screen.getByRole('dialog', { name: 'Disconnect TD Canada Trust?' })
    expect(within(dialog).getByText(BANKS.disconnectBody)).toBeTruthy()
    expect(within(dialog).getByRole('button', { name: BANKS.cancel })).toBeTruthy()
    expect(within(dialog).getByRole('button', { name: BANKS.disconnect })).toBeTruthy()

    fireEvent.keyDown(dialog, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()

    fireEvent.click(card(TD).getByRole('button', { name: BANKS.disconnect }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: BANKS.cancel }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(disconnectBank).not.toHaveBeenCalled()
  })

  test('C40 disconnect error', async () => {
    vi.mocked(disconnectBank).mockResolvedValue({ error: 'disconnectFailed' })
    await renderPage([bank(TD)])

    fireEvent.click(card(TD).getByRole('button', { name: BANKS.disconnect }))
    await act(async () => {
      fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: BANKS.disconnect }))
    })

    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText("We couldn't disconnect TD Canada Trust. Try again.")).toBeTruthy()
  })

  test('C47 disconnect success', async () => {
    vi.mocked(disconnectBank).mockResolvedValue({ error: null })
    const td = bank(TD)
    await renderPage([td])

    fireEvent.click(card(TD).getByRole('button', { name: BANKS.disconnect }))
    await act(async () => {
      fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: BANKS.disconnect }))
    })

    expect(disconnectBank).toHaveBeenCalledWith(BUSINESS, td.id)
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(toast).toHaveBeenCalledWith('TD Canada Trust disconnected')
  })
})
