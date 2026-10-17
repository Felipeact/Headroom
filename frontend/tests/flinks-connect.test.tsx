import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { connectFlinksBank } from '@/app/onboarding/bank/actions'
import { FlinksConnect } from '@/components/onboarding/flinks-connect'
import messages from '@/messages/en.json'

vi.mock('@/app/onboarding/bank/actions', () => ({ connectFlinksBank: vi.fn() }))
const router = vi.hoisted(() => ({ refresh: vi.fn() }))
vi.mock('next/navigation', () => ({ useRouter: () => router }))

const P = messages.BankProviders
const BUSINESS = '6f1c2b0e-0000-4000-8000-000000000001'
const ORIGIN = 'https://toolbox-iframe.private.fin.ag'
const LOGIN_ID = '8b35f6c8-e7b6-41d3-98f8-08d68b7f8d31'
const FLINKS = { connect_url: `${ORIGIN}/v2/?authorizeToken=token-1&demo=true`, origin: ORIGIN }

function renderView() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <FlinksConnect businessId={BUSINESS} flinks={FLINKS} />
    </NextIntlClientProvider>,
  )
}

const flinksButton = () => screen.getByRole('button', { name: P.flinks })

function openDialog() {
  const button = flinksButton()
  button.focus()
  fireEvent.click(button)
  return button
}

async function post(data: unknown, origin = ORIGIN) {
  await act(async () => {
    window.dispatchEvent(new MessageEvent('message', { data, origin }))
  })
}

const redirect = (loginId = LOGIN_ID) => ({
  step: 'REDIRECT',
  institution: 'FlinksCapital',
  url: `http://localhost:3000/onboarding/bank?loginId=${loginId}&institution=FlinksCapital`,
})

beforeEach(() => {
  vi.mocked(connectFlinksBank).mockReset()
  vi.mocked(connectFlinksBank).mockResolvedValue({ error: 'connectFailed' })
  router.refresh.mockClear()
})

describe('flinks connect', () => {
  test('dialog loading and focus', async () => {
    renderView()
    const button = openDialog()

    const dialog = screen.getByRole('dialog', { name: P.dialogTitle })
    const frame = dialog.querySelector('iframe')!
    expect(frame.getAttribute('src')).toBe(FLINKS.connect_url)
    expect(frame.getAttribute('title')).toBe(P.frameTitle)
    expect(screen.getByRole('status').textContent).toBe(P.loading)

    fireEvent.load(frame)
    expect(screen.queryByRole('status')).toBeNull()

    fireEvent.keyDown(dialog, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(document.activeElement).toBe(button))
    // The authorize token is single-use: closing without connecting asks for a new one.
    expect(router.refresh).toHaveBeenCalledTimes(1)
  })

  test('message origin: another origin is ignored', async () => {
    renderView()
    openDialog()

    await post(redirect(), 'https://evil.example')
    await post({ step: 'APP_MOUNTED' })

    expect(connectFlinksBank).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog')).toBeTruthy()
  })

  test('message origin: a REDIRECT from the iframe connects with its loginId', async () => {
    renderView()
    openDialog()

    await post(redirect())

    expect(connectFlinksBank).toHaveBeenCalledWith(BUSINESS, LOGIN_ID, '/onboarding/accounts')
    expect(screen.queryByRole('dialog')).toBeNull()
    // The connect failed, and the iframe token is spent: the page asks for a fresh one.
    expect(router.refresh).toHaveBeenCalledTimes(1)
  })

  test('message origin: a REDIRECT without a loginId is a failed connect', async () => {
    renderView()
    openDialog()

    await post({ step: 'REDIRECT', url: 'http://localhost:3000/onboarding/bank' })

    expect(connectFlinksBank).not.toHaveBeenCalled()
    expect(screen.getByRole('alert').textContent).toContain(P.errors.connectFailed)
  })

  test('still preparing retry reuses the same loginId', async () => {
    vi.mocked(connectFlinksBank).mockResolvedValue({ error: 'stillPreparing' })
    renderView()
    openDialog()
    await post(redirect())

    expect(screen.getByRole('alert').textContent).toContain(P.errors.stillPreparing)
    const retry = screen.getByRole('button', { name: P.retry })
    await act(async () => fireEvent.click(retry))

    expect(connectFlinksBank).toHaveBeenCalledTimes(2)
    expect(vi.mocked(connectFlinksBank).mock.calls[1]).toEqual([BUSINESS, LOGIN_ID, '/onboarding/accounts'])
  })

  test('already connected shows its error and no retry', async () => {
    vi.mocked(connectFlinksBank).mockResolvedValue({ error: 'alreadyConnected' })
    renderView()
    openDialog()
    await post(redirect())

    expect(screen.getByRole('alert').textContent).toContain(P.errors.alreadyConnected)
    expect(screen.queryByRole('button', { name: P.retry })).toBeNull()
  })
})
