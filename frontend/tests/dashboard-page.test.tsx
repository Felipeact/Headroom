import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { dismissAlert } from '@/app/(app)/actions'
import { DashboardContent } from '@/components/dashboard/dashboard-content'
import { DashboardSkeleton } from '@/components/dashboard/dashboard-skeleton'
import type { Dashboard } from '@/components/dashboard/types'
import { loadDashboard } from '@/lib/api/dashboard'
import messages from '@/messages/en.json'
import { ALERT, COASTAL, FIXES, IDS, PAYROLL, sampleDashboard } from './fixtures/dashboard-sample'

vi.mock('server-only', () => ({}))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('@/lib/api/dashboard', () => ({ loadDashboard: vi.fn() }))
vi.mock('@/lib/api/businesses', () => ({
  loadBusinesses: vi.fn().mockResolvedValue([
    { id: 'biz-1', name: 'Harbor Street Plumbing', time_zone: 'America/Toronto', role: 'owner' },
  ]),
}))
vi.mock('@/lib/api/bank', () => ({ createUpdateLinkToken: vi.fn().mockResolvedValue('link-update-token') }))
vi.mock('@/app/(app)/actions', () => ({ dismissAlert: vi.fn() }))
vi.mock('@/app/(app)/expected-payments/actions', () => ({
  createExpectedPayment: vi.fn(),
  updateExpectedPayment: vi.fn(),
  deleteExpectedPayment: vi.fn(),
}))
vi.mock('@/app/(app)/settings/banks/actions', () => ({ repairConnection: vi.fn() }))
vi.mock('react-plaid-link', () => ({ usePlaidLink: () => ({ open: vi.fn(), ready: true }) }))
const refresh = vi.hoisted(() => vi.fn())
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), refresh, replace: vi.fn() }),
  usePathname: () => '/',
}))

class NoResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

function setViewport(desktop: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: query.includes('min-width: 1024px') ? desktop : false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia
}

// 12:00 in Toronto on Saturday 2026-09-26, the sample's reference day.
const NOON = new Date('2026-09-26T16:00:00Z')

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(NOON)
  vi.stubGlobal('ResizeObserver', NoResizeObserver)
  setViewport(true)
  refresh.mockClear()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

async function renderPage(dashboard: Dashboard | null) {
  vi.mocked(loadDashboard).mockResolvedValue(dashboard)
  const tree = await DashboardContent()
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {tree}
    </NextIntlClientProvider>,
  )
}

/** The text a viewport shows: `lg:hidden` parts exist only on phones, `max-lg:hidden` from `lg` up. */
function textAt(element: HTMLElement, viewport: 'desktop' | 'phone'): string {
  const copy = element.cloneNode(true) as HTMLElement
  const hidden = viewport === 'desktop' ? '.lg\\:hidden' : '.max-lg\\:hidden'
  copy.querySelectorAll(hidden).forEach((node) => node.remove())
  // Each text node apart, as a reader sees separate lines: "Projected low $3,150 Week of Nov 9".
  const walker = document.createTreeWalker(copy, NodeFilter.SHOW_TEXT)
  const parts: string[] = []
  for (let node = walker.nextNode(); node; node = walker.nextNode()) parts.push(node.textContent ?? '')
  return parts.join(' ').replace(/\s+/g, ' ').replace(/ ([.,])/g, '$1').trim()
}

function card(label: string): HTMLElement {
  return screen.getByRole('region', { name: label })
}

