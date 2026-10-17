import { act, fireEvent, render, screen } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import type { PlaidLinkOptionsWithLinkToken } from 'react-plaid-link'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { connectBank } from '@/app/onboarding/bank/actions'
import { ConnectBank } from '@/components/onboarding/connect-bank'
import messages from '@/messages/en.json'

vi.mock('@/app/onboarding/bank/actions', () => ({ connectBank: vi.fn(), connectFlinksBank: vi.fn() }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ refresh: vi.fn() }) }))
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

const BANK = messages.Onboarding.Bank
const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const LINK_ERROR = {
  error_type: 'ITEM_ERROR',
  error_code: 'ITEM_LOGIN_REQUIRED',
  error_message: 'login required',
  display_message: null,
}

function renderView() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ConnectBank businessId={BUSINESS} linkToken="link-sandbox-123" />
    </NextIntlClientProvider>,
  )
}

const button = () => screen.getByRole('button') as HTMLButtonElement
const alert = () => screen.getByRole('alert')
const follows = (a: Node, b: Node) =>
  Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)

async function succeed(publicToken = 'public-sandbox-1') {
  await act(async () => link.options!.onSuccess(publicToken, {} as never))
}

beforeEach(() => {
  link.open.mockClear()
  link.ready = true
  link.options = undefined
  vi.mocked(connectBank).mockReset()
})

describe('connect bank view', () => {
  test('renders the mockup', () => {
    renderView()
    // The heading and the button share "Connect your bank", so the title comes by role.
    const heading = screen.getByRole('heading', { level: 1, name: BANK.title })
    const texts = [
      BANK.intro,
      BANK.readOnlyTitle,
      BANK.readOnlyBody,
      BANK.passwordTitle,
      BANK.passwordBody,
      BANK.controlTitle,
      BANK.controlBody,
      BANK.provider,
    ]
    const nodes = [heading, ...texts.map((text) => screen.getByText(text))]
    for (let i = 1; i < nodes.length; i++) expect(follows(nodes[i - 1], nodes[i])).toBe(true)
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(3)
    for (const item of items) expect(item.querySelector('svg[aria-hidden="true"]')).not.toBeNull()
    expect(button().textContent).toBe(BANK.connect)
    expect(follows(nodes.at(-1)!, button())).toBe(true)
  })

  test('opens plaid link', () => {
    renderView()

    expect(link.options?.token).toBe('link-sandbox-123')
    fireEvent.click(button())
    expect(link.open).toHaveBeenCalledTimes(1)
  })

  test('button states: disabled until ready, pending while saving', async () => {
    link.ready = false
    const first = renderView()
    expect(button().disabled).toBe(true)
    first.unmount()

    link.ready = true
    let finish: (value: { error: 'connectFailed' }) => void = () => {}
    vi.mocked(connectBank).mockReturnValue(new Promise((resolve) => (finish = resolve)))
    renderView()

    await succeed()
    expect(button().textContent).toBe(BANK.connecting)
    expect(button().disabled).toBe(true)
    expect(button().getAttribute('aria-busy')).toBe('true')
    fireEvent.click(button())
    expect(link.open).not.toHaveBeenCalled()
    expect(connectBank).toHaveBeenCalledTimes(1)

    await act(async () => finish({ error: 'connectFailed' }))
  })

  test('outcomes: duplicate, error, link closed, link error', async () => {
    renderView()

    vi.mocked(connectBank).mockResolvedValue({ error: 'alreadyConnected' })
    await succeed()
    expect(connectBank).toHaveBeenCalledWith(BUSINESS, 'public-sandbox-1', '/onboarding/accounts')
    expect(alert().textContent).toBe(BANK.errors.alreadyConnected)
    expect(button().disabled).toBe(false)

    vi.mocked(connectBank).mockResolvedValue({ error: 'connectFailed' })
    await succeed()
    expect(alert().textContent).toBe(BANK.errors.connectFailed)
    expect(button().disabled).toBe(false)

    await act(async () => link.options!.onExit!(null, {} as never))
    expect(alert().textContent).toBe('')
    expect(button().disabled).toBe(false)

    await act(async () => link.options!.onExit!(LINK_ERROR, {} as never))
    expect(alert().textContent).toBe(BANK.errors.connectFailed)
    expect(button().disabled).toBe(false)
    expect(follows(alert(), button())).toBe(true)
  })
})

describe('provider choice (spec 17a)', () => {
  const P = messages.BankProviders
  const FLINKS = {
    connect_url: 'https://toolbox-iframe.private.fin.ag/v2/?authorizeToken=token-1',
    origin: 'https://toolbox-iframe.private.fin.ag',
  }

  test('provider choice: with Flinks, both actions and the hint', () => {
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <ConnectBank businessId={BUSINESS} linkToken="link-sandbox-123" flinks={FLINKS} />
      </NextIntlClientProvider>,
    )

    const plaid = screen.getByRole('button', { name: P.plaid })
    const flinks = screen.getByRole('button', { name: P.flinks })
    expect(follows(plaid, flinks)).toBe(true)
    expect(screen.getByText(P.hint)).toBeTruthy()
    expect(screen.getByText(BANK.providerBoth)).toBeTruthy()
    fireEvent.click(plaid)
    expect(link.open).toHaveBeenCalledTimes(1)
  })

  test('provider choice: without Flinks, only the Plaid action', () => {
    renderView()

    expect(screen.getAllByRole('button')).toHaveLength(1)
    expect(button().textContent).toBe(BANK.connect)
    expect(screen.queryByText(P.hint)).toBeNull()
    expect(screen.getByText(BANK.provider)).toBeTruthy()
  })
})
