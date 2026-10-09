import { act, fireEvent, render, screen } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { saveMinimumBalance } from '@/app/onboarding/minimum-balance/actions'
import { MinimumBalanceForm } from '@/components/onboarding/minimum-balance-form'
import messages from '@/messages/en.json'

vi.mock('@/app/onboarding/minimum-balance/actions', () => ({ saveMinimumBalance: vi.fn() }))
const push = vi.hoisted(() => vi.fn())
vi.mock('next/navigation', () => ({ useRouter: () => ({ push, refresh: vi.fn() }) }))

const MINIMUM = messages.Onboarding.Minimum
const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const INVALID = 'Enter a whole-dollar amount from $0 to $10,000,000.'

function renderForm(initialCents: number | null = 500000, suggestedCents: number | null = 500000) {
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <MinimumBalanceForm businessId={BUSINESS} initialCents={initialCents} suggestedCents={suggestedCents} />
    </NextIntlClientProvider>,
  )
}

const input = () => screen.getByRole('textbox', { name: MINIMUM.label }) as HTMLInputElement
const type = (text: string) => fireEvent.change(input(), { target: { value: text } })
const submit = () => act(async () => fireEvent.click(screen.getByRole('button', { name: MINIMUM.continue })))

beforeEach(() => {
  vi.mocked(saveMinimumBalance).mockReset()
  push.mockClear()
})

describe('minimum balance form', () => {
  test('C23 card follows input', () => {
    renderForm()
    type('7,500')
    expect(screen.getByText(/If your forecast dips below \$7,500,/)).toBeDefined()
    type('abc')
    expect(screen.getByText(/If your forecast dips below \$7,500,/)).toBeDefined()
  })

  test.each(['', '5000.50', '10,000,001'])('C24 invalid input %j', async (text) => {
    renderForm()
    type(text)
    await submit()

    const error = screen.getByText(INVALID)
    expect(input().getAttribute('aria-invalid')).toBe('true')
    const describedBy = input().getAttribute('aria-describedby') ?? ''
    expect(describedBy.split(' ')).toContain(error.closest('[id]')?.id)
    expect(saveMinimumBalance).not.toHaveBeenCalled()
    expect(push).not.toHaveBeenCalled()
  })

  test('C25 saves and moves on', async () => {
    vi.mocked(saveMinimumBalance).mockResolvedValue({ error: null })
    renderForm()
    type('7,500')
    await submit()

    expect(saveMinimumBalance).toHaveBeenCalledWith(BUSINESS, 750000)
    expect(push).toHaveBeenCalledWith('/onboarding/forecast')
  })

  test('C33 Enter in the input submits', async () => {
    vi.mocked(saveMinimumBalance).mockResolvedValue({ error: null })
    renderForm()
    await act(async () => fireEvent.submit(input().form!))
    expect(saveMinimumBalance).toHaveBeenCalledWith(BUSINESS, 500000)
  })

  test('C26 save fails', async () => {
    vi.mocked(saveMinimumBalance).mockResolvedValue({ error: 'saveFailed' })
    renderForm()
    type('7,500')
    await submit()

    expect(screen.getByRole('alert').textContent).toContain(MINIMUM.errors.saveFailed)
    expect(input().value).toBe('7,500')
    expect(push).not.toHaveBeenCalled()
  })
})
