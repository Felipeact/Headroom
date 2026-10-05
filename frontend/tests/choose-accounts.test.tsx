import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import type { PlaidLinkOptionsWithLinkToken } from 'react-plaid-link'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { updateAccount } from '@/app/onboarding/accounts/actions'
import { connectBank } from '@/app/onboarding/bank/actions'
import { ChooseAccounts } from '@/components/onboarding/choose-accounts'
import type { components } from '@/lib/api/schema'
import messages from '@/messages/en.json'

vi.mock('@/app/onboarding/accounts/actions', () => ({ updateAccount: vi.fn() }))
vi.mock('@/app/onboarding/bank/actions', () => ({ connectBank: vi.fn() }))
const link = vi.hoisted(() => ({
  open: vi.fn(),
  ready: true,
  options: undefined as PlaidLinkOptionsWithLinkToken | undefined,
}))
vi.mock('react-plaid-link', () => ({
  usePlaidLink: (options: PlaidLinkOptionsWithLinkToken) => {
    link.options = options
    return { open: link.open, ready: link.ready }
  },
}))
const push = vi.hoisted(() => vi.fn())
vi.mock('next/navigation', () => ({ useRouter: () => ({ push, refresh: vi.fn() }) }))

type Connection = components['schemas']['Connection']
type Account = components['schemas']['Account']

const ACCOUNTS = messages.Onboarding.Accounts
const BANK = messages.Onboarding.Bank
const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'

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
const SAVINGS = account('Reserve savings', {
  type: 'savings',
  mask: '9025',
  balance_cents: 3430000,
  included: false,
})
const LINE = account('Line of credit', {
  type: 'line_of_credit',
  mask: '7702',
  balance_cents: 0,
  available_cents: 2000000,
  included: false,
})

function bank(name: string, accounts: Account[], id = `c-${name}`): Connection {
  return { id, institution_name: name, created_at: '2026-10-04T15:00:00Z', accounts }
}

const HARBOR = bank('Harbor Community Bank', [CHECKING, SAVINGS, LINE])

function renderView(connections: Connection[] = [HARBOR]) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ChooseAccounts businessId={BUSINESS} linkToken="link-sandbox-123" connections={connections} />
    </NextIntlClientProvider>,
  )
}

const card = (name: string) => screen.getByRole('listitem', { name })
const follows = (a: Node, b: Node) =>
  Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)
const inOrder = (nodes: Node[]) => nodes.every((node, i) => i === 0 || follows(nodes[i - 1], node))
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement

beforeEach(() => {
  link.open.mockClear()
  link.ready = true
  link.options = undefined
  vi.mocked(updateAccount).mockReset()
  vi.mocked(connectBank).mockReset()
  push.mockClear()
})

