import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { notFound } from 'next/navigation'
import { toast } from 'sonner'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { dismissAlert, type DismissResult } from '@/app/(app)/actions'
import AlertPage from '@/app/(app)/alerts/[alertId]/page'
import { loadAlert, type Alert } from '@/lib/api/alerts'
import { loadBusinesses } from '@/lib/api/businesses'
import { formatDate, formatMoney, formatSignedMoney } from '@/lib/format'
import messages from '@/messages/en.json'
import { ALERT, COASTAL, FIXES, PAYROLL } from './fixtures/dashboard-sample'

// Spec 27: the alert page, rendered from the real route with its loaders mocked.

vi.mock('server-only', () => ({}))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))
vi.mock('@/lib/api/alerts', () => ({ loadAlert: vi.fn() }))
vi.mock('@/lib/api/businesses', () => ({ loadBusinesses: vi.fn() }))
vi.mock('@/app/(app)/actions', () => ({ dismissAlert: vi.fn() }))
vi.mock('sonner', () => ({ toast: vi.fn() }))
const push = vi.hoisted(() => vi.fn())
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, refresh: vi.fn(), replace: vi.fn() }),
  usePathname: () => '/alerts/x',
  notFound: vi.fn(() => {
    throw new Error('NEXT_NOT_FOUND')
  }),
}))

const BUSINESS = { id: 'biz-1', name: 'Harbor Street Plumbing', time_zone: 'America/Toronto', role: 'owner' }
const BIRCH = ALERT.items.find((i) => i.kind === 'arrives_after')!

const alertWith = (overrides: Partial<Alert>): Alert => ({ ...(ALERT as Alert), ...overrides })

beforeEach(() => {
  vi.mocked(loadBusinesses).mockResolvedValue([BUSINESS] as Awaited<ReturnType<typeof loadBusinesses>>)
  vi.mocked(dismissAlert).mockReset()
  vi.mocked(toast).mockClear()
  vi.mocked(notFound).mockClear()
  push.mockClear()
})

async function renderPage(alert: Alert, intl: typeof messages = messages) {
  vi.mocked(loadAlert).mockResolvedValue(alert)
  const tree = await AlertPage({ params: Promise.resolve({ alertId: alert.id }), searchParams: Promise.resolve({}) })
  return render(
    <NextIntlClientProvider locale="en" messages={intl}>
      {tree}
    </NextIntlClientProvider>,
  )
}

/** Each text node apart, joined as a reader sees the lines. */
function text(element: HTMLElement): string {
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT)
  const parts: string[] = []
  for (let node = walker.nextNode(); node; node = walker.nextNode()) parts.push(node.textContent ?? '')
  return parts.join(' ').replace(/\s+/g, ' ').trim()
}

function fixCards(): HTMLElement[] {
  return screen.queryAllByTestId('fix-card')
}

