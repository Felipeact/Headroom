import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { toast } from 'sonner'
import { afterEach, beforeAll, beforeEach, describe, expect, test, vi } from 'vitest'
import {
  createExpectedPayment,
  deleteExpectedPayment,
  updateExpectedPayment,
} from '@/app/(app)/expected-payments/actions'
import { ExpectedPayments } from '@/components/expected-payments/expected-payments'
import type { AccountOption, ExpectedPayment } from '@/components/expected-payments/types'
import messages from '@/messages/en.json'

vi.mock('@/app/(app)/expected-payments/actions', () => ({
  createExpectedPayment: vi.fn(),
  updateExpectedPayment: vi.fn(),
  deleteExpectedPayment: vi.fn(),
}))
vi.mock('sonner', async (original) => ({ ...(await original<typeof import('sonner')>()), toast: vi.fn() }))

const COPY = messages.ExpectedPayments
const DIALOG = COPY.dialog
const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const OPERATING = '6f1c2b0e-0000-4000-8000-0000000000a1'
const RESERVE = '6f1c2b0e-0000-4000-8000-0000000000a2'
const ACCOUNTS: AccountOption[] = [
  { id: RESERVE, name: 'Reserve savings', primary: false },
  { id: OPERATING, name: 'Operating checking', primary: true },
]
const ACME: ExpectedPayment = {
  id: 'id-acme',
  account_id: OPERATING,
  description: 'Acme Co, invoice 1042',
  amount_cents: 800000,
  currency: 'CAD',
  date: '2026-10-06',
  repeats: null,
  next_date: '2026-10-06',
  overdue: false,
}

// Radix Select measures and captures pointers; jsdom implements neither.
beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false
  Element.prototype.releasePointerCapture ??= () => {}
  Element.prototype.scrollIntoView ??= () => {}
})

beforeEach(() => {
  vi.mocked(createExpectedPayment).mockReset().mockResolvedValue({ ok: true })
  vi.mocked(updateExpectedPayment).mockReset().mockResolvedValue({ ok: true })
  vi.mocked(deleteExpectedPayment).mockReset().mockResolvedValue({ ok: true })
  vi.mocked(toast).mockClear()
})

afterEach(() => {
  vi.clearAllMocks()
})

function renderPage(payments: ExpectedPayment[] = [ACME]) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ExpectedPayments businessId={BUSINESS} payments={payments} accounts={ACCOUNTS} />
    </NextIntlClientProvider>,
  )
}

const dialog = () => screen.getByRole('dialog')
const field = (label: string) => within(dialog()).getByLabelText(label) as HTMLInputElement
const combobox = (label: string) => within(dialog()).getByRole('combobox', { name: label })

function options(trigger: HTMLElement): string[] {
  fireEvent.keyDown(trigger, { key: 'Enter' })
  const names = within(screen.getByRole('listbox'))
    .getAllByRole('option')
    .map((option) => option.textContent ?? '')
  fireEvent.keyDown(screen.getByRole('listbox'), { key: 'Escape' })
  return names
}

function choose(trigger: HTMLElement, name: string) {
  fireEvent.keyDown(trigger, { key: 'Enter' })
  fireEvent.keyDown(screen.getByRole('option', { name }), { key: 'Enter' })
}

function type(label: string, value: string) {
  fireEvent.change(field(label), { target: { value } })
}

async function submit(name: string) {
  await act(async () => {
    fireEvent.click(within(dialog()).getByRole('button', { name }))
  })
}

function openAdd() {
  fireEvent.click(screen.getByRole('button', { name: COPY.add }))
}

function errorFor(input: HTMLElement): string | null {
  const id = input.getAttribute('aria-describedby')
  return id ? (document.getElementById(id)?.textContent ?? null) : null
}