describe('the dashboard with the sample', () => {
  test('chart container', async () => {
    const { container } = await renderPage(sampleDashboard())
    const section = screen.getByRole('region', { name: '13-week forecast' })
    expect(section.querySelector('[data-slot="chart"]')).not.toBeNull()
    expect(within(section).getByText('Projected balance at the end of each week')).toBeTruthy()
    // C21 on the page: the screen-reader summary the chart carries, not only its builder.
    expect(within(section).getByTestId('chart-summary').textContent).toBe(
      'Your cash is projected to go from $42,300 today to $25,160 by the week of Dec 21. ' +
        'The lowest point is $3,150 in the week of Nov 9, $1,850 below your $5,000 minimum.',
    )
    expect(within(section).getByTestId('chart-summary').classList.contains('sr-only')).toBe(true)
    expect(container.querySelectorAll('[data-slot="chart"]')).toHaveLength(1)
  })

  test('header and status line', async () => {
    const { container, unmount } = await renderPage(sampleDashboard())
    expect(screen.getByRole('heading', { level: 1, name: 'Cash flow' })).toBeTruthy()
    const main = container
    expect(textAt(main, 'desktop')).toContain('Saturday, September 26 · Forecast through December 27')
    expect(textAt(main, 'phone')).toContain('Forecast through December 27')
    expect(textAt(main, 'phone')).not.toContain('Saturday, September 26')
    const status = screen.getByTestId('status-line')
    expect(textAt(status, 'desktop')).toBe('Updated today at 6:02 AM · 2 banks synced')
    expect(textAt(status, 'phone')).toBe('Updated 6:02 AM · 2 banks synced')
    unmount()

    vi.setSystemTime(new Date('2026-09-27T16:00:00Z'))
    const yesterday = await renderPage(sampleDashboard())
    expect(textAt(screen.getByTestId('status-line'), 'desktop')).toBe('Updated yesterday at 6:02 AM · 2 banks synced')
    yesterday.unmount()

    vi.setSystemTime(new Date('2026-09-28T16:00:00Z'))
    await renderPage(sampleDashboard())
    expect(textAt(screen.getByTestId('status-line'), 'desktop')).toBe('Updated Sep 26 at 6:02 AM · 2 banks synced')
  })

  test('summary cards', async () => {
    await renderPage(sampleDashboard())
    const cards = screen.getAllByTestId('summary-card')
    expect(cards.map((c) => textAt(c, 'desktop'))).toEqual([
      'Cash on hand $42,300 Operating + Reserve · 2 accounts',
      'Projected low $3,150 Week of Nov 9 · $1,850 below your minimum',
      'Available credit $20,000 Line of credit · not counted as cash',
      'Next card payment $2,450 Business Visa · due Thu, Oct 8',
    ])
    expect(textAt(card('Projected low'), 'phone')).toBe('Projected low $3,150 Week of Nov 9, below your minimum')
    expect(textAt(card('Available credit'), 'phone')).toBe('Available credit $20,000 Line of credit, not counted as cash')
    expect(card('Next card payment').classList.contains('max-lg:hidden')).toBe(true)
  })

  test('summary card variants', async () => {
    const { unmount } = await renderPage(sampleDashboard({ minimum_balance_cents: 300000 }))
    expect(textAt(card('Projected low'), 'desktop')).toBe('Projected low $3,150 Week of Nov 9')
    unmount()
    const second = await renderPage(sampleDashboard({ minimum_balance_cents: null }))
    expect(textAt(card('Projected low'), 'desktop')).toBe('Projected low $3,150 Week of Nov 9')
    second.unmount()
    await renderPage(sampleDashboard({ available_credit_cents: null, next_card_payment: null }))
    expect(screen.queryByRole('region', { name: 'Available credit' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Next card payment' })).toBeNull()
  })

  test('alert card body', async () => {
    const body = (alert: Dashboard['alerts'][number]) => sampleDashboard({ alerts: [alert] })
    const paragraph = () =>
      within(screen.getByTestId('alert-card')).getByText(/taking cash down to/).textContent?.trim()

    let view = await renderPage(sampleDashboard())
    const alert = screen.getByTestId('alert-card')
    expect(within(alert).getByText('Cash gap')).toBeTruthy()
    expect(within(alert).getByRole('heading', { name: 'Cash falls below your $5,000 minimum the week of Nov 9' })).toBeTruthy()
    expect(paragraph()).toBe(
      'Coastal Supply Co ($14,500) and Payroll ($11,200) leave in the same week, taking cash down to $3,150.',
    )
    view.unmount()

    view = await renderPage(body({ ...ALERT, items: [COASTAL] }))
    expect(paragraph()).toBe('Coastal Supply Co ($14,500) leaves that week, taking cash down to $3,150.')
    view.unmount()

    const small = (name: string, cents: number) => ({ ...PAYROLL, counterparty: name, description: name, amount_cents: cents })
    view = await renderPage(body({ ...ALERT, items: [COASTAL, PAYROLL, small('Rent', -300000)] }))
    expect(paragraph()).toBe(
      'Coastal Supply Co ($14,500), Payroll ($11,200) and 1 more payment leave in the same week, taking cash down to $3,150.',
    )
    view.unmount()

    view = await renderPage(body({ ...ALERT, items: [small('Rent', -300000), PAYROLL, small('Tax', -200000), COASTAL] }))
    expect(paragraph()).toBe(
      'Coastal Supply Co ($14,500), Payroll ($11,200) and 2 more payments leave in the same week, taking cash down to $3,150.',
    )
    view.unmount()

    view = await renderPage(body({ ...ALERT, items: [{ ...COASTAL, description: 'Harbor Fuel' }] }))
    expect(paragraph()).toBe('Harbor Fuel ($14,500) leaves that week, taking cash down to $3,150.')
  })

  test('top fix', async () => {
    const topFix = () => screen.getByTestId('top-fix')
    const withFixes = (fixes: Dashboard['alerts'][number]['fixes']) => sampleDashboard({ alerts: [{ ...ALERT, fixes }] })

    let view = await renderPage(sampleDashboard())
    expect(textAt(topFix(), 'desktop')).toBe(
      'Top fix: ask Birch & Co to pay their $9,600 invoice a week early. That keeps you above your minimum.',
    )
    expect(textAt(topFix(), 'phone')).toBe('Top fix: ask Birch & Co to pay their $9,600 invoice a week early.')
    view.unmount()

    const cases: [Dashboard['alerts'][number]['fixes'][number], string][] = [
      [FIXES.move_payment, 'Top fix: move the $14,500 payment to Coastal Supply Co a week later.'],
      [FIXES.draw_credit, 'Top fix: draw $2,000 from your Line of credit.'],
      [FIXES.financing, 'Top fix: arrange $2,000 of short-term financing for the length of the gap.'],
    ]
    for (const [fix, text] of cases) {
      view = await renderPage(withFixes([{ ...fix, new_lowest_balance_cents: 400000 }]))
      expect(textAt(topFix(), 'desktop')).toBe(text)
      view.unmount()
    }

    view = await renderPage(withFixes([{ ...FIXES.pay_early, new_lowest_balance_cents: 400000 }]))
    expect(textAt(topFix(), 'desktop')).not.toContain('That keeps you above your minimum.')
    view.unmount()

    await renderPage(withFixes([]))
    expect(screen.queryByText('Top fix:')).toBeNull()
  })

  test('alert links', async () => {
    const link = () => within(screen.getByTestId('alert-card')).getAllByRole('link')[0]
    let view = await renderPage(sampleDashboard())
    expect(link().textContent).toContain('See all 3 fixes')
    expect(link().getAttribute('href')).toBe(`/alerts/${IDS.alert}`)
    expect(within(screen.getByTestId('alert-card')).getByRole('button', { name: 'Dismiss' })).toBeTruthy()
    view.unmount()
    view = await renderPage(sampleDashboard({ alerts: [{ ...ALERT, fixes: [FIXES.pay_early] }] }))
    expect(link().textContent).toContain('See the fix')
    view.unmount()
    await renderPage(sampleDashboard({ alerts: [{ ...ALERT, fixes: [] }] }))
    expect(link().textContent).toContain('See details')
  })

  test('dismiss fails', async () => {
    vi.mocked(dismissAlert).mockResolvedValue({ error: 'dismissFailed' })
    await renderPage(sampleDashboard())
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    })
    expect(dismissAlert).toHaveBeenCalledWith('biz-1', IDS.alert)
    await waitFor(() => expect(screen.getByText("We couldn't dismiss this alert. Try again.")).toBeTruthy())
    expect(screen.getByTestId('alert-card')).toBeTruthy()
  })

  test('accounts panel', async () => {
    let view = await renderPage(sampleDashboard())
    const panel = screen.getByRole('region', { name: 'Accounts' })
    expect(within(panel).getByRole('link', { name: 'Manage' }).getAttribute('href')).toBe('/settings/banks')
    expect(textAt(panel, 'desktop')).toBe(
      'Accounts Manage Counted as cash Operating checking Primary Harbor Community Bank ••2381 $8,000 ' +
        'Reserve savings Harbor Community Bank ••9025 $34,300 Cash on hand $42,300 ' +
        'Credit · not counted as cash Business Visa Summit Federal ••5530 $2,450 Payment due Oct 8 ' +
        'Line of credit Harbor Community Bank ••7702 $20,000 Available',
    )
    expect(textAt(panel, 'phone')).toContain('Business Visa Summit Federal ••5530 $2,450 Due Oct 8')
    view.unmount()

    const sample = sampleDashboard()
    const extra = { ...sample.accounts[1], id: 'acc-old', name: 'Old savings', included: false }
    const cashOnly = sample.accounts.filter((a) => a.type === 'checking' || a.type === 'savings')
    view = await renderPage({ ...sample, accounts: [...cashOnly, extra], available_credit_cents: null, next_card_payment: null })
    const only = screen.getByRole('region', { name: 'Accounts' })
    expect(only.textContent).not.toContain('Old savings')
    expect(only.textContent).not.toContain('Credit · not counted as cash')
  })

  test('next 14 days', async () => {
    await renderPage(sampleDashboard())
    const table = screen.getByTestId('upcoming-table')
    expect(table.classList.contains('max-lg:hidden')).toBe(true)
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'Date',
      'Description',
      'Account',
      'Type',
      'Amount',
    ])
    const rows = within(table)
      .getAllByRole('row')
      .slice(1)
      .map((row) => within(row).getAllByRole('cell').map((c) => c.textContent).join(' | '))
    expect(rows).toEqual([
      'Fri, Oct 2 | Payroll | Operating checking | Recurring, every 2 weeks | −$11,200',
      'Tue, Oct 6 | Acme Co, invoice 1042 | Operating checking | Expected | +$8,000',
      'Wed, Oct 7 | Software subscriptions | Operating checking | Recurring, monthly | −$640',
      'Thu, Oct 8 | Business Visa payment | Operating checking | Card payment | −$2,450',
    ])
    const list = screen.getByTestId('upcoming-list')
    expect(list.classList.contains('lg:hidden')).toBe(true)
    expect(within(list).getAllByRole('listitem').map((li) => textAt(li, 'phone'))).toEqual([
      'Fri, Oct 2 · Operating checking Payroll Recurring, every 2 weeks −$11,200',
      'Tue, Oct 6 · Operating checking Acme Co, invoice 1042 Expected +$8,000',
      'Wed, Oct 7 · Operating checking Software subscriptions Recurring, monthly −$640',
      'Thu, Oct 8 · Operating checking Business Visa payment Card payment −$2,450',
    ])
  })

  test('upcoming words', async () => {
    const schedules = [
      ['weekly', 'Recurring, every week'],
      ['biweekly', 'Recurring, every 2 weeks'],
      ['semimonthly', 'Recurring, twice a month'],
      ['monthly', 'Recurring, monthly'],
      ['quarterly', 'Recurring, every 3 months'],
    ] as const
    const sample = sampleDashboard()
    const upcoming = schedules.map(([schedule], i) => ({
      ...sample.upcoming[0],
      id: `s${i}`,
      schedule,
      description: i === 0 ? null : `Pattern ${i}`,
      counterparty: 'Wharfside Properties',
    }))
    let view = await renderPage({ ...sample, upcoming })
    const table = screen.getByTestId('upcoming-table')
    const types = within(table)
      .getAllByRole('row')
      .slice(1)
      .map((row) => within(row).getAllByRole('cell')[3].textContent)
    expect(types).toEqual(schedules.map(([, words]) => words))
    expect(within(table).getAllByRole('row')[1].textContent).toContain('Wharfside Properties')
    view.unmount()

    view = await renderPage({ ...sample, upcoming: [] })
    expect(screen.getByRole('region', { name: 'Next 14 days' }).textContent).toContain('Nothing is due in the next 14 days.')
  })
})