describe('the alert in full', () => {
  test('C1 header', async () => {
    await renderPage(ALERT as Alert)
    const back = screen.getByRole('link', { name: 'Dashboard' })
    expect(back.getAttribute('href')).toBe('/')
    expect(screen.getByText('Cash gap')).toBeTruthy()
    const headings = screen.getAllByRole('heading', { level: 1 })
    expect(headings).toHaveLength(1)
    expect(headings[0].textContent).toBe('Cash falls below your $5,000 minimum the week of Nov 9')
  })

  test('C2 summary cards', async () => {
    await renderPage(ALERT as Alert)
    const low = screen.getByTestId('projected-low')
    const short = screen.getByTestId('short-by')
    expect(text(low)).toBe('Projected low $3,150 Week of Nov 9')
    expect(text(short)).toBe('Short by $1,850 Below your minimum')
    expect(low.classList.contains('bg-warning-bg')).toBe(true)
    expect(short.classList.contains('bg-warning-bg')).toBe(false)
  })

  test('C3 causes largest first', async () => {
    await renderPage(alertWith({ items: [PAYROLL, COASTAL, BIRCH] }))
    const section = screen.getByRole('region', { name: "What's causing it" })
    expect(within(section).getAllByTestId('cause-row').map(text)).toEqual([
      'Coastal Supply Co Thu, Nov 12 · Expected payment −$14,500',
      'Payroll Fri, Nov 13 · Every 2 weeks −$11,200',
    ])
  })

  test('C4 arrives after', async () => {
    const { unmount } = await renderPage(ALERT as Alert)
    const section = screen.getByRole('region', { name: "What's causing it" })
    const rows = within(section).getAllByTestId(/^(cause|arrives)-row$/)
    expect(rows.map((r) => r.dataset.testid)).toEqual(['cause-row', 'cause-row', 'arrives-row'])
    expect(text(section)).toContain('Arrives after the gap')
    const arrives = within(section).getByTestId('arrives-row')
    expect(text(arrives)).toBe('Birch & Co, invoice 1057 Tue, Nov 17 · Expected payment +$9,600')
    expect(within(arrives).getByText('+$9,600').classList.contains('text-positive')).toBe(true)
    unmount()

    const none = await renderPage(alertWith({ items: [COASTAL, PAYROLL] }))
    expect(screen.queryByText('Arrives after the gap')).toBeNull()
    none.unmount()

    await renderPage(alertWith({ items: [COASTAL, PAYROLL, { ...BIRCH, description: null, counterparty: 'Birch & Co Ltd' }] }))
    expect(text(screen.getByTestId('arrives-row'))).toBe('Birch & Co Ltd Tue, Nov 17 · Expected payment +$9,600')
  })

  test('C5 row types', async () => {
    const cases: [Partial<typeof COASTAL>, string][] = [
      [{ source: 'expected_payment', schedule: null }, 'Expected payment'],
      [{ source: 'card_payment', schedule: null }, 'Card payment'],
      [{ source: 'recurring_pattern', schedule: 'weekly' }, 'Every week'],
      [{ source: 'recurring_pattern', schedule: 'biweekly' }, 'Every 2 weeks'],
      [{ source: 'recurring_pattern', schedule: 'semimonthly' }, 'Twice a month'],
      [{ source: 'recurring_pattern', schedule: 'monthly' }, 'Every month'],
      [{ source: 'recurring_pattern', schedule: 'quarterly' }, 'Every 3 months'],
      [{ source: 'recurring_pattern', schedule: null }, 'Recurring'],
    ]
    expect(cases).toHaveLength(8)
    for (const [overrides, expected] of cases) {
      const { unmount } = await renderPage(alertWith({ items: [{ ...COASTAL, ...overrides }] }))
      expect(text(screen.getByTestId('cause-row'))).toBe(`Coastal Supply Co Thu, Nov 12 · ${expected} −$14,500`)
      unmount()
    }
  })

  test('C6 fix cards', async () => {
    await renderPage(ALERT as Alert)
    const section = screen.getByRole('region', { name: 'Ways to fix it' })
    const cards = within(section).getAllByTestId('fix-card')
    expect(cards).toHaveLength(3)
    expect(cards.map((c) => c.dataset.kind)).toEqual(['pay_early', 'move_payment', 'draw_credit'])
    expect(cards.map((c) => text(within(c).getByTestId('fix-result')))).toEqual([
      'New lowest balance $12,750',
      'New lowest balance $17,650',
      'New lowest balance $5,150',
    ])
  })

  test('C7 pay early', async () => {
    await renderPage(ALERT as Alert)
    const card = fixCards()[0]
    expect(within(card).getByRole('heading').textContent).toBe('Ask Birch & Co to pay a week early')
    expect(within(card).getByText(/^Their/).textContent).toBe(
      'Their $9,600 invoice is due Nov 17. Ask them to pay by Nov 10. A small early-payment discount can help.',
    )
  })

  test('C8 move payment', async () => {
    await renderPage(ALERT as Alert)
    const card = fixCards()[1]
    expect(within(card).getByRole('heading').textContent).toBe('Move the Coastal Supply Co payment by a week')
    expect(within(card).getByText(/^Ask/).textContent).toBe('Ask Coastal Supply Co to move the $14,500 payment to Nov 19.')
  })

  test('C9 draw credit', async () => {
    const { unmount } = await renderPage(ALERT as Alert)
    let card = fixCards()[2]
    expect(within(card).getByRole('heading').textContent).toBe('Draw $2,000 on your line of credit')
    expect(within(card).getByText(/^You have/).textContent).toBe('You have $20,000 available. Repay it when Birch & Co pays.')
    unmount()

    await renderPage(alertWith({ items: [COASTAL, PAYROLL], fixes: [FIXES.draw_credit] }))
    card = fixCards()[0]
    expect(within(card).getByText(/^You have/).textContent).toBe('You have $20,000 available. Repay it on Nov 17.')
  })

  test('C10 financing', async () => {
    await renderPage(alertWith({ fixes: [FIXES.financing] }))
    const cards = fixCards()
    expect(cards).toHaveLength(1)
    expect(within(cards[0]).getByRole('heading').textContent).toBe('Arrange $2,000 of short-term financing')
    expect(within(cards[0]).getByText(/^Borrow/).textContent).toBe(
      'Borrow it on Nov 9 and repay it on Nov 16, after the gap.',
    )
  })

  test('C11 counterparty first', async () => {
    await renderPage(alertWith({ fixes: [{ ...FIXES.pay_early, counterparty: 'Birch and Company Ltd' }] }))
    expect(within(fixCards()[0]).getByRole('heading').textContent).toBe('Ask Birch and Company Ltd to pay a week early')
  })

  test('C12 new lowest style', async () => {
    const at = (cents: number) => ({ ...FIXES.draw_credit, new_lowest_balance_cents: cents })
    await renderPage(alertWith({ minimum_cents: 500000, fixes: [at(515000), at(500000), at(499999)] }))
    const results = fixCards().map((c) => within(c).getByTestId('fix-result'))
    for (const ok of results.slice(0, 2)) {
      expect(ok.classList.contains('bg-positive-bg')).toBe(true)
      expect(within(ok).queryByTestId('fix-ok')).not.toBeNull()
    }
    expect(results[2].classList.contains('bg-warning-bg')).toBe(true)
    expect(results[2].classList.contains('bg-positive-bg')).toBe(false)
    expect(within(results[2]).queryByTestId('fix-ok')).toBeNull()
  })

  test('C13 text from messages', async () => {
    const keyed = (node: unknown, path: string): unknown =>
      typeof node === 'string'
        ? `[[${path}]]`
        : Object.fromEntries(Object.entries(node as object).map(([k, v]) => [k, keyed(v, path ? `${path}.${k}` : k)]))
    const { container } = await renderPage(ALERT as Alert, keyed(messages, '') as typeof messages)

    const alert = ALERT as Alert
    const dates = [...alert.items, ...alert.fixes].flatMap((x) => [
      x.date,
      ...('original_date' in x ? [x.original_date, x.repay_on] : []),
    ])
    const allowed = new Set<string>([
      ...alert.items.flatMap((i) => [i.description ?? '', i.counterparty ?? '', 'Coastal Supply Co', 'Payroll']),
      ...[...dates, alert.lowest_week_starts_on]
        .filter((d): d is string => !!d)
        .flatMap((d) => [formatDate(d), formatDate(d, 'weekday')]),
      ...[
        ...alert.items.map((i) => i.amount_cents),
        ...alert.fixes.map((f) => f.new_lowest_balance_cents),
        alert.lowest_balance_cents,
        alert.shortfall_cents,
      ].flatMap((c) => [formatMoney(c), formatMoney(Math.abs(c)), formatSignedMoney(c)]),
    ])
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
    const stray: string[] = []
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const value = (node.textContent ?? '').trim()
      if (value && !value.includes('[[') && !allowed.has(value)) stray.push(value)
    }
    expect(stray).toEqual([])
  })

  test('C14 no fixes', async () => {
    await renderPage(alertWith({ fixes: [] }))
    expect(screen.queryByRole('heading', { name: 'Ways to fix it' })).toBeNull()
    expect(screen.queryByText('New lowest balance')).toBeNull()
    expect(screen.getAllByTestId('cause-row')).toHaveLength(2)
  })
})

