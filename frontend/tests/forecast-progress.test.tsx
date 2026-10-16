import { act, render, screen, within } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { ForecastProgress, type ForecastStatus } from '@/components/onboarding/forecast-progress'
import messages from '@/messages/en.json'

const refresh = vi.hoisted(() => vi.fn())
const replace = vi.hoisted(() => vi.fn())
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace, refresh }) }))

const FORECAST = messages.Onboarding.Forecast
const SLOW =
  "This is taking longer than usual. You can go to your dashboard; your forecast will appear there when it's ready."
const BUILDING: ForecastStatus = {
  state: 'building',
  institution_names: ['Harbor Community Bank'],
  transactions_read: true,
  history_months: 24,
  recurring_count: 11,
  recurring_names: ['Payroll', 'Rent'],
}

function renderProgress(status: Partial<ForecastStatus> = {}) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ForecastProgress status={{ ...BUILDING, ...status }} />
    </NextIntlClientProvider>,
  )
}

function steps() {
  return within(screen.getByRole('status'))
    .getAllByRole('listitem')
    .map((s) => [s.textContent, s.getAttribute('data-state')])
}

beforeEach(() => {
  refresh.mockClear()
  replace.mockClear()
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('forecast progress', () => {
  test('C30 step texts', () => {
    const { unmount } = renderProgress({ transactions_read: false, recurring_count: 0, recurring_names: [] })
    expect(steps().slice(1, 3)).toEqual([
      ['Reading your transactions', 'active'],
      ['Finding recurring payments', 'pending'],
    ])
    unmount()

    const cases: [Partial<ForecastStatus>, number, string][] = [
      [{ history_months: null }, 1, 'Read your transactions'],
      [{ history_months: 1 }, 1, 'Read 1 month of transactions'],
      [{ recurring_count: 0, recurring_names: [] }, 2, 'Finding recurring payments'],
      [{ recurring_count: 1, recurring_names: ['Payroll'] }, 2, 'Finding recurring paymentsPayroll so far'],
      [{ recurring_count: 2 }, 2, 'Finding recurring paymentsPayroll and Rent so far'],
      [{ recurring_count: 3 }, 2, 'Finding recurring paymentsPayroll, Rent, and 1 other so far'],
      [{ institution_names: ['Bank A', 'Bank B'] }, 0, 'Connected Bank A and Bank B'],
    ]
    for (const [status, index, text] of cases) {
      const view = renderProgress(status)
      expect(steps()[index][0]).toBe(text)
      view.unmount()
    }
  })

  test('C31 polls', () => {
    const { unmount } = renderProgress()
    act(() => vi.advanceTimersByTime(2999))
    expect(refresh).toHaveBeenCalledTimes(0)
    act(() => vi.advanceTimersByTime(1))
    expect(refresh).toHaveBeenCalledTimes(1)
    act(() => vi.advanceTimersByTime(3000))
    expect(refresh).toHaveBeenCalledTimes(2)

    act(() => vi.advanceTimersByTime(179_999 - 6000))
    expect(screen.queryByText(/taking longer than usual/)).toBeNull()
    act(() => vi.advanceTimersByTime(1))
    const slow = screen.getByText(/taking longer than usual/)
    expect(slow.textContent).toBe(SLOW)
    expect(within(slow).getByRole('link', { name: 'dashboard' }).getAttribute('href')).toBe('/')
    const before = refresh.mock.calls.length
    act(() => vi.advanceTimersByTime(3000))
    expect(refresh.mock.calls.length).toBe(before + 1)

    unmount()
    act(() => vi.advanceTimersByTime(9000))
    expect(refresh.mock.calls.length).toBe(before + 1)
  })

  test('C32 needs attention', () => {
    renderProgress({ state: 'needs_attention' })
    expect(screen.getByText(FORECAST.needsAttention)).toBeDefined()
    expect(screen.getByRole('link', { name: FORECAST.fixBank }).getAttribute('href')).toBe('/settings/banks')
    act(() => vi.advanceTimersByTime(9000))
    expect(refresh).not.toHaveBeenCalled()
  })

  test('C32 ready: every step done, then the dashboard after 2 s', () => {
    renderProgress({ state: 'ready' })
    expect(steps().map(([, state]) => state)).toEqual(['done', 'done', 'done', 'done'])
    act(() => vi.advanceTimersByTime(1999))
    expect(replace).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(1))
    expect(replace).toHaveBeenCalledWith('/')
    act(() => vi.advanceTimersByTime(9000))
    expect(refresh).not.toHaveBeenCalled()
  })
})
