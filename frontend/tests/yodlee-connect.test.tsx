import { act, fireEvent, render, screen } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { connectBank, connectYodleeBank, launchFastLink } from '@/app/onboarding/bank/actions'
import { ConnectBank } from '@/components/onboarding/connect-bank'
import { FASTLINK_CONTAINER_ID } from '@/components/onboarding/use-yodlee-connect'
import messages from '@/messages/en.json'

vi.mock('@/app/onboarding/bank/actions', () => ({
  connectBank: vi.fn(),
  connectYodleeBank: vi.fn(),
  launchFastLink: vi.fn(),
}))
vi.mock('react-plaid-link', () => ({
  usePlaidLink: () => ({ open: vi.fn(), ready: true }),
}))

const BANK = messages.Onboarding.Bank
const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const LAUNCH = {
  launch: {
    fastlink_url: 'https://fastlink.test/fastlink',
    access_token: 'yodlee-user-token',
    config_name: 'Headroom',
    expires_in: 1800,
    provider_account_id: null,
  },
}

type OpenConfig = Parameters<NonNullable<Window['fastlink']>['open']>[0]
const fastlink = { open: vi.fn<(config: OpenConfig, containerId: string) => void>() }

function renderView(yodlee = true) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ConnectBank businessId={BUSINESS} linkToken="link-sandbox-123" yodlee={yodlee} />
    </NextIntlClientProvider>,
  )
}

const yodleeButton = () => screen.getByRole('button', { name: new RegExp(`${BANK.yodleeConnect}|${BANK.yodleeOpening}`) }) as HTMLButtonElement
const alert = () => screen.getByRole('alert')

beforeEach(() => {
  fastlink.open.mockReset()
  window.fastlink = fastlink
  vi.mocked(launchFastLink).mockReset()
  vi.mocked(connectYodleeBank).mockReset()
  vi.mocked(connectBank).mockReset()
})

afterEach(() => {
  delete window.fastlink
})

describe('yodlee connect (spec 17b)', () => {
  test('loading', async () => {
    let finish: (value: typeof LAUNCH) => void = () => {}
    vi.mocked(launchFastLink).mockReturnValue(new Promise((resolve) => (finish = resolve)))
    renderView()

    fireEvent.click(yodleeButton())

    await vi.waitFor(() => expect(yodleeButton().textContent).toBe(BANK.yodleeOpening))
    expect(yodleeButton().disabled).toBe(true)
    expect(yodleeButton().getAttribute('aria-busy')).toBe('true')
    await act(async () => finish(LAUNCH))
  })

  test('error and retry', async () => {
    vi.mocked(launchFastLink).mockResolvedValue({ error: 'launchFailed' })
    renderView()

    await act(async () => fireEvent.click(yodleeButton()))
    expect(alert().textContent).toBe(BANK.errors.launchFailed)
    expect(yodleeButton().disabled).toBe(false)

    vi.mocked(launchFastLink).mockResolvedValue(LAUNCH)
    await act(async () => fireEvent.click(yodleeButton()))
    expect(launchFastLink).toHaveBeenCalledTimes(2)
    expect(fastlink.open).toHaveBeenCalledTimes(1)
    expect(alert().textContent).toBe('')
  })

  test('success posts provider account', async () => {
    vi.mocked(launchFastLink).mockResolvedValue(LAUNCH)
    vi.mocked(connectYodleeBank).mockResolvedValue({ error: 'alreadyConnected' })
    renderView()

    await act(async () => fireEvent.click(yodleeButton()))
    const [config, containerId] = fastlink.open.mock.calls[0]
    expect(config.fastLinkURL).toBe('https://fastlink.test/fastlink')
    expect(config.accessToken).toBe('Bearer yodlee-user-token')
    expect(config.params).toEqual({ configName: 'Headroom' })
    expect(document.getElementById(containerId)).not.toBeNull()

    await act(async () => config.onSuccess({ providerAccountId: 42 }))

    expect(connectYodleeBank).toHaveBeenCalledWith(BUSINESS, '42')
    expect(alert().textContent).toBe(BANK.errors.alreadyConnected)
  })

  test('close returns to start', async () => {
    vi.mocked(launchFastLink).mockResolvedValue(LAUNCH)
    renderView()
    await act(async () => fireEvent.click(yodleeButton()))
    const [config, containerId] = fastlink.open.mock.calls[0]

    await act(async () => config.onClose())

    expect(connectYodleeBank).not.toHaveBeenCalled()
    expect(document.getElementById(containerId)).toBeNull()
    expect(yodleeButton().disabled).toBe(false)
    expect(yodleeButton().textContent).toBe(BANK.yodleeConnect)
    expect(alert().textContent).toBe('')
  })

  test('container exists when fastlink opens', async () => {
    // Like Yodlee's initialize.js: open() throws when the container is not in the document.
    const present: boolean[] = []
    fastlink.open.mockImplementation((_config, containerId) => {
      present.push(document.getElementById(containerId) !== null)
      if (!present.at(-1)) throw new Error('Invalid container element')
    })
    vi.mocked(launchFastLink).mockResolvedValue(LAUNCH)
    renderView()

    await act(async () => fireEvent.click(yodleeButton()))

    expect(present).toEqual([true])
    expect(alert().textContent).toBe('')

    fastlink.open.mockReset()
    fastlink.open.mockImplementation(() => {
      throw new Error('fastlink failed')
    })
    await act(async () => fireEvent.click(yodleeButton()))

    expect(alert().textContent).toBe(BANK.errors.launchFailed)
    expect(document.getElementById(FASTLINK_CONTAINER_ID)).toBeNull()
  })

  test('copy from messages', () => {
    renderView()

    expect(screen.getByText(BANK.yodleeHint)).toBeTruthy()
    expect(yodleeButton().textContent).toBe(BANK.yodleeConnect)
    expect(screen.getByText(BANK.yodleeProvider)).toBeTruthy()
  })
})
