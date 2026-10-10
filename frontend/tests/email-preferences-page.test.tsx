import { act, fireEvent, render, screen } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { toast } from 'sonner'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import ErrorState from '@/app/(app)/error'
import { saveEmailPreferences } from '@/app/(app)/settings/email/actions'
import Loading from '@/app/(app)/settings/email/loading'
import EmailSettingsPage from '@/app/(app)/settings/email/page'
import { loadEmailPreferences } from '@/lib/api/email-preferences'
import messages from '@/messages/en.json'

vi.mock('server-only', () => ({}))
vi.mock('@clerk/nextjs/server', () => ({ auth: { protect: vi.fn().mockResolvedValue({}) } }))
vi.mock('@sentry/nextjs', () => ({ captureException: vi.fn(), captureMessage: vi.fn() }))
vi.mock('@/lib/api/email-preferences', () => ({ loadEmailPreferences: vi.fn() }))
vi.mock('@/app/(app)/settings/email/actions', () => ({ saveEmailPreferences: vi.fn() }))
vi.mock('sonner', async (original) => ({ ...(await original<typeof import('sonner')>()), toast: vi.fn() }))

const EMAIL = messages.Settings.Email

function wrap(node: React.ReactNode) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {node}
    </NextIntlClientProvider>,
  )
}

async function renderPage(preferences: { alerts: boolean; weekly_digest: boolean }) {
  vi.mocked(loadEmailPreferences).mockResolvedValue(preferences)
  wrap(await EmailSettingsPage())
}

beforeEach(() => {
  vi.mocked(saveEmailPreferences).mockReset()
  vi.mocked(toast).mockClear()
})

describe('email preferences page', () => {
  test('shows both switches', async () => {
    await renderPage({ alerts: true, weekly_digest: false })

    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe('Email preferences')
    const switches = screen.getAllByRole('switch')
    expect(switches).toHaveLength(2)
    const [alerts, digest] = switches
    expect(alerts.getAttribute('aria-checked')).toBe('true')
    expect(digest.getAttribute('aria-checked')).toBe('false')
    expect(screen.getByRole('switch', { name: 'Cash gap alerts' })).toBe(alerts)
    expect(screen.getByRole('switch', { name: 'Weekly digest' })).toBe(digest)
    const text = document.body.textContent ?? ''
    const order = [
      'Email preferences',
      'Cash gap alerts',
      'Email me when cash is projected to fall below my minimum.',
      'Weekly digest',
      'A summary of my forecast every Monday morning.',
    ].map((part) => text.indexOf(part))
    expect(order.every((at) => at >= 0)).toBe(true)
    expect([...order].sort((a, b) => a - b)).toEqual(order)
  })

  test('saves on flip', async () => {
    vi.mocked(saveEmailPreferences).mockResolvedValue({ ok: true })
    await renderPage({ alerts: true, weekly_digest: false })

    await act(async () => {
      fireEvent.click(screen.getByRole('switch', { name: 'Weekly digest' }))
    })

    expect(saveEmailPreferences).toHaveBeenCalledTimes(1)
    expect(saveEmailPreferences).toHaveBeenCalledWith({ alerts: true, weekly_digest: true })
    expect(toast).toHaveBeenCalledWith(EMAIL.saved)
    expect(toast).toHaveBeenCalledWith('Email preferences saved')
    expect(screen.getByRole('switch', { name: 'Weekly digest' }).getAttribute('aria-checked')).toBe('true')
  })

  test('save fails', async () => {
    vi.mocked(saveEmailPreferences).mockResolvedValue({ ok: false })
    await renderPage({ alerts: true, weekly_digest: false })

    await act(async () => {
      fireEvent.click(screen.getByRole('switch', { name: 'Cash gap alerts' }))
    })

    expect(screen.getByRole('switch', { name: 'Cash gap alerts' }).getAttribute('aria-checked')).toBe('true')
    expect(screen.getByRole('alert').textContent).toBe(
      "We couldn't save your email preferences. Try again.",
    )
    expect(toast).not.toHaveBeenCalled()
  })

  test('error and loading', async () => {
    vi.mocked(loadEmailPreferences).mockResolvedValue(null)

    await expect(EmailSettingsPage()).rejects.toThrow()
    const { unmount } = wrap(<ErrorState error={new Error('x')} retry={() => {}} />)
    expect(screen.getByText("We couldn't load this page")).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy()
    unmount()

    wrap(<Loading />)
    const status = screen.getByRole('status')
    expect(status.getAttribute('aria-busy')).toBe('true')
    expect(status.getAttribute('aria-label')).toBe('Loading')
  })
})