describe('choose accounts view', () => {
  test('renders the mockup', () => {
    renderView()

    const nodes = [
      screen.getByRole('heading', { level: 1, name: ACCOUNTS.title }),
      screen.getByText('Harbor Community Bank is connected. Choose what Headroom counts as cash you can spend.'),
      card('Operating checking'),
      card('Reserve savings'),
      card('Line of credit'),
      screen.getByText(ACCOUNTS.primaryNote),
      button(ACCOUNTS.connectAnother),
      button(ACCOUNTS.continue),
    ]
    expect(inOrder(nodes)).toBe(true)
    expect(button(ACCOUNTS.connectAnother).querySelector('svg[aria-hidden="true"]')).not.toBeNull()
    expect(screen.queryByRole('heading', { level: 2 })).toBeNull()
  })

  test('two banks', () => {
    renderView([HARBOR, bank('RBC Royal Bank', [account('Payroll')])])

    expect(
      screen.getByText('Your banks are connected. Choose what Headroom counts as cash you can spend.'),
    ).toBeDefined()
    const headings = screen.getAllByRole('heading', { level: 2 })
    expect(headings.map((h) => h.textContent)).toEqual(['Harbor Community Bank', 'RBC Royal Bank'])
    expect(inOrder([headings[0], card('Line of credit'), headings[1], card('Payroll')])).toBe(true)
  })

  test('card header', () => {
    renderView([
      bank('Bank', [
        CHECKING,
        SAVINGS,
        account('Visa', { type: 'credit_card', mask: '1111' }),
        LINE,
        account('Money market', { type: 'other', mask: '3333', included: false }),
        account('No mask', { mask: null }),
        account('US chequing', { currency: 'USD', balance_cents: 120000, included: false }),
        account('No balance', { balance_cents: null }),
      ]),
    ])

    expect(within(card('Operating checking')).getByText('••2381 · Checking')).toBeDefined()
    expect(within(card('Operating checking')).getByText('$8,000')).toBeDefined()
    expect(within(card('Reserve savings')).getByText('••9025 · Savings')).toBeDefined()
    expect(within(card('Visa')).getByText('••1111 · Credit')).toBeDefined()
    expect(within(card('Line of credit')).getByText('••7702 · Credit')).toBeDefined()
    expect(within(card('Money market')).getByText('••3333 · Other')).toBeDefined()
    expect(within(card('No mask')).getByText('Checking')).toBeDefined()
    expect(within(card('No mask')).queryByText(/••/)).toBeNull()
    expect(within(card('US chequing')).getByText('US$1,200')).toBeDefined()
    expect(card('No balance').textContent).not.toMatch(/\$/)
  })

  test('checking switch', () => {
    renderView([bank('Bank', [CHECKING, account('Ops', { included: false })])])

    const on = within(card('Operating checking')).getByRole('switch', {
      name: 'Operating checking counts as cash',
    })
    expect(on.getAttribute('aria-checked')).toBe('true')
    expect(within(card('Operating checking')).getByText(ACCOUNTS.countsAsCash)).toBeDefined()
    const off = within(card('Ops')).getByRole('switch', { name: 'Ops counts as cash' })
    expect(off.getAttribute('aria-checked')).toBe('false')
  })

  test('savings segmented', () => {
    renderView([bank('Bank', [CHECKING, SAVINGS, account('Rainy day', { type: 'savings', included: true })])])

    const excluded = within(card('Reserve savings'))
    expect(excluded.getByText(ACCOUNTS.spendQuestion)).toBeDefined()
    const group = excluded.getByRole('radiogroup', { name: 'Count Reserve savings as cash' })
    const yes = within(group).getByRole('radio', { name: ACCOUNTS.spendYes })
    const no = within(group).getByRole('radio', { name: ACCOUNTS.spendNo })
    expect([yes.getAttribute('aria-checked'), no.getAttribute('aria-checked')]).toEqual(['false', 'true'])

    const included = within(screen.getByRole('radiogroup', { name: 'Count Rainy day as cash' }))
    expect(included.getByRole('radio', { name: ACCOUNTS.spendYes }).getAttribute('aria-checked')).toBe('true')
    expect(included.getByRole('radio', { name: ACCOUNTS.spendNo }).getAttribute('aria-checked')).toBe('false')
  })

  test('credit card and line of credit', () => {
    renderView([
      bank('Bank', [
        CHECKING,
        LINE,
        account('Visa', { type: 'credit_card', balance_cents: 81234, available_cents: 420000, included: false }),
        account('Closed card', { type: 'credit_card', available_cents: null, included: false }),
      ]),
    ])

    const line = within(card('Line of credit'))
    expect(line.getByText('$20,000')).toBeDefined()
    expect(line.getByText(ACCOUNTS.available)).toBeDefined()
    expect(line.getByText(ACCOUNTS.creditNote)).toBeDefined()
    const visa = within(card('Visa'))
    expect(visa.getByText('$4,200')).toBeDefined()
    expect(visa.queryByText('$812')).toBeNull()
    expect(card('Closed card').textContent).not.toMatch(/\$/)
    for (const name of ['Line of credit', 'Visa', 'Closed card']) {
      const scope = within(card(name))
      expect(scope.queryByRole('switch')).toBeNull()
      expect(scope.queryByRole('radiogroup')).toBeNull()
      expect(scope.queryByRole('radio')).toBeNull()
    }
  })

  test('cannot count: other type and non-CAD', () => {
    renderView([
      bank('Bank', [
        CHECKING,
        account('Money market', { type: 'other', included: false }),
        account('US chequing', { currency: 'USD', included: false }),
        account('US savings', { type: 'savings', currency: 'USD', included: false }),
      ]),
    ])

    expect(within(card('Money market')).getByText(ACCOUNTS.otherNote)).toBeDefined()
    expect(within(card('US chequing')).getByText(ACCOUNTS.currencyNote)).toBeDefined()
    expect(within(card('US savings')).getByText(ACCOUNTS.currencyNote)).toBeDefined()
    for (const name of ['Money market', 'US chequing', 'US savings']) {
      const scope = within(card(name))
      expect(scope.queryByRole('switch')).toBeNull()
      expect(scope.queryByRole('radiogroup')).toBeNull()
      expect(scope.queryByRole('radio')).toBeNull()
    }
  })

  test('primary radio', () => {
    renderView([bank('Bank', [CHECKING, account('Ops'), SAVINGS, LINE])])

    const radios = screen.getAllByRole('radio', { name: ACCOUNTS.primary })
    expect(radios).toHaveLength(2)
    expect(within(card('Operating checking')).getByRole('radio', { name: ACCOUNTS.primary }).getAttribute('aria-checked')).toBe('true')
    expect(within(card('Ops')).getByRole('radio', { name: ACCOUNTS.primary }).getAttribute('aria-checked')).toBe('false')
    expect(within(card('Reserve savings')).queryByRole('radio', { name: ACCOUNTS.primary })).toBeNull()
    const groups = new Set(radios.map((radio) => radio.closest('[role="radiogroup"]')))
    expect(groups.size).toBe(1)
    expect([...groups][0]?.getAttribute('aria-label')).toBe(ACCOUNTS.primaryGroupLabel)
  })

  test('saves changes', async () => {
    let finish: (value: { error: null }) => void = () => {}
    vi.mocked(updateAccount).mockReturnValue(new Promise((resolve) => (finish = resolve)))
    renderView([bank('Bank', [CHECKING, account('Ops'), SAVINGS])])

    fireEvent.click(within(card('Ops')).getByRole('switch'))
    expect(updateAccount).toHaveBeenLastCalledWith(BUSINESS, 'id-Ops', { included: false })

    // While the save is pending, every control is disabled.
    const controls = [
      ...screen.getAllByRole('switch'),
      ...screen.getAllByRole('radio'),
      button(ACCOUNTS.connectAnother),
      button(ACCOUNTS.continue),
    ]
    for (const control of controls) expect((control as HTMLButtonElement).disabled).toBe(true)
    await act(async () => finish({ error: null }))
    for (const control of controls) expect((control as HTMLButtonElement).disabled).toBe(false)

    vi.mocked(updateAccount).mockResolvedValue({ error: null })
    await act(async () => {
      fireEvent.click(within(card('Reserve savings')).getByRole('radio', { name: ACCOUNTS.spendYes }))
    })
    expect(updateAccount).toHaveBeenLastCalledWith(BUSINESS, `id-${SAVINGS.name}`, { included: true })

    await act(async () => {
      fireEvent.click(within(card('Ops')).getByRole('radio', { name: ACCOUNTS.primary }))
    })
    expect(updateAccount).toHaveBeenLastCalledWith(BUSINESS, 'id-Ops', { primary: true })

    vi.mocked(updateAccount).mockResolvedValue({ error: 'saveFailed' })
    await act(async () => {
      fireEvent.click(within(card('Ops')).getByRole('switch'))
    })
    const alert = screen.getByRole('alert')
    expect(alert.textContent).toContain(ACCOUNTS.errors.saveFailed)
    expect(follows(alert, button(ACCOUNTS.connectAnother))).toBe(true)
    // The props still say included, so the switch shows what the API last returned.
    expect(within(card('Ops')).getByRole('switch').getAttribute('aria-checked')).toBe('true')
  })

  test('connect another bank', async () => {
    renderView()

    expect(link.options?.token).toBe('link-sandbox-123')
    fireEvent.click(button(ACCOUNTS.connectAnother))
    expect(link.open).toHaveBeenCalledTimes(1)

    vi.mocked(connectBank).mockResolvedValue({ error: 'alreadyConnected' })
    await act(async () => link.options!.onSuccess('public-sandbox-2', {} as never))
    expect(connectBank).toHaveBeenCalledWith(BUSINESS, 'public-sandbox-2')
    expect(screen.getByRole('alert').textContent).toContain(BANK.errors.alreadyConnected)

    vi.mocked(connectBank).mockResolvedValue({ error: 'connectFailed' })
    await act(async () => link.options!.onSuccess('public-sandbox-3', {} as never))
    expect(screen.getByRole('alert').textContent).toContain(BANK.errors.connectFailed)

    await act(async () => link.options!.onExit!(null, {} as never))
    expect(screen.getByRole('alert').textContent).toBe('')

    const linkError = { error_type: 'ITEM_ERROR', error_code: 'X', error_message: 'x', display_message: null }
    await act(async () => link.options!.onExit!(linkError, {} as never))
    expect(screen.getByRole('alert').textContent).toContain(BANK.errors.connectFailed)
  })

  test('continue', () => {
    renderView()
    fireEvent.click(button(ACCOUNTS.continue))
    expect(push).toHaveBeenCalledWith('/')
  })

  test('continue with nothing included', () => {
    renderView([bank('Bank', [SAVINGS, LINE])])

    fireEvent.click(button(ACCOUNTS.continue))

    expect(push).not.toHaveBeenCalled()
    expect(screen.getByRole('alert').textContent).toContain(ACCOUNTS.errors.noneIncluded)
  })
})