describe('the dashboard states', () => {
  test('loading skeleton', () => {
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <DashboardSkeleton />
      </NextIntlClientProvider>,
    )
    const busy = screen.getByLabelText('Loading')
    expect(busy.getAttribute('aria-busy')).toBe('true')
    expect(within(busy).getAllByTestId('skeleton-card')).toHaveLength(4)
    expect(within(busy).getAllByTestId('skeleton-chart')).toHaveLength(1)
    expect(within(busy).getAllByTestId('skeleton-panel')).toHaveLength(2)
  })

  test('empty no bank', async () => {
    await renderPage(sampleDashboard({ connections: [], accounts: [], forecast: null, alerts: [], upcoming: [] }))
    expect(screen.getByRole('heading', { name: 'No bank connected yet' })).toBeTruthy()
    expect(screen.getByText('Connect your bank to see your 13-week forecast.')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Connect your bank' }).getAttribute('href')).toBe('/onboarding/bank')
    expect(screen.queryAllByTestId('summary-card')).toHaveLength(0)
    expect(screen.queryByRole('region', { name: '13-week forecast' })).toBeNull()
  })

  test('forecast not ready', async () => {
    await renderPage(
      sampleDashboard({ forecast: null, projected_low: null, next_card_payment: null, alerts: [], upcoming: [] }),
    )
    expect(textAt(card('Cash on hand'), 'desktop')).toContain('$42,300')
    expect(screen.getByRole('region', { name: 'Accounts' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Your forecast is on its way' })).toBeTruthy()
    expect(screen.getByText("We're reading your bank data. This usually takes a minute or two.")).toBeTruthy()
    expect(screen.getByRole('link', { name: 'See progress' }).getAttribute('href')).toBe('/onboarding/forecast')
    expect(screen.queryByRole('region', { name: 'Projected low' })).toBeNull()
    expect(screen.queryByRole('region', { name: '13-week forecast' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Next 14 days' })).toBeNull()
    expect(screen.queryByTestId('alert-card')).toBeNull()
  })

  test('load fails', async () => {
    await renderPage(null)
    expect(screen.getByRole('heading', { name: "We couldn't load your dashboard." })).toBeTruthy()
    expect(screen.getByText('Check your connection and try again.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  test('partial banners', async () => {
    const sample = sampleDashboard()
    const login = sample.connections.map((c) =>
      c.id === IDS.harbor ? { ...c, status: 'login_required' as const } : c,
    )
    let view = await renderPage({ ...sample, connections: login })
    const banner = screen.getByRole('alert')
    expect(banner.textContent).toContain('Harbor Community Bank')
    expect(within(banner).getByRole('button', { name: 'Reconnect' })).toBeTruthy()
    const order = banner.compareDocumentPosition(screen.getAllByTestId('summary-card')[0])
    expect(order & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByRole('region', { name: '13-week forecast' })).toBeTruthy()
    expect(screen.getByRole('region', { name: 'Accounts' })).toBeTruthy()
    view.unmount()

    const stale = { ...sample, forecast: { ...(sample.forecast as NonNullable<Dashboard['forecast']>), incomplete: true } }
    view = await renderPage(stale)
    expect(screen.getByText('Some bank data is more than 2 days old, so this forecast may be off.')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Go to bank settings' }).getAttribute('href')).toBe('/settings/banks')
    view.unmount()

    await renderPage({ ...stale, connections: login })
    expect(screen.queryByText('Some bank data is more than 2 days old, so this forecast may be off.')).toBeNull()
    expect(screen.getByRole('button', { name: 'Reconnect' })).toBeTruthy()
  })
})