describe('dismiss', () => {
  test('C16 dismiss shown', async () => {
    const { container } = await renderPage(ALERT as Alert)
    const button = screen.getByRole('button', { name: 'Dismiss alert' })
    const note = screen.getByText('This alert closes on its own when the gap leaves your forecast.')
    expect(button.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(container.contains(note)).toBe(true)
  })

  test('C17 dismiss pending', async () => {
    let finish: (value: DismissResult) => void = () => {}
    vi.mocked(dismissAlert).mockReturnValue(new Promise((resolve) => (finish = resolve)))
    await renderPage(ALERT as Alert)
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss alert' }))
    const pending = await screen.findByRole('button', { name: 'Dismissing…' })
    expect((pending as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(pending)
    expect(dismissAlert).toHaveBeenCalledTimes(1)
    expect(dismissAlert).toHaveBeenCalledWith('biz-1', ALERT.id)
    await act(async () => finish({ error: null }))
  })

  test('C18 dismiss success', async () => {
    vi.mocked(dismissAlert).mockResolvedValue({ error: null })
    await renderPage(ALERT as Alert)
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Dismiss alert' })))
    expect(push).toHaveBeenCalledTimes(1)
    expect(push).toHaveBeenCalledWith('/')
    expect(toast).toHaveBeenCalledWith('Alert dismissed')
  })

  test('C19 dismiss fails', async () => {
    vi.mocked(dismissAlert).mockResolvedValue({ error: 'dismissFailed' })
    await renderPage(ALERT as Alert)
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Dismiss alert' })))
    expect(push).not.toHaveBeenCalled()
    const button = screen.getByRole('button', { name: 'Dismiss alert' }) as HTMLButtonElement
    expect(button.disabled).toBe(false)
    expect(screen.getByRole('alert').textContent).toBe("We couldn't dismiss this alert. Try again.")
  })
})

describe('the other states', () => {
  test('C21 dismissed', async () => {
    await renderPage(alertWith({ state: 'dismissed', dismissed_at: '2026-10-02T02:00:00Z' }))
    expect(screen.getByText('You dismissed this alert on Oct 1. It comes back if the gap gets worse.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Dismiss alert' })).toBeNull()
  })

  test('C22 resolved', async () => {
    await renderPage(alertWith({ state: 'resolved', resolved_at: '2026-10-02T02:00:00Z' }))
    expect(screen.getByText('This gap is no longer in your forecast.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Dismiss alert' })).toBeNull()
  })

  test('C24 load outcomes', async () => {
    const props = { params: Promise.resolve({ alertId: ALERT.id }), searchParams: Promise.resolve({}) }
    vi.mocked(loadAlert).mockResolvedValue('not_found')
    await expect(AlertPage(props)).rejects.toThrow('NEXT_NOT_FOUND')
    expect(notFound).toHaveBeenCalledTimes(1)

    vi.mocked(loadAlert).mockResolvedValue(null)
    await expect(AlertPage(props)).rejects.toThrow()

    vi.mocked(loadAlert).mockResolvedValue(ALERT as Alert)
    for (const businesses of [null, []]) {
      vi.mocked(loadBusinesses).mockResolvedValue(businesses)
      await expect(AlertPage(props)).rejects.toThrow()
    }
    expect(notFound).toHaveBeenCalledTimes(1)
  })
})
