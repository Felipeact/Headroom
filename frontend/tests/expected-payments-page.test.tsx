import { render, screen, within } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import Loading from '@/app/(app)/expected-payments/loading'
import ExpectedPaymentsPage from '@/app/(app)/expected-payments/page'
import { api } from '@/lib/api/client'
import type { components } from '@/lib/api/schema'
import messages from '@/messages/en.json'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn() } }))
vi.mock('@/lib/api/auth', () => ({
  authHeaders: vi.fn().mockResolvedValue({ Authorization: 'Bearer tok_test' }),
}))
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('@/app/(app)/expected-payments/actions', () => ({
  createExpectedPayment: vi.fn(),
  updateExpectedPayment: vi.fn(),
  deleteExpectedPayment: vi.fn(),
}))
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => '/expected-payments',
}))

type Payment = components['schemas']['ExpectedPayment']
type Connection = components['schemas']['Connection']

const COPY = messages.ExpectedPayments
const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const OPERATING = '6f1c2b0e-0000-4000-8000-0000000000a1'

function payment(description: string, overrides: Partial<Payment> = {}): Payment {
  return {
    id: `id-${description}`,
    account_id: OPERATING,
    description,
    amount_cents: 100000,
    currency: 'CAD',
    date: '2026-10-06',
    repeats: null,
    next_date: '2026-10-06',
    overdue: false,
    ...overrides,
  }
}

const SAMPLE: Payment[] = [
  payment('Acme Co, invoice 1042', { amount_cents: 800000, date: '2026-10-06', next_date: '2026-10-06' }),
  payment('Coastal Supply Co, quarterly order', {
    amount_cents: -1450000,
    date: '2026-11-12',
    next_date: '2026-11-12',
    repeats: 'quarterly',
  }),
  payment('Birch & Co, invoice 1057', { amount_cents: 960000, date: '2026-11-17', next_date: '2026-11-17' }),
  payment('Equipment lease deposit', { amount_cents: -300000, date: '2026-12-07', next_date: '2026-12-07' }),
]

const CONNECTIONS: Connection[] = [
  {
    id: 'conn-1',
    provider: 'plaid',

    institution_name: 'Harbor Community Bank',
    created_at: '2026-09-01T10:00:00Z',
    status: 'synced',
    last_synced_at: '2026-10-06T10:02:00Z',
    accounts: [
      {
        id: OPERATING,
        name: 'Operating checking',
        type: 'checking',
        mask: '2381',
        currency: 'CAD',
        balance_cents: 800000,
        available_cents: null,
        included: true,
        primary: true,
      },
      {
        id: 'acc-visa',
        name: 'Business Visa',
        type: 'credit_card',
        mask: '5530',
        currency: 'CAD',
        balance_cents: 100,
        available_cents: null,
        included: false,
        primary: false,
      },
    ],
  },
]

function answer(path: string, payments: Payment[] | null) {
  const body =
    path === '/v1/businesses'
      ? { items: [{ id: BUSINESS, name: 'Harbor Street Plumbing', time_zone: 'America/Toronto' }] }
      : path.endsWith('/expected-payments')
        ? payments && { items: payments }
        : { items: CONNECTIONS }
  const status = body ? 200 : 500
  return { data: body ?? undefined, response: new Response(null, { status }) }
}

function serve(payments: Payment[] | null) {
  vi.mocked(api.GET).mockImplementation(((path: string) => Promise.resolve(answer(path, payments))) as never)
}

async function renderPage(payments: Payment[] | null) {
  serve(payments)
  const tree = await ExpectedPaymentsPage()
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {tree}
    </NextIntlClientProvider>,
  )
}

function cells(row: HTMLElement): string[] {
  return within(row)
    .getAllByRole('cell')
    .map((cell) => cell.textContent ?? '')
}

beforeEach(() => {
  vi.mocked(api.GET).mockReset()
})

describe('expected payments page', () => {
  test('C35 renders the mockup rows', async () => {
    await renderPage(SAMPLE)

    expect(screen.getByRole('heading', { level: 1, name: COPY.title })).toBeTruthy()
    expect(screen.getByText(COPY.intro)).toBeTruthy()
    expect(screen.getAllByRole('button', { name: COPY.add })).toHaveLength(1)
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent)
    expect(headers).toEqual(['Date', 'Description', 'Account', 'Repeats', 'Amount', 'Actions'])
    expect(within(screen.getAllByRole('columnheader')[5]).getByText('Actions').classList.contains('sr-only')).toBe(true)

    const rows = within(screen.getByRole('region', { name: COPY.tableLabel })).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(4)
    expect(cells(rows[0]).slice(0, 5)).toEqual([
      'Tue, Oct 6',
      'Acme Co, invoice 1042',
      'Operating checking',
      "Doesn't repeat",
      '+$8,000',
    ])
    expect(cells(rows[1]).slice(0, 5)).toEqual([
      'Thu, Nov 12',
      'Coastal Supply Co, quarterly order',
      'Operating checking',
      'Every 3 months',
      '−$14,500',
    ])
    expect(cells(rows[2])[1]).toBe('Birch & Co, invoice 1057')
    expect(cells(rows[3])[1]).toBe('Equipment lease deposit')
    for (const p of SAMPLE) {
      expect(screen.getByRole('button', { name: `Edit ${p.description}` })).toBeTruthy()
      expect(screen.getByRole('button', { name: `Delete ${p.description}` })).toBeTruthy()
    }
    expect(within(rows[0]).getByText('+$8,000').classList.contains('text-positive')).toBe(true)
    expect(within(rows[1]).getByText('−$14,500').classList.contains('text-positive')).toBe(false)
  })

  test.each([
    [null, "Doesn't repeat"],
    ['weekly', 'Every week'],
    ['biweekly', 'Every 2 weeks'],
    ['monthly', 'Every month'],
    ['quarterly', 'Every 3 months'],
  ] as const)('C36 repeats text: %s', async (repeats, text) => {
    await renderPage([payment('One', { repeats })])
    const row = screen.getAllByRole('row')[1]
    expect(cells(row)[3]).toBe(text)
  })

  test('C37 overdue and removed account', async () => {
    await renderPage([
      payment('Late', { overdue: true, next_date: '2026-09-01' }),
      payment('On time', { account_id: 'gone' }),
    ])
    const [late, onTime] = screen.getAllByRole('row').slice(1)
    const badge = within(late).getByText(COPY.overdue)
    expect(badge.getAttribute('data-variant')).toBe('warning')
    expect(within(onTime).queryByText(COPY.overdue)).toBeNull()
    expect(cells(late)[2]).toBe('Operating checking')
    expect(cells(onTime)[2]).toBe(COPY.accountRemoved)
  })

  test('C38 empty state', async () => {
    await renderPage([])
    expect(screen.getByRole('heading', { name: COPY.emptyTitle })).toBeTruthy()
    expect(screen.getByText(COPY.emptyBody)).toBeTruthy()
    expect(screen.getAllByRole('button', { name: COPY.add })).toHaveLength(1)
    expect(screen.queryByRole('table')).toBeNull()
  })

  test('C39 error and loading states', async () => {
    await renderPage(null)
    expect(screen.getByText(COPY.loadFailed)).toBeTruthy()
    expect(screen.getByRole('button', { name: messages.States.tryAgain })).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()

    const { container } = render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <Loading />
      </NextIntlClientProvider>,
    )
    expect(within(container).getByRole('status').getAttribute('aria-busy')).toBe('true')
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
  })
})