describe('expected payment dialogs', () => {
  test('C40 add dialog', async () => {
    renderPage()
    openAdd()

    expect(within(dialog()).getByRole('heading', { name: DIALOG.addTitle })).toBeTruthy()
    const out = within(dialog()).getByRole('radio', { name: DIALOG.moneyOut })
    const into = within(dialog()).getByRole('radio', { name: DIALOG.moneyIn })
    expect(out.getAttribute('aria-checked')).toBe('true')
    expect(into.getAttribute('aria-checked')).toBe('false')
    expect(field(DIALOG.amount).getAttribute('inputmode')).toBe('decimal')
    expect(field(DIALOG.date).getAttribute('type')).toBe('date')
    expect(combobox(DIALOG.account).textContent).toBe('Operating checking')
    expect(options(combobox(DIALOG.account))).toEqual(['Reserve savings', 'Operating checking'])
    expect(combobox(DIALOG.repeats).textContent).toBe(COPY.repeats.once)

    // DOM order: direction, amount, date, description, account, repeats, then the buttons.
    const order = [
      out,
      field(DIALOG.amount),
      field(DIALOG.date),
      field(DIALOG.descriptionLabel),
      combobox(DIALOG.account),
      combobox(DIALOG.repeats),
      within(dialog()).getByRole('button', { name: DIALOG.cancel }),
      within(dialog()).getByRole('button', { name: DIALOG.add }),
    ]
    for (let i = 1; i < order.length; i++) {
      expect(order[i - 1].compareDocumentPosition(order[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    }

    type(DIALOG.amount, '2,300.50')
    fireEvent.click(into)
    type(DIALOG.date, '2026-11-20')
    type(DIALOG.descriptionLabel, 'Van repair deposit')
    choose(combobox(DIALOG.repeats), COPY.repeats.monthly)
    await submit(DIALOG.add)

    expect(createExpectedPayment).toHaveBeenCalledWith(BUSINESS, {
      account_id: OPERATING,
      description: 'Van repair deposit',
      amount_cents: 230050,
      date: '2026-11-20',
      repeats: 'monthly',
    })
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(toast).toHaveBeenCalledWith(COPY.toasts.added)
  })

  test('C40 add dialog: money out is negative', async () => {
    renderPage()
    openAdd()
    type(DIALOG.amount, '2,300.50')
    type(DIALOG.date, '2026-11-20')
    type(DIALOG.descriptionLabel, 'Van repair deposit')
    await submit(DIALOG.add)

    expect(vi.mocked(createExpectedPayment).mock.calls[0][1]).toMatchObject({
      amount_cents: -230050,
      repeats: null,
    })
  })

  test('C41 edit dialog', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: `Edit ${ACME.description}` }))

    expect(within(dialog()).getByRole('heading', { name: DIALOG.editTitle })).toBeTruthy()
    expect(within(dialog()).getByRole('radio', { name: DIALOG.moneyIn }).getAttribute('aria-checked')).toBe('true')
    expect(field(DIALOG.amount).value).toBe('8,000.00')
    expect(field(DIALOG.date).value).toBe('2026-10-06')
    expect(field(DIALOG.descriptionLabel).value).toBe(ACME.description)
    expect(combobox(DIALOG.account).textContent).toBe('Operating checking')
    expect(combobox(DIALOG.repeats).textContent).toBe(COPY.repeats.once)

    await submit(DIALOG.save)

    expect(updateExpectedPayment).toHaveBeenCalledWith(BUSINESS, ACME.id, {
      account_id: OPERATING,
      description: ACME.description,
      amount_cents: 800000,
      date: '2026-10-06',
      repeats: null,
    })
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(toast).toHaveBeenCalledWith(COPY.toasts.updated)
  })

  test('C42 delete confirmation', async () => {
    renderPage()
    const trigger = () => screen.getByRole('button', { name: `Delete ${ACME.description}` })

    fireEvent.click(trigger())
    expect(within(dialog()).getByRole('heading', { name: `Delete ${ACME.description}?` })).toBeTruthy()
    fireEvent.click(within(dialog()).getByRole('button', { name: COPY.deleteDialog.cancel }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(deleteExpectedPayment).not.toHaveBeenCalled()

    fireEvent.click(trigger())
    const confirm = within(dialog()).getByRole('button', { name: COPY.deleteDialog.confirm })
    expect(confirm.getAttribute('data-variant')).toBe('destructive')
    await act(async () => {
      fireEvent.click(confirm)
    })
    expect(deleteExpectedPayment).toHaveBeenCalledWith(BUSINESS, ACME.id)
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(toast).toHaveBeenCalledWith(COPY.toasts.deleted)
  })

  test.each([
    ['', DIALOG.errors.amountRequired],
    ['0', DIALOG.errors.amountZero],
    ['abc', DIALOG.errors.amountInvalid],
    ['1.234', DIALOG.errors.amountInvalid],
    ['100000000', DIALOG.errors.amountTooLarge],
  ])('C43 validation: amount %j', async (amount, message) => {
    renderPage()
    openAdd()
    type(DIALOG.amount, amount)
    type(DIALOG.date, '2026-11-20')
    type(DIALOG.descriptionLabel, 'Deposit')
    await submit(DIALOG.add)

    expect(errorFor(field(DIALOG.amount))).toBe(message)
    expect(field(DIALOG.amount).getAttribute('aria-invalid')).toBe('true')
    expect(createExpectedPayment).not.toHaveBeenCalled()
  })

  test('C43 validation: blank description', async () => {
    renderPage()
    openAdd()
    type(DIALOG.amount, '100')
    type(DIALOG.date, '2026-11-20')
    type(DIALOG.descriptionLabel, '   ')
    await submit(DIALOG.add)

    expect(errorFor(field(DIALOG.descriptionLabel))).toBe(DIALOG.errors.descriptionRequired)
    expect(createExpectedPayment).not.toHaveBeenCalled()
  })

  test('C43 validation: the largest amount is accepted', async () => {
    renderPage()
    openAdd()
    fireEvent.click(within(dialog()).getByRole('radio', { name: DIALOG.moneyIn }))
    type(DIALOG.amount, '99,999,999.99')
    type(DIALOG.date, '2026-11-20')
    type(DIALOG.descriptionLabel, 'Big')
    await submit(DIALOG.add)

    expect(vi.mocked(createExpectedPayment).mock.calls[0][1].amount_cents).toBe(9999999999)
  })

  test.each([
    [409, 'Choose an account you count as cash.', 'Choose an account you count as cash.'],
    [422, null, DIALOG.saveFailed],
  ])('C43 validation: API %i keeps the dialog open', async (status, detail, shown) => {
    vi.mocked(createExpectedPayment).mockResolvedValue({ ok: false, status, detail })
    renderPage()
    openAdd()
    type(DIALOG.amount, '2,300.50')
    type(DIALOG.date, '2026-11-20')
    type(DIALOG.descriptionLabel, 'Van repair deposit')
    await submit(DIALOG.add)

    expect(within(dialog()).getByRole('alert').textContent).toBe(shown)
    expect(field(DIALOG.amount).value).toBe('2,300.50')
    expect(field(DIALOG.descriptionLabel).value).toBe('Van repair deposit')
    expect(toast).not.toHaveBeenCalled()
  })
})
