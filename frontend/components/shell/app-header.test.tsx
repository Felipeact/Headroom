import { render, screen, within } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { expect, test, vi } from 'vitest'
import messages from '@/messages/en.json'
import { AppHeader } from './app-header'

vi.mock('next/navigation', () => ({ usePathname: () => '/' }))

function renderHeader(businessName?: string) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <AppHeader businessName={businessName} />
    </NextIntlClientProvider>,
  )
}

test('C10 with business name', () => {
  renderHeader('Harbor Street Plumbing')
  const desktop = screen.getByTestId('header-desktop-identity')
  expect(within(desktop).getByText('Business')).toBeDefined()
  expect(within(desktop).getByText('Harbor Street Plumbing')).toBeDefined()
  expect(screen.getByTestId('business-divider')).toBeDefined()
  expect(screen.getByTestId('header-phone-identity').textContent).toBe('Harbor Street Plumbing')
})

test('C11 without business name', () => {
  renderHeader()
  const desktop = screen.getByTestId('header-desktop-identity')
  expect(screen.queryByText('Business')).toBeNull()
  expect(screen.queryByTestId('business-divider')).toBeNull()
  expect(within(desktop).getByText('Headroom')).toBeDefined()
  expect(screen.getByTestId('header-phone-identity').textContent).toBe('Headroom')
})
