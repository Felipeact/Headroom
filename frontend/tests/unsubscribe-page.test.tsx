import { act, fireEvent, render, screen } from '@testing-library/react'
import { NextIntlClientProvider, createTranslator } from 'next-intl'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { type UnsubscribeResult, unsubscribe } from '@/app/unsubscribe/[token]/actions'
import UnsubscribePage from '@/app/unsubscribe/[token]/page'
import { api } from '@/lib/api/client'
import messages from '@/messages/en.json'

vi.mock('server-only', () => ({}))
vi.mock('@/lib/api/client', () => ({ api: { GET: vi.fn(), POST: vi.fn() } }))
vi.mock('@/app/unsubscribe/[token]/actions', () => ({ unsubscribe: vi.fn() }))
vi.mock('next-intl/server', () => ({
  getTranslations: async (namespace: 'Shell') => createTranslator({ locale: 'en', messages, namespace }),
}))

const TOKEN = 'tok_' + 'a'.repeat(39)

async function renderPage() {
  const page = await UnsubscribePage({ params: Promise.resolve({ token: TOKEN }) } as never)
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {page}
    </NextIntlClientProvider>,
  )
}

function deferred() {
  let resolve: (value: UnsubscribeResult) => void = () => {}
  const promise = new Promise<UnsubscribeResult>((r) => {
    resolve = r
  })
  return { promise, resolve }
}

beforeEach(() => {
  vi.mocked(unsubscribe).mockReset()
  vi.mocked(api.GET).mockReset()
  vi.mocked(api.POST).mockReset()
})

describe('unsubscribe page', () => {
  test('asks before unsubscribing', async () => {
    await renderPage()

    expect(screen.getByText('Headroom')).toBeTruthy()
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Unsubscribe from Headroom emails?')
    expect(screen.getByText("You'll stop getting cash gap alerts and the weekly digest.")).toBeTruthy()
    const button = screen.getByRole('button', { name: 'Unsubscribe' })
    expect(button.getAttribute('data-variant')).toBe('primary')
    expect(unsubscribe).not.toHaveBeenCalled()
    expect(api.GET).not.toHaveBeenCalled()
    expect(api.POST).not.toHaveBeenCalled()
  })

  test('outcomes: pending, then unsubscribed', async () => {
    const answer = deferred()
    vi.mocked(unsubscribe).mockReturnValue(answer.promise)
    await renderPage()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Unsubscribe' }))
    })

    expect(unsubscribe).toHaveBeenCalledTimes(1)
    expect(unsubscribe).toHaveBeenCalledWith(TOKEN)
    const pending = screen.getByRole('button', { name: 'Unsubscribing…' }) as HTMLButtonElement
    expect(pending.disabled).toBe(true)

    await act(async () => {
      answer.resolve({ status: 'unsubscribed' })
    })

    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe("You're unsubscribed")
    expect(document.body.textContent).toContain(
      "You won't get any more emails from Headroom. To turn them back on, go to Email preferences.",
    )
    expect(screen.getByRole('link', { name: 'Email preferences' }).getAttribute('href')).toBe('/settings/email')
  })

  test('outcomes: invalid link', async () => {
    vi.mocked(unsubscribe).mockResolvedValue({ status: 'invalid' })
    await renderPage()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Unsubscribe' }))
    })

    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe("This unsubscribe link isn't valid")
    expect(document.body.textContent).toContain('To change your emails, go to Email preferences.')
    expect(screen.getByRole('link', { name: 'Email preferences' }).getAttribute('href')).toBe('/settings/email')
  })

  test('outcomes: error', async () => {
    vi.mocked(unsubscribe).mockResolvedValue({ status: 'error' })
    await renderPage()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Unsubscribe' }))
    })

    expect(screen.getByRole('alert').textContent).toBe("We couldn't unsubscribe you. Try again.")
    const button = screen.getByRole('button', { name: 'Unsubscribe' }) as HTMLButtonElement
    expect(button.disabled).toBe(false)
  })
})
